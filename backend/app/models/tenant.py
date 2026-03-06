# backend/app/models/tenant.py
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    company_name = Column(String, nullable=False)
    website_url = Column(String)

    # Настройки виджета в JSON
    widget_config = Column(JSON, default={
        "consultant_name": "Консультант",
        "consultant_avatar": None,
        "button_color": "#007bff",
        "welcome_message": "Здравствуйте! Чем могу помочь?",
        "typing_delay": 1000,
        "response_delay": 500
    })

    # Настройки AI
    ai_prompt = Column(Text, default="Ты - дружелюбный консультант. Отвечай на вопросы клиентов.")
    company_knowledge_base = Column(Text, default="")

    # Статус и баланс
    is_active = Column(Boolean, default=True)
    message_balance = Column(Integer, default=100)  # Начальный баланс для тестирования

    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    owner = relationship("User", back_populates="tenants")
    chat_sessions = relationship("ChatSession", back_populates="tenant", cascade="all, delete-orphan")