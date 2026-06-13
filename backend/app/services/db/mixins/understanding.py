from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text


class UnderstandingMixin:
    async def get_understanding_content(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取已保存的表理解 Markdown 及核对状态"""
        result = await self.db.execute(
            text("""
                SELECT understanding_content, understanding_content_initial,
                       understanding_updated_at, understanding_verification_status
                FROM sheet_meta WHERE table_name = :table_name
            """),
            {"table_name": table_name},
        )
        row = result.first()
        if not row:
            return None
        m = row._mapping
        content = m.get("understanding_content") or m.get("understanding_content_initial")
        if not content:
            return None
        updated = m.get("understanding_updated_at")
        updated_str = None
        if updated:
            updated_str = (
                updated.isoformat()
                if hasattr(updated, "isoformat")
                else str(updated)
            )
        return {
            "content": content,
            "content_initial": m.get("understanding_content_initial"),
            "updated_at": updated_str,
            "verification_status": m.get("understanding_verification_status") or "idle",
        }

    async def save_understanding_draft(
        self, table_name: str, content: str, verification_status: str = "verifying"
    ) -> str:
        """保存表理解初稿（初稿与当前展示内容相同）"""
        now = datetime.utcnow()
        await self.db.execute(
            text("""
                UPDATE sheet_meta
                SET understanding_content = :content,
                    understanding_content_initial = :content,
                    understanding_updated_at = :updated_at,
                    understanding_verification_status = :status
                WHERE table_name = :table_name
            """),
            {
                "table_name": table_name,
                "content": content,
                "updated_at": now,
                "status": verification_status,
            },
        )
        await self.db.commit()
        return now.isoformat()

    async def save_understanding_verified(
        self, table_name: str, content: str, verification_status: str = "completed"
    ) -> str:
        """保存核对后的终稿（保留 understanding_content_initial 供对比）"""
        now = datetime.utcnow()
        await self.db.execute(
            text("""
                UPDATE sheet_meta
                SET understanding_content = :content,
                    understanding_updated_at = :updated_at,
                    understanding_verification_status = :status
                WHERE table_name = :table_name
            """),
            {
                "table_name": table_name,
                "content": content,
                "updated_at": now,
                "status": verification_status,
            },
        )
        await self.db.commit()
        return now.isoformat()

    async def update_understanding_content(
        self,
        table_name: str,
        content: str,
        verification_status: Optional[str] = None,
    ) -> str:
        """用户手动保存（同时更新终稿，不保留核对流程）"""
        now = datetime.utcnow()
        status = verification_status if verification_status is not None else "idle"
        await self.db.execute(
            text("""
                UPDATE sheet_meta
                SET understanding_content = :content,
                    understanding_updated_at = :updated_at,
                    understanding_verification_status = :status
                WHERE table_name = :table_name
            """),
            {
                "table_name": table_name,
                "content": content,
                "updated_at": now,
                "status": status,
            },
        )
        await self.db.commit()
        return now.isoformat()

    async def set_understanding_verification_status(
        self, table_name: str, status: str
    ) -> None:
        await self.db.execute(
            text("""
                UPDATE sheet_meta
                SET understanding_verification_status = :status
                WHERE table_name = :table_name
            """),
            {"table_name": table_name, "status": status},
        )
        await self.db.commit()
