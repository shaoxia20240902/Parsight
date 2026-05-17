"""
表理解 API — 六维 AI 分析，Markdown 输出，异议字段后台核对
"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.understanding_agent import TableUnderstandingAgent
from app.models.database import get_db
from app.services.db_service import DBService
from app.services.understanding_verification import run_understanding_verification

router = APIRouter(prefix="/api/data", tags=["understanding"])
logger = logging.getLogger(__name__)

VerificationStatus = Literal["idle", "verifying", "completed", "failed"]


class UnderstandingResponse(BaseModel):
    content: str
    content_initial: Optional[str] = None
    is_cached: bool
    updated_at: Optional[str] = None
    verification_status: VerificationStatus = "idle"


class UnderstandingUpdateRequest(BaseModel):
    content: str


async def _generate_initial_understanding(
    db_service: DBService,
    table_name: str,
    meta: dict,
) -> str:
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


@router.get("/table/{table_name}/understanding", response_model=UnderstandingResponse)
async def get_table_understanding(
    table_name: str,
    background_tasks: BackgroundTasks,
    regenerate: bool = Query(False, description="是否强制重新生成"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取表的 AI 六维理解。

    - 首次/重新生成：先返回初稿并立即展示，后台核对异议字段后覆盖
    - 已有缓存：直接返回（含 verification_status，前端可轮询）
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

    content = await _generate_initial_understanding(db_service, table_name, meta)
    updated_at = await db_service.save_understanding_draft(table_name, content)

    background_tasks.add_task(run_understanding_verification, table_name)

    return UnderstandingResponse(
        content=content,
        content_initial=content,
        is_cached=False,
        updated_at=updated_at,
        verification_status="verifying",
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
