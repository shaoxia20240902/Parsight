"""上传后异步执行单表六维理解。"""

import asyncio
import logging

from app.agents.understanding_agent import TableUnderstandingAgent
from app.models.database import async_session
from app.services.ai_service import AIService
from app.services.db_service import DBService
from app.services.understanding_verification import run_understanding_verification

logger = logging.getLogger(__name__)

_running_files: set[str] = set()


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

        await db_service.update_file_status(file_id, "understanding_ready")
        logger.info("文件 %s 全部表理解已完成，状态 understanding_ready", file_id)
