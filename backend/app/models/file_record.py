import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Index
from sqlalchemy import JSON
from .database import Base


class FileRecord(Base):
    __tablename__ = "file_records"
    __table_args__ = (
        Index("idx_file_records_space_upload", "space_id", "upload_time"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow)
    sheet_count = Column(Integer)
    status = Column(String(20), default="uploaded")  # uploaded/analyzing/analyzed/error
    space_id = Column(String(36), nullable=True)
    bi_config = Column(JSON)  # BI看板配置（分类+图表列表）
    bi_thinking_journal = Column(JSON)  # BI 生成思考过程（自然语言条目列表）
