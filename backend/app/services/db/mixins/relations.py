from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.services.db.utils import quote_identifier, serialize_cell


class RelationsMixin:
    async def build_space_relations_context(self, space_id: str) -> List[Dict[str, Any]]:
        """构建空间关联分析输入：每表随机样本 + 单表理解"""
        tables = await self.get_tables_by_space(space_id)
        if not tables:
            return []
        sheets_ctx = []
        for t in tables:
            table_name = t["table_name"]
            understanding = await self.get_understanding_content(table_name)
            understanding_md = ""
            if understanding and understanding.get("content"):
                understanding_md = understanding["content"]
            else:
                meta = await self.get_sheet_meta_by_table(table_name)
                understanding_md = (meta or {}).get("summary") or ""
            if not understanding_md:
                raise ValueError(
                    f"表「{t.get('sheet_name', table_name)}」缺少单表理解，请先在「理解内容」中生成"
                )
            random_rows = await self.fetch_random_rows_from_table(table_name)
            columns = await self.get_table_columns(table_name)
            sheets_ctx.append({
                "sheet_name": t.get("sheet_name", table_name),
                "table_name": table_name,
                "row_count": t.get("row_count", 0),
                "columns": columns,
                "understanding": understanding_md,
                "sample_rows": random_rows,
            })
        return sheets_ctx

    async def get_space_relations(self, space_id: str) -> Optional[Dict[str, Any]]:
        result = await self.db.execute(
            text("""
                SELECT relations_content, relations_content_initial,
                       relations_verification_status, relations_updated_at
                FROM spaces WHERE id = :space_id
            """),
            {"space_id": space_id},
        )
        row = result.first()
        if not row:
            return None
        m = row._mapping
        content = m.get("relations_content")
        if not content:
            return None
        updated = m.get("relations_updated_at")
        updated_str = (
            updated.isoformat()
            if updated and hasattr(updated, "isoformat")
            else (str(updated) if updated else None)
        )
        return {
            "content": content,
            "content_initial": m.get("relations_content_initial"),
            "verification_status": m.get("relations_verification_status") or "idle",
            "updated_at": updated_str,
        }

    async def save_space_relations_draft(
        self, space_id: str, content: str, verification_status: str = "verifying"
    ) -> str:
        now = datetime.utcnow()
        await self.db.execute(
            text("""
                UPDATE spaces
                SET relations_content = :content,
                    relations_content_initial = :content,
                    relations_verification_status = :status,
                    relations_updated_at = :updated_at
                WHERE id = :space_id
            """),
            {
                "space_id": space_id,
                "content": content,
                "status": verification_status,
                "updated_at": now,
            },
        )
        await self.db.commit()
        return now.isoformat()

    async def save_space_relations_verified(
        self, space_id: str, content: str, verification_status: str = "completed"
    ) -> str:
        now = datetime.utcnow()
        await self.db.execute(
            text("""
                UPDATE spaces
                SET relations_content = :content,
                    relations_verification_status = :status,
                    relations_updated_at = :updated_at
                WHERE id = :space_id
            """),
            {
                "space_id": space_id,
                "content": content,
                "status": verification_status,
                "updated_at": now,
            },
        )
        await self.db.commit()
        return now.isoformat()

    async def verify_relation_join(
        self,
        from_table: str,
        to_table: str,
        from_field: str,
        to_field: str,
        allowed_from_cols: List[str],
        allowed_to_cols: List[str],
    ) -> Dict[str, Any]:
        """核实两表关联：匹配行数、左表匹配率、取值重叠样本"""
        if from_field not in allowed_from_cols or to_field not in allowed_to_cols:
            raise ValueError("关联字段不在表字段白名单内")
        for name in (from_table, to_table, from_field, to_field):
            if '"' in name:
                raise ValueError("非法标识符")

        join_sql = f'''
            SELECT COUNT(*) AS match_rows
            FROM {quote_identifier(from_table)} a
            INNER JOIN {quote_identifier(to_table)} b ON a.{quote_identifier(from_field)} = b.{quote_identifier(to_field)}
        '''
        join_result = await self.db.execute(text(join_sql))
        match_rows = join_result.first()._mapping["match_rows"]

        from_total_sql = f"SELECT COUNT(*) AS cnt FROM {quote_identifier(from_table)} WHERE {quote_identifier(from_field)} IS NOT NULL"
        from_total = (await self.db.execute(text(from_total_sql))).first()._mapping["cnt"]

        overlap_sql = f'''
            SELECT COUNT(DISTINCT a.{quote_identifier(from_field)}) AS overlap_count
            FROM {quote_identifier(from_table)} a
            WHERE a.{quote_identifier(from_field)} IS NOT NULL
              AND a.{quote_identifier(from_field)} IN (
                SELECT DISTINCT b.{quote_identifier(to_field)} FROM {quote_identifier(to_table)} b
                WHERE b.{quote_identifier(to_field)} IS NOT NULL
              )
        '''
        overlap_count = (await self.db.execute(text(overlap_sql))).first()._mapping["overlap_count"]

        sample_sql = f'''
            SELECT DISTINCT a.{quote_identifier(from_field)} AS val
            FROM {quote_identifier(from_table)} a
            WHERE a.{quote_identifier(from_field)} IS NOT NULL
              AND a.{quote_identifier(from_field)} IN (
                SELECT DISTINCT b.{quote_identifier(to_field)} FROM {quote_identifier(to_table)} b
                WHERE b.{quote_identifier(to_field)} IS NOT NULL
              )
            LIMIT 20
        '''
        sample_result = await self.db.execute(text(sample_sql))
        overlap_samples = [
            serialize_cell(r._mapping["val"]) for r in sample_result.fetchall()
        ]

        return {
            "from_table": from_table,
            "to_table": to_table,
            "from_field": from_field,
            "to_field": to_field,
            "match_rows": int(match_rows),
            "from_field_non_null_rows": int(from_total),
            "overlap_distinct_count": int(overlap_count),
            "overlap_sample_values": overlap_samples,
        }
