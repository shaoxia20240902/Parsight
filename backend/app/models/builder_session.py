import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String

from .database import Base


class BuilderSession(Base):
    __tablename__ = "bi_builder_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), nullable=False, index=True)
    space_id = Column(String(36), nullable=True, index=True)
    state = Column(String(64), nullable=False, default="idle")
    base_chart_id = Column(String(128), nullable=True)
    context_chart_id = Column(String(128), nullable=True)
    scope_plan = Column(JSON, nullable=True)
    chart_list = Column(JSON, nullable=True)
    pending_input_ui = Column(JSON, nullable=True)
    created_chart_ids = Column(JSON, nullable=True)
    knowledge_cards = Column(JSON, nullable=True)
    preference_cards = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
