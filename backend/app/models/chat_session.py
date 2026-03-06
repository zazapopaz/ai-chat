# backend/app/models/chat_session.py
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)

    # Информация о лиде
    lead_phone = Column(String, nullable=True)
    lead_name = Column(String, nullable=True)
    lead_email = Column(String, nullable=True)

    # Уникальный ID браузера
    client_id = Column(String, nullable=True, index=True)

    # Метаданные
    session_metadata = Column(JSON, default={
        "page_url": "",
        "user_agent": "",
        "ip_address": ""
    })

    # Даты
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Индексы для быстрого поиска
    __table_args__ = (
        Index('idx_chat_session_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_chat_session_client_id', 'client_id'),
        Index('idx_chat_session_updated', 'updated_at'),              # ← Новый индекс для сортировки по обновлению
        Index('idx_chat_session_tenant_updated', 'tenant_id', 'updated_at'),  # ← Составной индекс для фильтрации по компании + сортировки
    )

    # Связи
    tenant = relationship("Tenant", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="chat_session", cascade="all, delete-orphan")