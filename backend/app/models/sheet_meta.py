import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy import JSON
from .database import Base


class SheetMeta(Base):
    __tablename__ = "sheet_meta"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), ForeignKey("file_records.id"), nullable=False)
    sheet_index = Column(Integer, nullable=False)
    sheet_name = Column(String(255))
    columns = Column(JSON)  # [{name, type, unique_count, sample_values}]
    row_count = Column(Integer)
    table_name = Column(String(255), unique=True)
    summary = Column(Text)
    key_dimensions = Column(JSON)
    key_metrics = Column(JSON)
    data_granularity = Column(String(100))
    time_range = Column(String(100))
    notable_patterns = Column(JSON)
    understanding_content = Column(Text)  # AI 六维理解终稿（Markdown）
    understanding_content_initial = Column(Text)  # 核对前初稿（用于对比）
    understanding_updated_at = Column(DateTime)
    understanding_verification_status = Column(String(20), default="idle")  # idle/verifying/completed/failed
    created_at = Column(DateTime, default=datetime.utcnow)
