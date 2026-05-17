import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from .database import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    space_id = Column(String(36), ForeignKey("spaces.id"), nullable=True)
    file_id = Column(String(36), ForeignKey("file_records.id"), nullable=True)
    mode = Column(String(32), nullable=True, default="insight")
    session_id = Column(String(36), nullable=True)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
