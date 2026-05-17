import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String

from .database import Base


class UserPreference(Base):
    __tablename__ = "bi_user_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    space_id = Column(String(36), nullable=True, index=True)
    scope = Column(String(64), nullable=False, default="bi_builder")
    preference_key = Column(String(255), nullable=False)
    preference_value = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
