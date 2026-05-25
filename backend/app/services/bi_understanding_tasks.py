"""上传后异步执行单表六维理解。"""

import asyncio
import logging
import time
from typing import Dict, Any

from app.agents.understanding_agent import TableUnderstandingAgent
from app.agents.relations_agent import RelationsAnalysisAgent
from app.agents.recommendation_agent import ChatRecommendationAgent
from app.models.database import async_session
from app.services.ai_service import AIService
from app.services.db_service import DBService
from app.services.understanding_verification import run_understanding_verification

logger = logging.getLogger(__name__)

_running_files: set[str] = set()

# 记录当前正在被后台任务生成理解的表名（供前端轮询时判断，避免重复触发同步生成）
_generating_tables: set[str] = set()

# 限制同时进行的表理解 LLM 调用数（避免压垮 LLM API）
_SHEET_SEMAPHORE = asyncio.Semaphore(3)

# 表理解实时生成进度（供 SSE 端点读取）
# {table_name: {"content": str, "status": "generating"|"verifying"|"completed"|"failed", "updated_at": float}}
_generation_progress: Dict[str, Dict[str, Any]] = {}

# 空间关联总结实时生成进度（供 SSE 端点读取）
# {space_id: {"content": str, "status": "generating"|"verifying"|"completed"|"failed", "updated_at": float}}
_relations_generation_progress: Dict[str, Dict[str, Any]] = {}
_generating_relations_spaces: set[str] = set()


async def _generate_recommendations(file_id: str, sheets_info: list) -> None:
    """基于 Sheet 理解和关联总结生成对话推荐问题。"""
    agent = ChatRecommendationAgent()

    async with async_session() as db:
        db_service = DBService(db)

        # 收集所有 Sheet 的理解内容
        sheets_data = []
        for sheet in sheets_info:
            table_name = sheet["table_name"]
            understanding = await db_service.get_understanding_content(table_name)
            columns = await db_service.get_table_columns(table_name)
            meta = await db_service.get_sheet_meta_by_table(table_name)
            sheets_data.append({
                "sheet_name": sheet["name"],
                "table_name": table_name,
                "understanding": understanding.get("content", "") if understanding else "",
                "fields": [c.get("name") or c.get("field") for c in columns],
                "row_count": meta.row_count if meta else 0,
            })

        # 获取关联总结（如果空间有）
        file_record = await db_service.get_file_record(file_id)
        relations_summary = ""
        if file_record and file_record.space_id:
            relations = await db_service.get_space_relations(file_record.space_id)
            if relations:
                relations_summary = relations.get("content", "")

    # LLM 调用在 DB 会话外执行
    try:
        result = await agent.run({
            "sheets": sheets_data,
            "relations_summary": relations_summary,
            "file_summary": sheets_data[0]["understanding"][:500] if sheets_data else "",
        })

        async with async_session() as db:
            db_service = DBService(db)
            await db_service.save_recommended_questions(
                file_id,
                {
                    "insight_groups": result.get("insight_groups", []),
                    "deep_questions": result.get("deep_questions", []),
                    "builder_questions": result.get("builder_questions", []),
                },
                status="completed",
            )
        logger.info("文件 %s 推荐问题生成完成", file_id)
    except Exception as e:
        logger.warning("文件 %s 推荐问题生成失败: %s", file_id, e)
        async with async_session() as db:
            db_service = DBService(db)
            await db_service.save_recommended_questions(file_id, {}, status="failed")
        raise


async def _wait_sheet_verification_done(file_id: str, timeout_seconds: int = 1800) -> None:
    """等待同一文件下单表理解离开 generating/verifying，避免关联总结吃到半成品。"""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        async with async_session() as db:
            db_service = DBService(db)
            metas = await db_service.get_sheet_metas(file_id)
            statuses = [
                (getattr(meta, "understanding_verification_status", None) or "idle")
                for meta in metas
            ]
        if statuses and all(status in ("completed", "failed") for status in statuses):
            return
        await asyncio.sleep(2)


async def run_space_relations_summary(space_id: str, regenerate: bool = False) -> None:
    """后台生成空间关联总结，并启动异常复核。"""
    if not space_id or space_id in _generating_relations_spaces:
        return

    _generating_relations_spaces.add(space_id)
    _relations_generation_progress[space_id] = {
        "content": "",
        "status": "generating",
        "updated_at": time.time(),
    }
    try:
        async with async_session() as db:
            db_service = DBService(db)
            if not regenerate:
                cached = await db_service.get_space_relations(space_id)
                if cached and cached.get("content") and cached.get("verification_status") == "completed":
                    _relations_generation_progress[space_id].update({
                        "content": cached["content"],
                        "status": "completed",
                        "updated_at": time.time(),
                    })
                    return
            sheets_context = await db_service.build_space_relations_context(space_id)

        content = ""
        agent = RelationsAnalysisAgent()
        async for chunk in agent.run_stream(sheets_context):
            content += chunk
            _relations_generation_progress[space_id]["content"] = content
            _relations_generation_progress[space_id]["updated_at"] = time.time()

        async with async_session() as db:
            db_service = DBService(db)
            await db_service.save_space_relations_draft(
                space_id, content, verification_status="verifying"
            )

        _relations_generation_progress[space_id]["status"] = "verifying"
        _relations_generation_progress[space_id]["updated_at"] = time.time()

        from app.services.relations_verification import run_relations_verification

        asyncio.create_task(run_relations_verification(space_id))
    except Exception as e:
        logger.exception("空间 %s 关联总结生成失败: %s", space_id, e)
        _relations_generation_progress[space_id]["status"] = "failed"
        async with async_session() as db:
            db_service = DBService(db)
            await db_service.save_space_relations_draft(
                space_id,
                f"## 关联总结生成失败\n\n错误信息：{e}\n\n请稍后点击「重新生成」重试。",
                verification_status="failed",
            )
    finally:
        _generating_relations_spaces.discard(space_id)
        await asyncio.sleep(30)
        _relations_generation_progress.pop(space_id, None)


async def run_post_upload_understanding(file_id: str, sheets_info: list) -> None:
    """后台：Sheet 短摘要 + 六维理解（不生成 BI）。"""
    if file_id in _running_files:
        return
    _running_files.add(file_id)
    try:
        await _run_impl(file_id, sheets_info)
    finally:
        _running_files.discard(file_id)


async def _run_impl(file_id: str, sheets_info: list) -> None:
    # 阶段 1：用短会话获取元数据
    async with async_session() as db:
        db_service = DBService(db)
        metas = await db_service.get_sheet_metas(file_id)
        meta_by_table = {m.table_name: m for m in metas}

    # 阶段 2：为每张表准备输入数据（限制并发，避免 DB 被 ORDER BY RAND() 压垮）
    _PREP_SEMAPHORE = asyncio.Semaphore(3)

    async def _prepare_sheet_input(sheet: dict) -> dict:
        async with _PREP_SEMAPHORE:
            async with async_session() as db:
                db_service = DBService(db)
                table_name = sheet["table_name"]
                columns = await db_service.get_table_columns(table_name)
                sample = await db_service.fetch_sample_rows_from_table(table_name)
                row_count = await db_service.get_table_row_count(table_name)
                return {
                    "sheet": sheet,
                    "columns": columns,
                    "sample": sample,
                    "row_count": row_count,
                    "meta": meta_by_table.get(table_name),
                }

    sheet_inputs = await asyncio.gather(*[
        _prepare_sheet_input(sheet) for sheet in sheets_info
    ])

    # 阶段 3：并发处理每张表（受信号量限制）
    async def _process_one(sheet_input: dict) -> None:
        sheet = sheet_input["sheet"]
        table_name = sheet["table_name"]
        _generating_tables.add(table_name)
        _generation_progress[table_name] = {"content": "", "status": "generating", "updated_at": time.time()}
        try:
            async with _SHEET_SEMAPHORE:
                columns = sheet_input["columns"]
                sample = sheet_input["sample"]
                row_count = sheet_input["row_count"]
                meta = sheet_input["meta"]

                ai_service = AIService()
                understanding_agent = TableUnderstandingAgent()

                try:
                    # Sheet 摘要（LLM 调用，无 DB 会话）
                    summary_result = await ai_service.analyze_sheet({
                        "sheet_name": sheet["name"],
                        "columns": columns,
                        "row_count": row_count,
                        "sample_data": sample["rows"],
                    })
                except Exception as e:
                    logger.warning("表 %s Sheet 摘要失败: %s", table_name, e)
                    summary_result = {"summary": "", "key_dimensions": [], "key_metrics": []}

                # 保存摘要（短 DB 会话）
                if meta:
                    async with async_session() as db:
                        db_service = DBService(db)
                        await db_service.update_sheet_summary(meta.id, summary_result)

                try:
                    # 六维理解（流式生成，逐 chunk 保存进度）
                    understanding_content = ""
                    chunk_count = 0
                    async for chunk in understanding_agent.run_stream({
                        "sheet_name": sheet["name"],
                        "table_name": table_name,
                        "columns": columns,
                        "sample_rows": sample["rows"],
                        "row_count": row_count,
                        "first_n_count": sample.get("first_n_count", 0),
                        "random_n_count": sample.get("random_n_count", 0),
                    }):
                        understanding_content += chunk
                        _generation_progress[table_name]["content"] = understanding_content
                        _generation_progress[table_name]["updated_at"] = time.time()
                        chunk_count += 1
                        # 每 20 个 chunk 保存一次中间进度到数据库
                        if chunk_count % 20 == 0:
                            async with async_session() as db:
                                db_service = DBService(db)
                                await db_service.save_understanding_draft(
                                    table_name, understanding_content, verification_status="generating"
                                )
                except Exception as e:
                    logger.error("表 %s 六维理解生成失败: %s", table_name, e)
                    _generation_progress[table_name]["status"] = "failed"
                    # 保存失败标记，让前端知道
                    async with async_session() as db:
                        db_service = DBService(db)
                        await db_service.save_understanding_draft(
                            table_name,
                            f"## 表理解生成失败\n\n错误信息：{e}\n\n请稍后点击「重新生成」重试。",
                            verification_status="failed",
                        )
                    return

                # 保存初稿（短 DB 会话）
                async with async_session() as db:
                    db_service = DBService(db)
                    await db_service.save_understanding_draft(
                        table_name, understanding_content, verification_status="verifying"
                    )

                _generation_progress[table_name]["status"] = "verifying"
                _generation_progress[table_name]["updated_at"] = time.time()

                # 后台启动核对（不阻塞）
                asyncio.create_task(run_understanding_verification(table_name))
        finally:
            _generating_tables.discard(table_name)
            # 延迟清理进度字典，给 SSE 消费者留足时间读取最终状态
            await asyncio.sleep(5)
            _generation_progress.pop(table_name, None)

    await asyncio.gather(*[_process_one(si) for si in sheet_inputs])

    async with async_session() as db:
        db_service = DBService(db)
        file_record = await db_service.get_file_record(file_id)
        space_id = file_record.space_id if file_record else None

    if space_id:
        await _wait_sheet_verification_done(file_id)
        await run_space_relations_summary(space_id, regenerate=True)

    # 阶段 4：生成推荐问题（在 DB 会话外执行 LLM）
    try:
        async with async_session() as db:
            db_service = DBService(db)
            await db_service.save_recommended_questions(file_id, {}, status="generating")

        await _generate_recommendations(file_id, sheets_info)
    except Exception as e:
        logger.warning("文件 %s 推荐问题生成失败: %s", file_id, e)

    async with async_session() as db:
        db_service = DBService(db)
        await db_service.update_file_status(file_id, "understanding_ready")
    logger.info("文件 %s 全部表理解已完成，状态 understanding_ready", file_id)
