import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.services.db.utils import json_default


class KnowledgeMixin:
    async def list_business_knowledge(
        self, file_id: str, table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM bi_business_knowledge
            WHERE file_id = :file_id AND status = 'active'
        """
        params: Dict[str, Any] = {"file_id": file_id}
        if table_name:
            sql += " AND (table_name = :table_name OR table_name IS NULL)"
            params["table_name"] = table_name
        result = await self.db.execute(text(sql), params)
        return [dict(row._mapping) for row in result.fetchall()]

    async def save_business_knowledge(
        self,
        file_id: str,
        term: str,
        canonical: str,
        table_name: Optional[str] = None,
        knowledge_type: str = "alias",
        definition: Optional[str] = None,
        scope: str = "file",
    ) -> str:
        knowledge_id = str(uuid.uuid4())
        now = datetime.utcnow()
        await self.db.execute(
            text("""
                INSERT INTO bi_business_knowledge
                (id, file_id, table_name, term, canonical, knowledge_type, definition, scope, status, created_at, updated_at)
                VALUES
                (:id, :file_id, :table_name, :term, :canonical, :knowledge_type, :definition, :scope, 'active', :created_at, :updated_at)
            """),
            {
                "id": knowledge_id,
                "file_id": file_id,
                "table_name": table_name,
                "term": term,
                "canonical": canonical,
                "knowledge_type": knowledge_type,
                "definition": definition,
                "scope": scope,
                "created_at": now,
                "updated_at": now,
            },
        )
        await self.db.commit()
        return knowledge_id

    async def append_business_knowledge_to_understanding(
        self,
        table_name: str,
        line: str,
    ) -> None:
        """Append confirmed builder knowledge to the sheet understanding markdown."""
        understanding = await self.get_understanding_content(table_name)
        current = (understanding or {}).get("content") or ""
        title = "## 七 业务知识及用户偏好（重要）"
        item = f"- {line.strip()}"
        if not current.strip():
            next_content = f"{title}\n\n{item}\n"
        elif title in current:
            next_content = current.rstrip() + f"\n{item}\n"
        else:
            next_content = current.rstrip() + f"\n\n{title}\n\n{item}\n"
        await self.update_understanding_content(
            table_name,
            next_content,
            verification_status=(understanding or {}).get("verification_status") or "idle",
        )

    async def list_user_preferences(
        self,
        space_id: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: str = "bi_builder",
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM bi_user_preferences
            WHERE scope = :scope AND status = 'active'
        """
        params: Dict[str, Any] = {"scope": scope}
        if space_id:
            sql += " AND (space_id = :space_id OR space_id IS NULL)"
            params["space_id"] = space_id
        if user_id:
            sql += " AND (user_id = :user_id OR user_id IS NULL)"
            params["user_id"] = user_id
        result = await self.db.execute(text(sql), params)
        rows = []
        for row in result.fetchall():
            item = dict(row._mapping)
            raw = item.get("preference_value")
            if isinstance(raw, str):
                try:
                    item["preference_value"] = json.loads(raw)
                except json.JSONDecodeError:
                    pass
            rows.append(item)
        return rows

    async def save_user_preference(
        self,
        preference_key: str,
        preference_value: Any,
        space_id: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: str = "bi_builder",
    ) -> str:
        preference_id = str(uuid.uuid4())
        now = datetime.utcnow()
        await self.db.execute(
            text("""
                INSERT INTO bi_user_preferences
                (id, user_id, space_id, scope, preference_key, preference_value, status, created_at, updated_at)
                VALUES
                (:id, :user_id, :space_id, :scope, :preference_key, :preference_value, 'active', :created_at, :updated_at)
            """),
            {
                "id": preference_id,
                "user_id": user_id,
                "space_id": space_id,
                "scope": scope,
                "preference_key": preference_key,
                "preference_value": json.dumps(
                    preference_value, ensure_ascii=False, default=json_default
                ),
                "created_at": now,
                "updated_at": now,
            },
        )
        await self.db.commit()
        return preference_id
