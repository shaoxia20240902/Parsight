"""
表理解异议字段核对 — 后台流水线

1. 从初稿 Markdown 提取有异议字段
2. 对异议字段执行 SELECT DISTINCT … LIMIT 500
3. 结合核实结果重新生成表理解并覆盖落库
"""

import asyncio
import logging
from typing import Any, Dict, List

from app.agents.understanding_agent import TableUnderstandingAgent
from app.models.database import async_session
from app.services.db_service import DBService

logger = logging.getLogger(__name__)

_running_tables: set[str] = set()

# 限制同时进行的核对任务数
_VERIFICATION_SEMAPHORE = asyncio.Semaphore(3)


async def run_understanding_verification(table_name: str) -> None:
    """后台执行异议字段核对（使用独立 DB 会话）"""
    if table_name in _running_tables:
        return
    _running_tables.add(table_name)
    try:
        async with _VERIFICATION_SEMAPHORE:
            await _run_verification_impl(table_name)
    finally:
        _running_tables.discard(table_name)


async def _run_verification_impl(table_name: str) -> None:
    # 阶段 1：获取已有数据和初稿（短 DB 会话）
    async with async_session() as db:
        db_service = DBService(db)
        meta = await db_service.get_sheet_meta_by_table(table_name)
        if not meta:
            logger.error("核对失败：未找到表 %s", table_name)
            return

        cached = await db_service.get_understanding_content(table_name)
        if not cached or not cached.get("content"):
            await db_service.set_understanding_verification_status(table_name, "failed")
            return

        previous_content = cached["content"]
        sheet_name = meta.get("sheet_name") or table_name
        columns = await db_service.get_table_columns(table_name)
        column_names = [c["name"] for c in columns]
        sample_result = await db_service.fetch_sample_rows_from_table(table_name)
        row_count = await db_service.get_table_row_count(table_name)

    agent_input = {
        "sheet_name": sheet_name,
        "table_name": table_name,
        "columns": columns,
        "sample_rows": sample_result["rows"],
        "row_count": row_count,
        "first_n_count": sample_result["first_n_count"],
        "random_n_count": sample_result["random_n_count"],
    }

    agent = TableUnderstandingAgent()

    try:
        # 阶段 2：提取异议字段（LLM 调用，无 DB 会话）
        disputed = await agent.extract_disputed_fields(
            previous_content, table_name, column_names
        )
        logger.info(
            "表 %s 异议字段 %d 个: %s",
            table_name,
            len(disputed),
            [d["field_name"] for d in disputed],
        )

        # 阶段 3：查询异议字段的去重值（短 DB 会话）
        verification_results: List[Dict[str, Any]] = []
        if disputed:
            async with async_session() as db:
                db_service = DBService(db)
                for item in disputed:
                    field_name = item["field_name"]
                    distinct_values = await db_service.fetch_distinct_field_values(
                        table_name, field_name, column_names, limit=500
                    )
                    verification_results.append({
                        "table_name": table_name,
                        "field_name": field_name,
                        "issue_summary": item.get("issue_summary", ""),
                        "distinct_count": len(distinct_values),
                        "distinct_values": distinct_values,
                    })

        if not verification_results:
            async with async_session() as db:
                db_service = DBService(db)
                await db_service.set_understanding_verification_status(
                    table_name, "completed"
                )
            logger.info("表 %s 无异议字段，核对完成", table_name)
            return

        # 阶段 4：重新生成（LLM 调用，无 DB 会话）
        revised = await agent.regenerate_with_verification(
            agent_input, previous_content, verification_results
        )

        # 阶段 5：保存结果（短 DB 会话）
        async with async_session() as db:
            db_service = DBService(db)
            await db_service.save_understanding_verified(
                table_name, revised, verification_status="completed"
            )
        logger.info("表 %s 核对修订完成", table_name)

    except Exception as e:
        logger.exception("表 %s 异议核对失败: %s", table_name, e)
        async with async_session() as db:
            db_service = DBService(db)
            await db_service.set_understanding_verification_status(table_name, "failed")
        raise
