import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.services.db.utils import json_default, json_safe


class BIMixin:
    async def update_bi_config(self, file_id: str, bi_config: Dict[str, Any]):
        """更新 BI 看板配置"""
        await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_config = :bi_config
                WHERE id = :id
            """),
            {
                "id": file_id,
                "bi_config": json.dumps(
                    json_safe(bi_config), ensure_ascii=False, default=json_default
                ),
            },
        )
        await self.db.commit()

    async def clear_bi_config(self, file_id: str) -> None:
        """清空 BI 看板配置，用于重新生成开始前避免继续展示旧配置。"""
        await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_config = NULL
                WHERE id = :id
            """),
            {"id": file_id},
        )
        await self.db.commit()

    async def clear_bi_thinking_journal(self, file_id: str) -> None:
        await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_thinking_journal = :journal
                WHERE id = :id
            """),
            {"id": file_id, "journal": json.dumps([], ensure_ascii=False)},
        )
        await self.db.commit()

    async def append_bi_thinking_entry(self, file_id: str, entry: Dict[str, Any]) -> None:
        current = await self.get_bi_thinking_journal(file_id)
        current.append(entry)
        await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_thinking_journal = :journal
                WHERE id = :id
            """),
            {
                "id": file_id,
                "journal": json.dumps(current, ensure_ascii=False, default=json_default),
            },
        )
        await self.db.commit()

    async def set_bi_thinking_journal(
        self, file_id: str, entries: List[Dict[str, Any]]
    ) -> None:
        await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_thinking_journal = :journal
                WHERE id = :id
            """),
            {
                "id": file_id,
                "journal": json.dumps(entries, ensure_ascii=False, default=json_default),
            },
        )
        await self.db.commit()

    async def get_bi_thinking_journal(self, file_id: str) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            text("SELECT bi_thinking_journal FROM file_records WHERE id = :id"),
            {"id": file_id},
        )
        row = result.first()
        if not row:
            return []
        raw = row._mapping.get("bi_thinking_journal")
        if not raw:
            return []
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return []
        else:
            data = raw
        return data if isinstance(data, list) else []

    async def get_bi_config(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取 BI 看板配置"""
        result = await self.db.execute(
            text("SELECT bi_config FROM file_records WHERE id = :id"),
            {"id": file_id},
        )
        row = result.first()
        if row:
            raw = row._mapping.get("bi_config")
            if raw:
                return json.loads(raw) if isinstance(raw, str) else raw
        return None

    async def update_bi_status(self, file_id: str, status: str) -> None:
        """更新 BI 生成状态"""
        if status == "generating":
            await self.db.execute(
                text("""
                    UPDATE file_records
                    SET bi_status = :status,
                        bi_generation_started_at = :started_at,
                        bi_generation_finished_at = NULL
                    WHERE id = :id
                """),
                {"id": file_id, "status": status, "started_at": datetime.utcnow()},
            )
        elif status in {"completed", "failed"}:
            await self.db.execute(
                text("""
                    UPDATE file_records
                    SET bi_status = :status,
                        bi_generation_finished_at = :finished_at
                    WHERE id = :id
                """),
                {"id": file_id, "status": status, "finished_at": datetime.utcnow()},
            )
        else:
            await self.db.execute(
                text("UPDATE file_records SET bi_status = :status WHERE id = :id"),
                {"id": file_id, "status": status},
            )
        await self.db.commit()

    async def get_bi_status(self, file_id: str) -> Optional[str]:
        """获取 BI 生成状态"""
        result = await self.db.execute(
            text("SELECT bi_status FROM file_records WHERE id = :id"),
            {"id": file_id},
        )
        row = result.first()
        return row._mapping.get("bi_status") if row else None

    async def get_bi_status_info(self, file_id: str) -> Dict[str, Any]:
        """获取 BI 生成状态与任务时间。"""
        result = await self.db.execute(
            text("""
                SELECT bi_status, bi_generation_started_at, bi_generation_finished_at
                FROM file_records
                WHERE id = :id
            """),
            {"id": file_id},
        )
        row = result.first()
        if not row:
            return {}
        data = dict(row._mapping)
        return {
            "status": data.get("bi_status"),
            "generation_started_at": data.get("bi_generation_started_at"),
            "generation_finished_at": data.get("bi_generation_finished_at"),
        }

    async def ensure_bi_generation_started_at(self, file_id: str) -> Optional[datetime]:
        """为旧的 generating 任务补齐开始时间，只在缺失时写一次。"""
        started_at = datetime.utcnow()
        await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_generation_started_at = :started_at
                WHERE id = :id
                  AND bi_status = 'generating'
                  AND bi_generation_started_at IS NULL
            """),
            {"id": file_id, "started_at": started_at},
        )
        await self.db.commit()
        info = await self.get_bi_status_info(file_id)
        return info.get("generation_started_at")

    async def save_recommended_questions(
        self, file_id: str, questions: Dict[str, Any], status: str = "completed"
    ) -> None:
        """保存对话推荐问题"""
        await self.db.execute(
            text("""
                UPDATE file_records
                SET recommended_questions = :questions,
                    recommended_questions_status = :status
                WHERE id = :id
            """),
            {
                "id": file_id,
                "questions": json.dumps(questions, ensure_ascii=False),
                "status": status,
            },
        )
        await self.db.commit()

    async def get_recommended_questions(self, file_id: str) -> Dict[str, Any]:
        """获取对话推荐问题"""
        result = await self.db.execute(
            text("""
                SELECT recommended_questions, recommended_questions_status
                FROM file_records WHERE id = :id
            """),
            {"id": file_id},
        )
        row = result.first()
        if not row:
            return {"questions": None, "status": "idle"}
        raw = row._mapping.get("recommended_questions")
        status = row._mapping.get("recommended_questions_status") or "idle"
        if not raw:
            return {"questions": None, "status": status}
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return {"questions": None, "status": status}
        else:
            data = raw
        return {"questions": data, "status": status}

    async def get_builder_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        result = await self.db.execute(
            text("SELECT * FROM bi_builder_sessions WHERE id = :id"),
            {"id": session_id},
        )
        row = result.first()
        return dict(row._mapping) if row else None

    async def create_builder_session(
        self,
        session_id: str,
        file_id: str,
        space_id: Optional[str],
        state: str = "idle",
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        await self.db.execute(
            text("""
                INSERT INTO bi_builder_sessions
                (id, file_id, space_id, state, scope_plan, chart_list, pending_input_ui,
                 created_chart_ids, knowledge_cards, preference_cards, created_at, updated_at)
                VALUES
                (:id, :file_id, :space_id, :state, :scope_plan, :chart_list, :pending_input_ui,
                 :created_chart_ids, :knowledge_cards, :preference_cards, :created_at, :updated_at)
            """),
            {
                "id": session_id,
                "file_id": file_id,
                "space_id": space_id,
                "state": state,
                "scope_plan": json.dumps({}, ensure_ascii=False),
                "chart_list": json.dumps([], ensure_ascii=False),
                "pending_input_ui": json.dumps({}, ensure_ascii=False),
                "created_chart_ids": json.dumps([], ensure_ascii=False),
                "knowledge_cards": json.dumps([], ensure_ascii=False),
                "preference_cards": json.dumps([], ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
            },
        )
        await self.db.commit()
        return await self.get_builder_session(session_id) or {}

    async def update_builder_session(self, session_id: str, **fields: Any) -> None:
        allowed = {
            "state",
            "base_chart_id",
            "context_chart_id",
            "scope_plan",
            "chart_list",
            "pending_input_ui",
            "created_chart_ids",
            "knowledge_cards",
            "preference_cards",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        params: Dict[str, Any] = {
            "id": session_id,
            "updated_at": datetime.utcnow(),
        }
        assignments = ["updated_at = :updated_at"]
        json_fields = {
            "scope_plan",
            "chart_list",
            "pending_input_ui",
            "created_chart_ids",
            "knowledge_cards",
            "preference_cards",
        }
        for key, value in updates.items():
            assignments.append(f"{key} = :{key}")
            if key in json_fields:
                params[key] = json.dumps(
                    value if value is not None else ([] if key != "scope_plan" else {}),
                    ensure_ascii=False,
                    default=json_default,
                )
            else:
                params[key] = value
        await self.db.execute(
            text(
                f"UPDATE bi_builder_sessions SET {', '.join(assignments)} WHERE id = :id"
            ),
            params,
        )
        await self.db.commit()
