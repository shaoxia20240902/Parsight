"""
表理解异议字段核对 — 后台流水线

1. 从初稿 Markdown 提取有异议字段
2. 对异议字段执行 SELECT DISTINCT … LIMIT 500
3. 结合核实结果重新生成表理解并覆盖落库
"""

import logging
from typing import Any, Dict, List

from app.agents.understanding_agent import TableUnderstandingAgent
from app.models.database import async_session
from app.services.db_service import DBService

logger = logging.getLogger(__name__)

_running_tables: set[str] = set()


async def run_understanding_verification(table_name: str) -> None:
    """后台执行异议字段核对（使用独立 DB 会话）"""
    if table_name in _running_tables:
        return
    _running_tables.add(table_name)
    try:
        await _run_verification_impl(table_name)
    finally:
        _running_tables.discard(table_name)


async def _run_verification_impl(table_name: str) -> None:
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
            disputed = await agent.extract_disputed_fields(
                previous_content, table_name, column_names
            )
            logger.info(
                "表 %s 异议字段 %d 个: %s",
                table_name,
                len(disputed),
                [d["field_name"] for d in disputed],
            )

            verification_results: List[Dict[str, Any]] = []
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
                await db_service.set_understanding_verification_status(
                    table_name, "completed"
                )
                logger.info("表 %s 无异议字段，核对完成", table_name)
                return

            revised = await agent.regenerate_with_verification(
                agent_input, previous_content, verification_results
            )
            await db_service.save_understanding_verified(
                table_name, revised, verification_status="completed"
            )
            logger.info("表 %s 核对修订完成", table_name)

        except Exception as e:
            logger.exception("表 %s 异议核对失败: %s", table_name, e)
            await db_service.set_understanding_verification_status(table_name, "failed")
            raise
