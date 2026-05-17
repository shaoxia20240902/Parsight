"""
空间 Sheet 关联分析 — 异议关联 SQL 核对流水线
"""

import logging
from typing import Any, Dict, List

from app.agents.relations_agent import RelationsAnalysisAgent
from app.models.database import async_session
from app.services.db_service import DBService

logger = logging.getLogger(__name__)

_running_spaces: set[str] = set()


async def run_relations_verification(space_id: str) -> None:
    if space_id in _running_spaces:
        return
    _running_spaces.add(space_id)
    try:
        await _run_impl(space_id)
    finally:
        _running_spaces.discard(space_id)


async def _run_impl(space_id: str) -> None:
    async with async_session() as db:
        db_service = DBService(db)
        cached = await db_service.get_space_relations(space_id)
        if not cached or not cached.get("content"):
            await db_service.save_space_relations_verified(
                space_id, "", verification_status="failed"
            )
            return

        previous = cached["content"]
        try:
            sheets_context = await db_service.build_space_relations_context(space_id)
        except ValueError as e:
            logger.error("关联核对失败 %s: %s", space_id, e)
            await db_service.save_space_relations_verified(
                space_id, previous, verification_status="failed"
            )
            raise

        table_columns = {
            s["table_name"]: [c["name"] for c in s.get("columns", [])]
            for s in sheets_context
        }
        valid_tables = list(table_columns.keys())
        agent = RelationsAnalysisAgent()

        try:
            disputed = await agent.extract_disputed_relations(
                previous, valid_tables, table_columns
            )
            logger.info(
                "空间 %s 异议关联 %d 条: %s",
                space_id,
                len(disputed),
                disputed,
            )

            verification_results: List[Dict[str, Any]] = []
            for rel in disputed:
                stats = await db_service.verify_relation_join(
                    rel["from_table"],
                    rel["to_table"],
                    rel["from_field"],
                    rel["to_field"],
                    table_columns[rel["from_table"]],
                    table_columns[rel["to_table"]],
                )
                stats["issue_summary"] = rel.get("issue_summary", "")
                verification_results.append(stats)

            if not verification_results:
                await db_service.save_space_relations_verified(
                    space_id, previous, verification_status="completed"
                )
                return

            revised = await agent.regenerate_with_verification(
                sheets_context, previous, verification_results
            )
            await db_service.save_space_relations_verified(
                space_id, revised, verification_status="completed"
            )
            logger.info("空间 %s 关联分析核对完成", space_id)

        except Exception as e:
            logger.exception("空间 %s 关联核对失败: %s", space_id, e)
            await db_service.save_space_relations_verified(
                space_id, previous, verification_status="failed"
            )
            raise
