"""
表理解 API — 六维 AI 分析，Markdown 输出，异议字段后台核对
"""
import asyncio
import json
import logging
import time
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.understanding_agent import TableUnderstandingAgent
from app.models.database import get_db
from app.services.db_service import DBService
from app.services.understanding_verification import run_understanding_verification
from app.services.bi_understanding_tasks import (
    _generating_tables as _bg_generating_tables,
    _generation_progress,
)

router = APIRouter(prefix="/api/data", tags=["understanding"])
logger = logging.getLogger(__name__)

VerificationStatus = Literal["idle", "generating", "verifying", "completed", "failed"]


class UnderstandingResponse(BaseModel):
    content: str
    content_initial: Optional[str] = None
    is_cached: bool
    updated_at: Optional[str] = None
    verification_status: VerificationStatus = "idle"


class UnderstandingUpdateRequest(BaseModel):
    content: str


# 记录当前正在被同步请求生成理解的表名（避免同一表多个请求并发触发 LLM）
_generating_tables: set[str] = set()


async def _generate_initial_understanding(
    db_service: DBService,
    table_name: str,
    meta: dict,
) -> str:
    if table_name in _generating_tables:
        raise RuntimeError("该表正在生成中，请稍后刷新")
    _generating_tables.add(table_name)
    try:
        columns = await db_service.get_table_columns(table_name)
        sample_result = await db_service.fetch_sample_rows_from_table(table_name)
        row_count = await db_service.get_table_row_count(table_name)

        agent = TableUnderstandingAgent()
        return await agent.run({
            "sheet_name": meta.get("sheet_name") or table_name,
            "table_name": table_name,
            "columns": columns,
            "sample_rows": sample_result["rows"],
            "row_count": row_count,
            "first_n_count": sample_result["first_n_count"],
            "random_n_count": sample_result["random_n_count"],
        })
    finally:
        _generating_tables.discard(table_name)


async def _wait_verified_stream(db_service: DBService, table_name: str, last_sent_len: int = 0):
    """Keep the SSE open through anomaly verification and emit the final verified content."""
    last_status = ""
    while True:
        cached = await db_service.get_understanding_content(table_name)
        status = (cached or {}).get("verification_status") or "idle"
        content = (cached or {}).get("content") or ""

        if status != last_status:
            yield f"data: {json.dumps({'phase': status}, ensure_ascii=False)}\n\n"
            last_status = status

        if status in ("completed", "failed"):
            yield f"data: {json.dumps({'done': True, 'data': {'content': content, 'content_initial': (cached or {}).get('content_initial'), 'verification_status': status, 'updated_at': (cached or {}).get('updated_at')}}, ensure_ascii=False)}\n\n"
            return

        yield f"data: {json.dumps({'heartbeat': True, 'phase': status}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(2)


@router.get("/table/{table_name}/understanding", response_model=UnderstandingResponse)
async def get_table_understanding(
    table_name: str,
    background_tasks: BackgroundTasks,
    regenerate: bool = Query(False, description="是否强制重新生成"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取表的 AI 六维理解（非流式，仅用于读取缓存或触发后台生成）。
    """
    db_service = DBService(db)
    meta = await db_service.get_sheet_meta_by_table(table_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"未找到表: {table_name}")

    if not regenerate:
        cached = await db_service.get_understanding_content(table_name)
        if cached and cached.get("content"):
            status = cached.get("verification_status", "idle")
            if status == "verifying":
                background_tasks.add_task(run_understanding_verification, table_name)
            return UnderstandingResponse(
                content=cached["content"],
                content_initial=cached.get("content_initial"),
                is_cached=True,
                updated_at=cached.get("updated_at"),
                verification_status=status,
            )

        # 无缓存 —— 检查是否已有后台任务或同步请求正在生成
        if table_name in _bg_generating_tables or table_name in _generating_tables:
            logger.info("表 %s 理解正在后台生成中，返回 generating 状态", table_name)
            return UnderstandingResponse(
                content="",
                is_cached=False,
                verification_status="generating",
            )

    # 普通读取接口只返回当前状态，不再同步触发 LLM 生成。
    # 生成/重新生成统一走 SSE，避免表数据页面因为理解内容请求被长时间阻塞。
    return UnderstandingResponse(
        content="",
        content_initial=None,
        is_cached=False,
        updated_at=None,
        verification_status="idle",
    )


@router.post("/table/{table_name}/understanding/stream")
async def generate_table_understanding_stream(
    table_name: str,
    regenerate: bool = Query(False, description="是否强制重新生成"),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE 流式生成表的 AI 六维理解。

    事件格式：
      data: {"chunk": "..."}          # 逐字内容
      data: {"done": true, "data": {...}}  # 完成，含完整内容
      data: {"error": "..."}          # 错误
    """
    db_service = DBService(db)
    meta = await db_service.get_sheet_meta_by_table(table_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"未找到表: {table_name}")

    # 有缓存且非强制重新生成时，按状态决定是直接返回还是继续挂住复核长链
    if not regenerate:
        cached = await db_service.get_understanding_content(table_name)
        if cached and cached.get("content"):
            async def cached_stream():
                yield f"data: {json.dumps({'chunk': cached['content']}, ensure_ascii=False)}\n\n"
                status = cached.get("verification_status", "idle")
                if status in ("generating", "verifying"):
                    async for event in _wait_verified_stream(db_service, table_name, len(cached["content"])):
                        yield event
                else:
                    yield f"data: {json.dumps({'done': True, 'data': {'content': cached['content'], 'content_initial': cached.get('content_initial'), 'verification_status': status, 'updated_at': cached.get('updated_at')}}, ensure_ascii=False)}\n\n"
            return StreamingResponse(
                cached_stream(),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no"},
            )

        # 如果表正在后台或同步生成中，接入现有生成进度并流式推送
    if table_name in _bg_generating_tables or table_name in _generating_tables:
        async def watch_progress_stream():
            last_sent_len = 0
            # 先尝试推送数据库中已存在的中间进度
            cached = await db_service.get_understanding_content(table_name)
            if cached and cached.get("content"):
                content = cached["content"]
                yield f"data: {json.dumps({'chunk': content}, ensure_ascii=False)}\n\n"
                last_sent_len = len(content)

            while True:
                progress = _generation_progress.get(table_name)
                if progress:
                    current_content = progress.get("content", "")
                    status = progress.get("status", "generating")
                    if len(current_content) > last_sent_len:
                        new_part = current_content[last_sent_len:]
                        yield f"data: {json.dumps({'chunk': new_part}, ensure_ascii=False)}\n\n"
                        last_sent_len = len(current_content)
                    if status == "verifying":
                        yield f"data: {json.dumps({'phase': 'verifying'}, ensure_ascii=False)}\n\n"
                    if status in ("completed", "failed"):
                        yield f"data: {json.dumps({'done': True, 'data': {'content': current_content, 'verification_status': status}}, ensure_ascii=False)}\n\n"
                        return
                # 如果进度字典已被清理但表仍在生成中，继续等待
                elif table_name not in _bg_generating_tables and table_name not in _generating_tables:
                    # 生成已结束但可能没拿到最终内容，再读一次数据库
                    cached = await db_service.get_understanding_content(table_name)
                    if cached and cached.get("content"):
                        content = cached["content"]
                        if len(content) > last_sent_len:
                            new_part = content[last_sent_len:]
                            yield f"data: {json.dumps({'chunk': new_part}, ensure_ascii=False)}\n\n"
                        status = cached.get("verification_status", "idle")
                        if status in ("generating", "verifying"):
                            async for event in _wait_verified_stream(db_service, table_name, len(content)):
                                yield event
                        else:
                            yield f"data: {json.dumps({'done': True, 'data': {'content': content, 'content_initial': cached.get('content_initial'), 'verification_status': status, 'updated_at': cached.get('updated_at')}}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'done': True, 'data': {'content': '', 'verification_status': 'idle'}}, ensure_ascii=False)}\n\n"
                    return
                await asyncio.sleep(0.2)

        return StreamingResponse(
            watch_progress_stream(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    async def event_stream():
        full_content = ""
        try:
            _generating_tables.add(table_name)
            _generation_progress[table_name] = {"content": "", "status": "generating", "updated_at": time.time()}

            columns = await db_service.get_table_columns(table_name)
            sample_result = await db_service.fetch_sample_rows_from_table(table_name)
            row_count = await db_service.get_table_row_count(table_name)

            agent = TableUnderstandingAgent()
            async for chunk in agent.run_stream({
                "sheet_name": meta.get("sheet_name") or table_name,
                "table_name": table_name,
                "columns": columns,
                "sample_rows": sample_result["rows"],
                "row_count": row_count,
                "first_n_count": sample_result.get("first_n_count", 0),
                "random_n_count": sample_result.get("random_n_count", 0),
            }):
                full_content += chunk
                _generation_progress[table_name]["content"] = full_content
                _generation_progress[table_name]["updated_at"] = time.time()
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # 保存到数据库
            updated_at = await db_service.save_understanding_draft(
                table_name, full_content, verification_status="verifying"
            )
            _generation_progress[table_name]["status"] = "verifying"
            _generation_progress[table_name]["updated_at"] = time.time()
            # 后台启动核对
            asyncio.create_task(run_understanding_verification(table_name))

            yield f"data: {json.dumps({'phase': 'verifying', 'data': {'content': full_content, 'verification_status': 'verifying', 'updated_at': updated_at}}, ensure_ascii=False)}\n\n"
            async for event in _wait_verified_stream(db_service, table_name, len(full_content)):
                yield event

        except Exception as e:
            logger.exception("表 %s 流式理解生成失败: %s", table_name, e)
            _generation_progress[table_name]["status"] = "failed"
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            _generating_tables.discard(table_name)
            # 延迟清理进度字典，给 SSE 消费者留足时间读取最终状态
            await asyncio.sleep(5)
            _generation_progress.pop(table_name, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.put("/table/{table_name}/understanding", response_model=UnderstandingResponse)
async def update_table_understanding(
    table_name: str,
    body: UnderstandingUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """保存用户编辑后的理解内容（不再触发自动核对）"""
    db_service = DBService(db)
    meta = await db_service.get_sheet_meta_by_table(table_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"未找到表: {table_name}")

    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="理解内容不能为空")

    updated_at = await db_service.update_understanding_content(
        table_name, content, verification_status="idle"
    )

    return UnderstandingResponse(
        content=content,
        content_initial=None,
        is_cached=True,
        updated_at=updated_at,
        verification_status="idle",
    )
