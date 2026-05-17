"""BI 生成前置：六维理解门禁。"""

from typing import Any, Dict, List, Tuple

from app.services.db_service import DBService


async def resolve_understanding_text(db: DBService, table_name: str) -> str | None:
    cached = await db.get_understanding_content(table_name)
    if not cached:
        return None
    text = (cached.get("content") or "").strip()
    if not text:
        text = (cached.get("content_initial") or "").strip()
    return text or None


async def check_understanding_ready(db: DBService, file_id: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    返回 (是否全部就绪, 未就绪表列表)。
    未就绪项: { table_name, sheet_name, verification_status }
    """
    metas = await db.get_sheet_metas(file_id)
    pending: List[Dict[str, Any]] = []
    for meta in metas:
        text = await resolve_understanding_text(db, meta.table_name)
        if not text:
            cached = await db.get_understanding_content(meta.table_name)
            status = (cached or {}).get("verification_status", "idle")
            pending.append({
                "table_name": meta.table_name,
                "sheet_name": meta.sheet_name,
                "verification_status": status,
            })
    return len(pending) == 0, pending


def understanding_gate_http_detail(pending: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "detail": "以下表尚未完成六维理解，无法生成 BI 看板",
        "pending_tables": [p["table_name"] for p in pending],
        "pending_sheets": pending,
        "action": "wait_or_regenerate_understanding",
    }
