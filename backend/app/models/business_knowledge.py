import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from .database import Base


class BusinessKnowledge(Base):
    __tablename__ = "bi_business_knowledge"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), nullable=False, index=True)
    table_name = Column(String(255), nullable=True, index=True)
    term = Column(String(255), nullable=False)
    canonical = Column(String(255), nullable=False)
    knowledge_type = Column(String(64), nullable=False, default="alias")
    definition = Column(Text, nullable=True)
    scope = Column(String(64), nullable=False, default="file")
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
