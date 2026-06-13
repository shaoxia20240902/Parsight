import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.config import RELATIONS_RANDOM_SAMPLE_N, SAMPLE_FIRST_N, SAMPLE_RANDOM_N
from app.services.db.utils import (
    json_safe,
    normalize_columns,
    quote_identifier,
    serialize_cell,
)

logger = logging.getLogger(__name__)


class TableMixin:
    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """执行SQL查询"""
        sql = sql.strip()
        try:
            result = await self.db.execute(text(sql))
            columns = result.keys()
            rows = result.fetchall()
            return [json_safe(dict(zip(columns, row))) for row in rows]
        except Exception as e:
            logger.error("SQL执行失败: %s", sql)
            logger.error("错误: %s", str(e))
            raise

    async def create_dynamic_table(self, table_name: str, create_sql: str):
        """创建动态表"""
        await self.db.execute(text(create_sql))
        await self.db.commit()

    async def insert_data(self, insert_sql: str, values: List[tuple]):
        """批量插入数据"""
        for value in values:
            params = {f"param{i}": v for i, v in enumerate(value)}
            named_sql = insert_sql
            for i in range(len(value)):
                named_sql = named_sql.replace("?", f":param{i}", 1)
            await self.db.execute(text(named_sql), params)
        await self.db.commit()

    async def clear_table_data(self, table_name: str):
        """清空动态表数据（保留表结构）"""
        await self.db.execute(text(f"DELETE FROM `{table_name}`"))
        await self.db.commit()

    async def update_sheet_row_count(self, table_name: str, row_count: int):
        """更新 sheet_meta 行数"""
        await self.db.execute(
            text(
                "UPDATE sheet_meta SET row_count = :row_count WHERE table_name = :table_name"
            ),
            {"table_name": table_name, "row_count": row_count},
        )
        await self.db.commit()

    async def fetch_all_table_rows(self, table_name: str) -> List[Dict[str, Any]]:
        """读取动态表全部行（用于导出）"""
        result = await self.db.execute(text(f"SELECT * FROM `{table_name}`"))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]

    async def get_tables_by_space(self, space_id: str) -> List[Dict[str, Any]]:
        """获取空间下所有动态表（通过 sheet_meta 关联 file_record 查询）"""
        result = await self.db.execute(
            text("""
                SELECT sm.* FROM sheet_meta sm
                INNER JOIN file_records fr ON sm.file_id = fr.id
                WHERE fr.space_id = :space_id
                ORDER BY sm.sheet_index
            """),
            {"space_id": space_id},
        )
        rows = result.fetchall()
        tables = []
        for row in rows:
            m = row._mapping
            columns_data = m.get("columns")
            if isinstance(columns_data, str):
                columns_data = json.loads(columns_data)
            columns_data = normalize_columns(columns_data)
            tables.append({
                "table_name": m.get("table_name"),
                "sheet_name": m.get("sheet_name"),
                "sheet_index": m.get("sheet_index"),
                "row_count": m.get("row_count"),
                "columns": columns_data,
                "file_id": m.get("file_id"),
                "summary": m.get("summary"),
            })
        return tables

    async def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的所有列信息"""
        result = await self.db.execute(
            text("SELECT * FROM sheet_meta WHERE table_name = :table_name"),
            {"table_name": table_name},
        )
        row = result.first()
        if not row:
            return []
        m = row._mapping
        columns_data = m.get("columns")
        if isinstance(columns_data, str):
            columns_data = json.loads(columns_data)
        return normalize_columns(columns_data)

    async def get_table_row_count(self, table_name: str) -> int:
        """获取表行数"""
        try:
            result = await self.db.execute(
                text(f"SELECT COUNT(*) as cnt FROM {quote_identifier(table_name)}")
            )
            row = result.first()
            return row._mapping["cnt"] if row else 0
        except Exception:
            return 0

    async def execute_query_with_params(
        self, sql: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行带参数的 SQL 查询（防注入）"""
        sql = sql.strip()
        try:
            if params:
                result = await self.db.execute(text(sql), params)
            else:
                result = await self.db.execute(text(sql))
            columns = result.keys()
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error("SQL执行失败: %s", sql)
            logger.error("参数: %s", params)
            logger.error("错误: %s", str(e))
            raise

    async def fetch_distinct_field_values(
        self,
        table_name: str,
        field_name: str,
        allowed_columns: List[str],
        limit: int = 500,
    ) -> List[Any]:
        """对指定字段执行去重查询（字段名必须在白名单内）"""
        if field_name not in allowed_columns:
            raise ValueError(f"非法字段名: {field_name}")
        if '"' in table_name or '"' in field_name:
            raise ValueError("表名或字段名包含非法字符")

        sql = (
            f"SELECT DISTINCT {quote_identifier(field_name)} AS val FROM {quote_identifier(table_name)} "
            f"WHERE {quote_identifier(field_name)} IS NOT NULL LIMIT :limit"
        )
        result = await self.db.execute(text(sql), {"limit": limit})
        return [serialize_cell(row._mapping["val"]) for row in result.fetchall()]

    async def fetch_sample_rows_from_table(self, table_name: str) -> Dict[str, Any]:
        """从动态表采样：前 N 条 + 随机 M 条（与导入时 DataSampler 策略一致）"""
        first_n = SAMPLE_FIRST_N
        random_n = SAMPLE_RANDOM_N

        first_result = await self.db.execute(
            text(f"SELECT * FROM {quote_identifier(table_name)} LIMIT :limit"),
            {"limit": first_n},
        )
        first_rows = [
            {k: serialize_cell(v) for k, v in dict(zip(first_result.keys(), row)).items()}
            for row in first_result.fetchall()
        ]

        total = await self.get_table_row_count(table_name)
        random_rows: List[Dict[str, Any]] = []
        if total > first_n:
            remaining = total - first_n
            sample_size = min(random_n, remaining)
            random_result = await self.db.execute(
                text(
                    f"SELECT * FROM {quote_identifier(table_name)} "
                    f"ORDER BY RAND() LIMIT :limit OFFSET :offset"
                ),
                {"limit": sample_size, "offset": first_n},
            )
            random_rows = [
                {k: serialize_cell(v) for k, v in dict(zip(random_result.keys(), row)).items()}
                for row in random_result.fetchall()
            ]

        return {
            "rows": first_rows + random_rows,
            "first_n_count": len(first_rows),
            "random_n_count": len(random_rows),
        }

    async def fetch_random_rows_from_table(
        self, table_name: str, limit: int = None
    ) -> List[Dict[str, Any]]:
        """随机采样 N 行（用于关联分析）"""
        if limit is None:
            limit = RELATIONS_RANDOM_SAMPLE_N
        total = await self.get_table_row_count(table_name)
        if total == 0:
            return []
        sample_size = min(limit, total)
        result = await self.db.execute(
            text(
                f"SELECT * FROM {quote_identifier(table_name)} ORDER BY RAND() LIMIT :limit"
            ),
            {"limit": sample_size},
        )
        return [
            {k: serialize_cell(v) for k, v in dict(zip(result.keys(), row)).items()}
            for row in result.fetchall()
        ]

    async def paginated_query(
        self,
        table_name: str,
        page: int = 1,
        page_size: int = 20,
        search: str = "",
        search_field: str = "",
    ) -> Dict[str, Any]:
        """分页查询 + 模糊搜索"""
        columns_info = await self.get_table_columns(table_name)
        all_cols = [c["name"] for c in columns_info] if columns_info else []
        safe_cols = [c for c in all_cols if "`" not in c]

        where_clause = ""
        params = {}
        if search:
            if search_field and search_field in safe_cols:
                where_clause = f"WHERE {quote_identifier(search_field)} LIKE :search"
                params["search"] = f"%{search}%"
            elif safe_cols:
                conditions = [
                    f"{quote_identifier(c)} LIKE :search" for c in safe_cols
                ]
                where_clause = "WHERE " + " OR ".join(conditions)
                params["search"] = f"%{search}%"

        count_sql = f"SELECT COUNT(*) as cnt FROM {quote_identifier(table_name)} {where_clause}"
        count_result = await self.db.execute(text(count_sql), params)
        total = count_result.first()._mapping["cnt"]

        offset = (page - 1) * page_size
        data_sql = f"SELECT * FROM {quote_identifier(table_name)} {where_clause} LIMIT :limit OFFSET :offset"
        params["limit"] = page_size
        params["offset"] = offset
        data_result = await self.db.execute(text(data_sql), params)
        columns = data_result.keys()
        rows = data_result.fetchall()
        data = [dict(zip(columns, row)) for row in rows]

        return {
            "rows": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
            if page_size > 0
            else 0,
        }
