"""
空间 Sheet 关联分析 API — Markdown 输出，异议关联 SQL 核对，支持初稿/终稿对比
"""
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.relations_agent import RelationsAnalysisAgent
from app.models.database import get_db
from app.services.db_service import DBService
from app.services.relations_verification import run_relations_verification

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
