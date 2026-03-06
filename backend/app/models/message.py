# backend/app/models/message.py
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)

    # Содержание сообщения
    content = Column(Text, nullable=False)

    # Кто отправил: True = от лида, False = от бота
    is_from_lead = Column(Boolean, default=True)

    # Дата создания
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    chat_session = relationship("ChatSession", back_populates="messages")