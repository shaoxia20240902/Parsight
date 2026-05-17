"""BI Builder context assembly.

This module keeps all data-reading and context-normalisation away from the
dialogue orchestrator. The builder agents receive only this compact structure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.bi_profiler import BIProfiler
from app.services.db_service import DBService


@dataclass
class BuilderContext:
    file_id: str
    space_id: Optional[str]
    sheets: List[Dict[str, Any]]
    profiles: List[Dict[str, Any]]
    bi_config: Dict[str, Any]
    categories: List[Dict[str, Any]]
    charts: List[Dict[str, Any]]
    filters: List[Dict[str, Any]]
    business_knowledge: List[Dict[str, Any]]
    user_preferences: List[Dict[str, Any]]


class BIBuilderContextAssembler:
    def __init__(self, db_service: DBService):
        self.db = db_service
        self.profiler = BIProfiler(db_service)

    async def load(self, file_id: str, space_id: Optional[str] = None) -> BuilderContext:
        file_record = await self.db.get_file_record(file_id)
        if not file_record:
            return BuilderContext(file_id, space_id, [], [], {}, [], [], [], [], [])

        effective_space_id = space_id or getattr(file_record, "space_id", None)
        metas = await self.db.get_sheet_metas(file_id)
        sheets = [self._sheet_from_meta(meta) for meta in metas]

        profiles: List[Dict[str, Any]] = []
        for sheet in sheets:
            try:
                profile = await self.profiler.profile_sheet(sheet)
            except Exception:
                profile = self._profile_from_meta(sheet)
            profile.setdefault("sheet_index", sheet.get("sheet_index"))
            profile.setdefault("sheet_name", sheet.get("sheet_name"))
            profile.setdefault("table_name", sheet.get("table_name"))
            profiles.append(profile)

        bi_config = await self.db.get_bi_config(file_id) or self._empty_bi_config(file_id, sheets)
        business_knowledge = await self.db.list_business_knowledge(file_id)
        user_preferences = await self.db.list_user_preferences(space_id=effective_space_id)
        return BuilderContext(
            file_id=file_id,
            space_id=effective_space_id,
            sheets=sheets,
            profiles=profiles,
            bi_config=bi_config,
            categories=bi_config.get("categories", []),
            charts=bi_config.get("charts", []),
            filters=bi_config.get("global_filters", []),
            business_knowledge=business_knowledge,
            user_preferences=user_preferences,
        )

    def _sheet_from_meta(self, meta: Any) -> Dict[str, Any]:
        columns = self._json_value(getattr(meta, "columns", None), [])
        return {
            "sheet_name": meta.sheet_name,
            "sheet_index": meta.sheet_index,
            "table_name": meta.table_name,
            "columns": columns or [],
            "row_count": meta.row_count,
            "summary": meta.summary or "",
            "key_dimensions": self._json_value(getattr(meta, "key_dimensions", None), []),
            "key_metrics": self._json_value(getattr(meta, "key_metrics", None), []),
        }

    def _profile_from_meta(self, sheet: Dict[str, Any]) -> Dict[str, Any]:
        fields = []
        for column in sheet.get("columns") or []:
            name = column.get("name") if isinstance(column, dict) else str(column)
            col_type = (column.get("type") if isinstance(column, dict) else "") or "text"
            data_role = "metric" if col_type in {"number", "integer", "float", "decimal"} else "dimension"
            fields.append({
                "field": name,
                "data_role": data_role,
                "groupable": data_role == "dimension",
                "filterable": True,
                "sample_values": [],
            })
        return {
            "sheet_name": sheet.get("sheet_name"),
            "sheet_index": sheet.get("sheet_index"),
            "table_name": sheet.get("table_name"),
            "fields": fields,
            "row_count": sheet.get("row_count"),
        }

    def _empty_bi_config(self, file_id: str, sheets: List[Dict[str, Any]]) -> Dict[str, Any]:
        categories = []
        for idx, sheet in enumerate(sheets):
            categories.append({
                "id": f"sheet_{sheet.get('sheet_index', idx)}",
                "name": sheet.get("sheet_name"),
                "display_name": sheet.get("sheet_name"),
                "source": "sheet",
                "table_name": sheet.get("table_name"),
                "sheet_index": sheet.get("sheet_index", idx),
            })
        return {
            "version": 3,
            "file_id": file_id,
            "categories": categories,
            "custom_categories": [],
            "global_filters": [],
            "charts": [],
        }

    def _json_value(self, raw: Any, default: Any) -> Any:
        if raw is None:
            return default
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return default
        return raw
