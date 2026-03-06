# backend/app/models/__init__.py
from app.models.user import User
from app.models.tenant import Tenant
from app.models.chat_session import ChatSession
from app.models.message import Message

# Экспортируем все модели
__all__ = ["User", "Tenant", "ChatSession", "Message"]
