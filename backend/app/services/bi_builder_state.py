"""Persistent state store for BI builder sessions."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from app.services.db_service import DBService


class BIBuilderStateStore:
    def __init__(self, db_service: DBService):
        self.db = db_service

    async def load_or_create(
        self,
        session_id: Optional[str],
        file_id: str,
        space_id: Optional[str],
    ) -> Dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        session = await self.db.get_builder_session(sid)
        if not session:
            session = await self.db.create_builder_session(sid, file_id, space_id)
        return self._normalise(session)

    async def save(self, session: Dict[str, Any], **updates: Any) -> Dict[str, Any]:
        session.update(updates)
        await self.db.update_builder_session(session["id"], **updates)
        return session

    def _normalise(self, session: Dict[str, Any]) -> Dict[str, Any]:
        for key, default in {
            "scope_plan": {},
            "chart_list": [],
            "pending_input_ui": {},
            "created_chart_ids": [],
            "knowledge_cards": [],
            "preference_cards": [],
        }.items():
            session[key] = self._json_value(session.get(key), default)
        return session

    def _json_value(self, raw: Any, default: Any) -> Any:
        if raw is None:
            return default
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return default
        return raw
