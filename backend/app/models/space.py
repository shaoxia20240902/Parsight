import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from .database import Base


class Space(Base):
    __tablename__ = "spaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seq_id = Column(Integer, unique=True, nullable=True, index=True)  # 自增序号，用于短表名
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(String(500), default="")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    relations_content = Column(Text)  # 空间级 Sheet 关联分析终稿
    relations_content_initial = Column(Text)  # 核对前初稿
    relations_verification_status = Column(String(20), default="idle")
    relations_updated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
