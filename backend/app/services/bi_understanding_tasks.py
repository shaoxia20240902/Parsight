"""上传后异步执行单表六维理解。"""

import asyncio
import logging

from app.agents.understanding_agent import TableUnderstandingAgent
from app.agents.recommendation_agent import ChatRecommendationAgent
from app.models.database import async_session
from app.services.ai_service import AIService
from app.services.db_service import DBService
from app.services.understanding_verification import run_understanding_verification

logger = logging.getLogger(__name__)

_running_files: set[str] = set()


async def _generate_recommendations(db_service: DBService, file_id: str, sheets_info: list) -> None:
    """基于 Sheet 理解和关联总结生成对话推荐问题。"""
    agent = ChatRecommendationAgent()

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

    try:
        result = await agent.run({
            "sheets": sheets_data,
            "relations_summary": relations_summary,
            "file_summary": sheets_data[0]["understanding"][:500] if sheets_data else "",
        })
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
        await db_service.save_recommended_questions(file_id, {}, status="failed")
        raise


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
    async with async_session() as db:
        db_service = DBService(db)
        ai_service = AIService()
        understanding_agent = TableUnderstandingAgent()
        metas = await db_service.get_sheet_metas(file_id)
        meta_by_table = {m.table_name: m for m in metas}

        for sheet in sheets_info:
            table_name = sheet["table_name"]
            columns = await db_service.get_table_columns(table_name)
            sample = await db_service.fetch_sample_rows_from_table(table_name)
            row_count = await db_service.get_table_row_count(table_name)

            summary_result = await ai_service.analyze_sheet({
                "sheet_name": sheet["name"],
                "columns": columns,
                "row_count": row_count,
                "sample_data": sample["rows"],
            })
            meta = meta_by_table.get(table_name)
            if meta:
                await db_service.update_sheet_summary(meta.id, summary_result)

            understanding_content = await understanding_agent.run({
                "sheet_name": sheet["name"],
                "table_name": table_name,
                "columns": columns,
                "sample_rows": sample["rows"],
                "row_count": row_count,
                "first_n_count": sample.get("first_n_count", 0),
                "random_n_count": sample.get("random_n_count", 0),
            })
            await db_service.save_understanding_draft(
                table_name, understanding_content, verification_status="verifying"
            )
            asyncio.create_task(run_understanding_verification(table_name))

        # 生成对话推荐问题
        try:
            await db_service.update_file_status(file_id, "generating_recommendations")
            await _generate_recommendations(db_service, file_id, sheets_info)
        except Exception as e:
            logger.warning("文件 %s 推荐问题生成失败: %s", file_id, e)

        await db_service.update_file_status(file_id, "understanding_ready")
        logger.info("文件 %s 全部表理解已完成，状态 understanding_ready", file_id)
