"""
空间 Sheet 关联分析 API — Markdown 输出，异议关联 SQL 核对，支持初稿/终稿对比
"""
import asyncio
import json
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.relations_agent import RelationsAnalysisAgent
from app.models.database import get_db
from app.services.db_service import DBService
from app.services.relations_verification import run_relations_verification
from app.services.bi_understanding_tasks import (
    _generating_relations_spaces,
    _relations_generation_progress,
    run_space_relations_summary,
)

router = APIRouter(prefix="/api/data", tags=["relations"])

VerificationStatus = Literal["idle", "verifying", "completed", "failed"]


class RelationsResponse(BaseModel):
    space_id: str
    content: str
    content_initial: Optional[str] = None
    is_cached: bool = False
    updated_at: Optional[str] = None
    verification_status: VerificationStatus = "idle"


@router.get("/relations", response_model=RelationsResponse)
async def get_relations(
    background_tasks: BackgroundTasks,
    space_id: str = Query(...),
    regenerate: bool = Query(False, description="是否强制重新生成"),
    db: AsyncSession = Depends(get_db),
):
    db_service = DBService(db)

    tables = await db_service.get_tables_by_space(space_id)
    if not tables:
        return RelationsResponse(
            space_id=space_id,
            content="该空间下暂无数据表，请先上传 XLSX 文件。",
            is_cached=True,
            verification_status="idle",
        )

    if len(tables) < 2:
        return RelationsResponse(
            space_id=space_id,
            content="当前空间仅有 1 个 Sheet，无需跨表关联分析。上传包含多个 Sheet 的文件后再试。",
            is_cached=True,
            verification_status="idle",
        )

    if not regenerate:
        cached = await db_service.get_space_relations(space_id)
        if cached and cached.get("content"):
            status = cached.get("verification_status", "idle")
            if status == "verifying":
                background_tasks.add_task(run_relations_verification, space_id)
            return RelationsResponse(
                space_id=space_id,
                content=cached["content"],
                content_initial=cached.get("content_initial"),
                is_cached=True,
                updated_at=cached.get("updated_at"),
                verification_status=status,
            )

    try:
        sheets_context = await db_service.build_space_relations_context(space_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    agent = RelationsAnalysisAgent()
    content = await agent.run(sheets_context)
    updated_at = await db_service.save_space_relations_draft(space_id, content)

    background_tasks.add_task(run_relations_verification, space_id)

    return RelationsResponse(
        space_id=space_id,
        content=content,
        content_initial=content,
        is_cached=False,
        updated_at=updated_at,
        verification_status="verifying",
    )


async def _wait_relations_verified_stream(db_service: DBService, space_id: str, last_sent_len: int = 0):
    last_status = ""
    while True:
        cached = await db_service.get_space_relations(space_id)
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


@router.post("/relations/stream")
async def generate_relations_stream(
    space_id: str = Query(...),
    regenerate: bool = Query(False, description="是否强制重新生成"),
    db: AsyncSession = Depends(get_db),
):
    db_service = DBService(db)

    tables = await db_service.get_tables_by_space(space_id)
    if len(tables) < 2:
        async def short_stream():
            content = "当前空间少于 2 个 Sheet，无需跨表关联分析。"
            yield f"data: {json.dumps({'chunk': content}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'data': {'content': content, 'verification_status': 'idle'}}, ensure_ascii=False)}\n\n"
        return StreamingResponse(short_stream(), media_type="text/event-stream")

    if not regenerate:
        cached = await db_service.get_space_relations(space_id)
        if cached and cached.get("content"):
            async def cached_stream():
                content = cached["content"]
                yield f"data: {json.dumps({'chunk': content}, ensure_ascii=False)}\n\n"
                status = cached.get("verification_status", "idle")
                if status in ("generating", "verifying"):
                    async for event in _wait_relations_verified_stream(db_service, space_id, len(content)):
                        yield event
                else:
                    yield f"data: {json.dumps({'done': True, 'data': {'content': content, 'content_initial': cached.get('content_initial'), 'verification_status': status, 'updated_at': cached.get('updated_at')}}, ensure_ascii=False)}\n\n"
            return StreamingResponse(
                cached_stream(),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no"},
            )

    if regenerate and space_id not in _generating_relations_spaces:
        asyncio.create_task(run_space_relations_summary(space_id, regenerate=True))

    async def watch_stream():
        last_sent_len = 0
        while True:
            progress = _relations_generation_progress.get(space_id)
            if progress:
                current_content = progress.get("content", "")
                status = progress.get("status", "generating")
                if len(current_content) > last_sent_len:
                    yield f"data: {json.dumps({'chunk': current_content[last_sent_len:]}, ensure_ascii=False)}\n\n"
                    last_sent_len = len(current_content)
                if status == "verifying":
                    yield f"data: {json.dumps({'phase': 'verifying'}, ensure_ascii=False)}\n\n"
                if status in ("completed", "failed"):
                    async for event in _wait_relations_verified_stream(db_service, space_id, last_sent_len):
                        yield event
                    return
            elif space_id not in _generating_relations_spaces:
                cached = await db_service.get_space_relations(space_id)
                if cached and cached.get("content"):
                    content = cached["content"]
                    if len(content) > last_sent_len:
                        yield f"data: {json.dumps({'chunk': content[last_sent_len:]}, ensure_ascii=False)}\n\n"
                    status = cached.get("verification_status", "idle")
                    if status in ("generating", "verifying"):
                        async for event in _wait_relations_verified_stream(db_service, space_id, len(content)):
                            yield event
                    else:
                        yield f"data: {json.dumps({'done': True, 'data': {'content': content, 'content_initial': cached.get('content_initial'), 'verification_status': status, 'updated_at': cached.get('updated_at')}}, ensure_ascii=False)}\n\n"
                    return
                if not regenerate:
                    yield f"data: {json.dumps({'heartbeat': True, 'phase': 'waiting'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'heartbeat': True, 'phase': 'waiting'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(
        watch_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
