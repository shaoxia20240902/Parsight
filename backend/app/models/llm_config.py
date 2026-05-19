from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean
from app.models.database import Base


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    api_base = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False)
    primary_model = Column(String(100), nullable=False)
    alt_model = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
