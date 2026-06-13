import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.models.file_record import FileRecord
from app.models.sheet_meta import SheetMeta
from app.services.db.utils import json_safe, normalize_columns


class FileMixin:
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

    async def create_file_record(
        self, filename: str, sheet_count: int, space_id: str = None
    ) -> FileRecord:
        """创建文件记录"""
        record = FileRecord(
            id=str(uuid.uuid4()),
            filename=filename,
            sheet_count=sheet_count,
            status="uploaded",
            space_id=space_id,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def update_file_status(self, file_id: str, status: str):
        """更新文件状态"""
        await self.db.execute(
            text("UPDATE file_records SET status = :status WHERE id = :id"),
            {"status": status, "id": file_id},
        )
        await self.db.commit()

    async def create_sheet_meta(
        self, file_id: str, sheet_data: Dict[str, Any]
    ) -> SheetMeta:
        """创建Sheet元数据"""
        meta = SheetMeta(
            id=str(uuid.uuid4()),
            file_id=file_id,
            sheet_index=sheet_data["index"],
            sheet_name=sheet_data["name"],
            columns=json.dumps(sheet_data["columns"], ensure_ascii=False),
            row_count=sheet_data["row_count"],
            table_name=sheet_data["table_name"],
        )
        self.db.add(meta)
        await self.db.commit()
        await self.db.refresh(meta)
        return meta

    async def update_sheet_summary(self, sheet_id: str, summary_data: Dict[str, Any]):
        """更新Sheet的AI总结"""
        await self.db.execute(
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
                "key_dimensions": json.dumps(
                    summary_data.get("key_dimensions", []), ensure_ascii=False
                ),
                "key_metrics": json.dumps(
                    summary_data.get("key_metrics", []), ensure_ascii=False
                ),
                "data_granularity": summary_data.get("data_granularity"),
                "time_range": summary_data.get("time_range"),
                "notable_patterns": json.dumps(
                    summary_data.get("notable_patterns", []), ensure_ascii=False
                ),
            },
        )
        await self.db.commit()

    async def get_file_record(self, file_id: str) -> Optional[FileRecord]:
        """获取文件记录"""
        result = await self.db.execute(
            text("SELECT * FROM file_records WHERE id = :id"),
            {"id": file_id},
        )
        row = result.first()
        if row:
            return FileRecord(**row._mapping)
        return None

    async def get_sheet_metas(self, file_id: str) -> List[SheetMeta]:
        """获取文件的所有Sheet元数据"""
        result = await self.db.execute(
            text(
                "SELECT * FROM sheet_meta WHERE file_id = :file_id ORDER BY sheet_index"
            ),
            {"file_id": file_id},
        )
        rows = result.fetchall()
        return [SheetMeta(**row._mapping) for row in rows]

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

    async def update_file_filename(self, file_id: str, filename: str):
        """更新文件记录的文件名"""
        await self.db.execute(
            text("UPDATE file_records SET filename = :filename WHERE id = :id"),
            {"id": file_id, "filename": filename},
        )
        await self.db.commit()

    async def get_sheet_meta_by_table(self, table_name: str) -> Optional[Dict]:
        """根据表名获取 sheet 元数据"""
        result = await self.db.execute(
            text("SELECT * FROM sheet_meta WHERE table_name = :table_name"),
            {"table_name": table_name},
        )
        row = result.first()
        if row:
            return dict(row._mapping)
        return None
