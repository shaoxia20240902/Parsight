import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import SAMPLE_FIRST_N, SAMPLE_RANDOM_N, RELATIONS_RANDOM_SAMPLE_N
from app.models.file_record import FileRecord
from app.models.sheet_meta import SheetMeta


def _json_default(value: Any):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _normalize_columns(columns_data: Any) -> List[Dict[str, Any]]:
    """将 columns 数据规范化为统一的 List[Dict] 格式。

    兼容两种存储格式：
    - List[Dict]: [{"name": "col1", "type": "text"}, ...]  （正确格式）
    - List[str]:   ["col1", "col2", ...]                     （旧格式/异常数据）
    """
    if not columns_data:
        return []
    if isinstance(columns_data, str):
        columns_data = json.loads(columns_data)
    if not isinstance(columns_data, list):
        return []
    normalized = []
    for c in columns_data:
        if isinstance(c, dict):
            normalized.append(c)
        elif isinstance(c, str):
            normalized.append({"name": c, "type": "text"})
    return normalized


def _qi(name: str) -> str:
    return f"`{str(name).replace('`', '')}`"


class DBService:
    """数据库服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_next_space_seq_id(self) -> int:
        """分配下一个空间自增序号（全局唯一）"""
        result = await self.db.execute(
            text("SELECT COALESCE(MAX(seq_id), 0) + 1 FROM spaces")
        )
        return int(result.scalar() or 1)

    async def get_space_seq_id_for_user(
        self, space_id: str, owner_id: str
    ) -> Optional[int]:
        """获取空间 seq_id，并校验归属"""
        result = await self.db.execute(
            text(
                "SELECT seq_id FROM spaces WHERE id = :space_id AND owner_id = :owner_id"
            ),
            {"space_id": space_id, "owner_id": owner_id},
        )
        row = result.fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0])

    async def create_file_record(self, filename: str, sheet_count: int, space_id: str = None) -> FileRecord:
        """创建文件记录"""
        record = FileRecord(
            id=str(uuid.uuid4()),
            filename=filename,
            sheet_count=sheet_count,
            status="uploaded",
            space_id=space_id
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def update_file_status(self, file_id: str, status: str):
        """更新文件状态"""
        result = await self.db.execute(
            text("UPDATE file_records SET status = :status WHERE id = :id"),
            {"status": status, "id": file_id}
        )
        await self.db.commit()

    async def create_sheet_meta(self, file_id: str, sheet_data: Dict[str, Any]) -> SheetMeta:
        """创建Sheet元数据"""
        meta = SheetMeta(
            id=str(uuid.uuid4()),
            file_id=file_id,
            sheet_index=sheet_data["index"],
            sheet_name=sheet_data["name"],
            columns=json.dumps(sheet_data["columns"], ensure_ascii=False),
            row_count=sheet_data["row_count"],
            table_name=sheet_data["table_name"]
        )
        self.db.add(meta)
        await self.db.commit()
        await self.db.refresh(meta)
        return meta

    async def update_sheet_summary(self, sheet_id: str, summary_data: Dict[str, Any]):
        """更新Sheet的AI总结"""
        result = await self.db.execute(
            text("""
                UPDATE sheet_meta
                SET summary = :summary,
                    key_dimensions = :key_dimensions,
                    key_metrics = :key_metrics,
                    data_granularity = :data_granularity,
                    time_range = :time_range,
                    notable_patterns = :notable_patterns
                WHERE id = :id
            """),
            {
                "id": sheet_id,
                "summary": summary_data.get("summary"),
                "key_dimensions": json.dumps(summary_data.get("key_dimensions", []), ensure_ascii=False),
                "key_metrics": json.dumps(summary_data.get("key_metrics", []), ensure_ascii=False),
                "data_granularity": summary_data.get("data_granularity"),
                "time_range": summary_data.get("time_range"),
                "notable_patterns": json.dumps(summary_data.get("notable_patterns", []), ensure_ascii=False)
            }
        )
        await self.db.commit()

    async def get_file_record(self, file_id: str) -> Optional[FileRecord]:
        """获取文件记录"""
        result = await self.db.execute(
            text("SELECT * FROM file_records WHERE id = :id"),
            {"id": file_id}
        )
        row = result.first()
        if row:
            return FileRecord(**row._mapping)
        return None

    async def get_sheet_metas(self, file_id: str) -> List[SheetMeta]:
        """获取文件的所有Sheet元数据"""
        result = await self.db.execute(
            text("SELECT * FROM sheet_meta WHERE file_id = :file_id ORDER BY sheet_index"),
            {"file_id": file_id}
        )
        rows = result.fetchall()
        return [SheetMeta(**row._mapping) for row in rows]

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """执行SQL查询"""
        # 清理 SQL 语句
        sql = sql.strip()

        try:
            result = await self.db.execute(text(sql))
            columns = result.keys()
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"SQL执行失败: {sql}")
            print(f"错误: {str(e)}")
            raise

    async def create_dynamic_table(self, table_name: str, create_sql: str):
        """创建动态表"""
        await self.db.execute(text(create_sql))
        await self.db.commit()

    async def insert_data(self, insert_sql: str, values: List[tuple]):
        """批量插入数据"""
        # MySQL 批量插入 - 使用参数字典格式
        for value in values:
            # 将元组转换为字典格式
            params = {f"param{i}": v for i, v in enumerate(value)}
            # 修改SQL使用命名参数
            named_sql = insert_sql
            for i in range(len(value)):
                named_sql = named_sql.replace("?", f":param{i}", 1)
            await self.db.execute(text(named_sql), params)
        await self.db.commit()

    async def get_latest_file_record(self, space_id: str) -> Optional[Dict[str, Any]]:
        """获取空间内最近一次上传的文件记录"""
        result = await self.db.execute(
            text("""
                SELECT * FROM file_records
                WHERE space_id = :space_id
                ORDER BY upload_time DESC
                LIMIT 1
            """),
            {"space_id": space_id},
        )
        row = result.first()
        return dict(row._mapping) if row else None

    async def clear_table_data(self, table_name: str):
        """清空动态表数据（保留表结构）"""
        await self.db.execute(text(f'DELETE FROM "{table_name}"'))
        await self.db.commit()

    async def update_sheet_row_count(self, table_name: str, row_count: int):
        """更新 sheet_meta 行数"""
        await self.db.execute(
            text("UPDATE sheet_meta SET row_count = :row_count WHERE table_name = :table_name"),
            {"table_name": table_name, "row_count": row_count},
        )
        await self.db.commit()

    async def update_file_filename(self, file_id: str, filename: str):
        """更新文件记录的文件名"""
        await self.db.execute(
            text("UPDATE file_records SET filename = :filename WHERE id = :id"),
            {"id": file_id, "filename": filename},
        )
        await self.db.commit()

    async def fetch_all_table_rows(self, table_name: str) -> List[Dict[str, Any]]:
        """读取动态表全部行（用于导出）"""
        result = await self.db.execute(text(f'SELECT * FROM "{table_name}"'))
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
            {"space_id": space_id}
        )
        rows = result.fetchall()
        tables = []
        for row in rows:
            m = row._mapping
            columns_data = m.get("columns")
            if isinstance(columns_data, str):
                columns_data = json.loads(columns_data)
            columns_data = _normalize_columns(columns_data)
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
            {"table_name": table_name}
        )
        row = result.first()
        if not row:
            return []
        m = row._mapping
        columns_data = m.get("columns")
        if isinstance(columns_data, str):
            columns_data = json.loads(columns_data)
        return _normalize_columns(columns_data)

    async def get_table_row_count(self, table_name: str) -> int:
        """获取表行数"""
        try:
            result = await self.db.execute(
                text(f"SELECT COUNT(*) as cnt FROM {_qi(table_name)}")
            )
            row = result.first()
            return row._mapping["cnt"] if row else 0
        except Exception:
            return 0

    async def update_bi_config(self, file_id: str, bi_config: Dict[str, Any]):
        """更新 BI 看板配置"""
        result = await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_config = :bi_config
                WHERE id = :id
            """),
            {
                "id": file_id,
                "bi_config": json.dumps(bi_config, ensure_ascii=False, default=_json_default),
            }
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
                "journal": json.dumps(current, ensure_ascii=False, default=_json_default),
            },
        )
        await self.db.commit()

    async def set_bi_thinking_journal(self, file_id: str, entries: List[Dict[str, Any]]) -> None:
        await self.db.execute(
            text("""
                UPDATE file_records
                SET bi_thinking_journal = :journal
                WHERE id = :id
            """),
            {
                "id": file_id,
                "journal": json.dumps(entries, ensure_ascii=False, default=_json_default),
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
            {"id": file_id}
        )
        row = result.first()
        if row:
            raw = row._mapping.get("bi_config")
            if raw:
                return json.loads(raw) if isinstance(raw, str) else raw
        return None

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
        params: Dict[str, Any] = {"id": session_id, "updated_at": datetime.utcnow()}
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
                params[key] = json.dumps(value if value is not None else ([] if key != "scope_plan" else {}), ensure_ascii=False, default=_json_default)
            else:
                params[key] = value
        await self.db.execute(
            text(f"UPDATE bi_builder_sessions SET {', '.join(assignments)} WHERE id = :id"),
            params,
        )
        await self.db.commit()

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
                "preference_value": json.dumps(preference_value, ensure_ascii=False, default=_json_default),
                "created_at": now,
                "updated_at": now,
            },
        )
        await self.db.commit()
        return preference_id

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
            print(f"SQL执行失败: {sql}")
            print(f"参数: {params}")
            print(f"错误: {str(e)}")
            raise

    async def get_sheet_meta_by_table(self, table_name: str) -> Optional[Dict]:
        """根据表名获取 sheet 元数据"""
        result = await self.db.execute(
            text("SELECT * FROM sheet_meta WHERE table_name = :table_name"),
            {"table_name": table_name}
        )
        row = result.first()
        if row:
            return dict(row._mapping)
        return None

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
            f"SELECT DISTINCT {_qi(field_name)} AS val FROM {_qi(table_name)} "
            f"WHERE {_qi(field_name)} IS NOT NULL LIMIT :limit"
        )
        result = await self.db.execute(text(sql), {"limit": limit})
        return [self._serialize_cell(row._mapping["val"]) for row in result.fetchall()]

    async def fetch_sample_rows_from_table(self, table_name: str) -> Dict[str, Any]:
        """从动态表采样：前 N 条 + 随机 M 条（与导入时 DataSampler 策略一致）"""
        first_n = SAMPLE_FIRST_N
        random_n = SAMPLE_RANDOM_N

        first_result = await self.db.execute(
            text(f"SELECT * FROM {_qi(table_name)} LIMIT :limit"),
            {"limit": first_n},
        )
        first_rows = [
            {k: self._serialize_cell(v) for k, v in dict(zip(first_result.keys(), row)).items()}
            for row in first_result.fetchall()
        ]

        total = await self.get_table_row_count(table_name)
        random_rows: List[Dict[str, Any]] = []
        if total > first_n:
            remaining = total - first_n
            sample_size = min(random_n, remaining)
            random_result = await self.db.execute(
                text(
                    f"SELECT * FROM {_qi(table_name)} "
                    f"ORDER BY RAND() LIMIT :limit OFFSET :offset"
                ),
                {"limit": sample_size, "offset": first_n},
            )
            random_rows = [
                {k: self._serialize_cell(v) for k, v in dict(zip(random_result.keys(), row)).items()}
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
            text(f"SELECT * FROM {_qi(table_name)} ORDER BY RAND() LIMIT :limit"),
            {"limit": sample_size},
        )
        return [
            {k: self._serialize_cell(v) for k, v in dict(zip(result.keys(), row)).items()}
            for row in result.fetchall()
        ]

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
        updated_str = updated.isoformat() if updated and hasattr(updated, "isoformat") else (
            str(updated) if updated else None
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
            FROM {_qi(from_table)} a
            INNER JOIN {_qi(to_table)} b ON a.{_qi(from_field)} = b.{_qi(to_field)}
        '''
        join_result = await self.db.execute(text(join_sql))
        match_rows = join_result.first()._mapping["match_rows"]

        from_total_sql = f"SELECT COUNT(*) AS cnt FROM {_qi(from_table)} WHERE {_qi(from_field)} IS NOT NULL"
        from_total = (await self.db.execute(text(from_total_sql))).first()._mapping["cnt"]

        overlap_sql = f'''
            SELECT COUNT(DISTINCT a.{_qi(from_field)}) AS overlap_count
            FROM {_qi(from_table)} a
            WHERE a.{_qi(from_field)} IS NOT NULL
              AND a.{_qi(from_field)} IN (
                SELECT DISTINCT b.{_qi(to_field)} FROM {_qi(to_table)} b
                WHERE b.{_qi(to_field)} IS NOT NULL
              )
        '''
        overlap_count = (await self.db.execute(text(overlap_sql))).first()._mapping["overlap_count"]

        sample_sql = f'''
            SELECT DISTINCT a.{_qi(from_field)} AS val
            FROM {_qi(from_table)} a
            WHERE a.{_qi(from_field)} IS NOT NULL
              AND a.{_qi(from_field)} IN (
                SELECT DISTINCT b.{_qi(to_field)} FROM {_qi(to_table)} b
                WHERE b.{_qi(to_field)} IS NOT NULL
              )
            LIMIT 20
        '''
        sample_result = await self.db.execute(text(sample_sql))
        overlap_samples = [
            self._serialize_cell(r._mapping["val"]) for r in sample_result.fetchall()
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

    @staticmethod
    def _serialize_cell(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, (datetime,)):
            return val.isoformat()
        return val

    async def paginated_query(
        self,
        table_name: str,
        page: int = 1,
        page_size: int = 20,
        search: str = "",
        search_field: str = ""
    ) -> Dict[str, Any]:
        """分页查询 + 模糊搜索"""
        # 获取列信息用于全字段搜索
        columns_info = await self.get_table_columns(table_name)
        all_cols = [c["name"] for c in columns_info] if columns_info else []

        # 安全校验：列名不得包含反引号（防止 SQL 注入）
        safe_cols = [c for c in all_cols if "`" not in c]

        # 构建 WHERE 子句
        where_clause = ""
        params = {}
        if search:
            if search_field and search_field in safe_cols:
                # 指定字段搜索
                where_clause = f"WHERE {_qi(search_field)} LIKE :search"
                params["search"] = f"%{search}%"
            elif safe_cols:
                # 全字段搜索
                conditions = [f"{_qi(c)} LIKE :search" for c in safe_cols]
                where_clause = "WHERE " + " OR ".join(conditions)
                params["search"] = f"%{search}%"

        # 计算总数
        count_sql = f"SELECT COUNT(*) as cnt FROM {_qi(table_name)} {where_clause}"
        count_result = await self.db.execute(text(count_sql), params)
        total = count_result.first()._mapping["cnt"]

        # 分页查询
        offset = (page - 1) * page_size
        data_sql = f"SELECT * FROM {_qi(table_name)} {where_clause} LIMIT :limit OFFSET :offset"
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
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
        }
