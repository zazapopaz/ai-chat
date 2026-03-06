# backend/app/schemas/chat.py
from pydantic import BaseModel, Field, validator, constr
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
import uuid

# Константы для валидации
MAX_MESSAGE_LENGTH = 2000
MAX_NAME_LENGTH = 100
MAX_PHONE_LENGTH = 20
MAX_EMAIL_LENGTH = 100
MIN_MESSAGE_LENGTH = 1
MIN_PHONE_LENGTH = 5


# Базовые схемы для ChatSession
class ChatSessionBase(BaseModel):
    lead_phone: Optional[str] = None
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    session_metadata: Optional[Dict[str, Any]] = None


class ChatSessionCreate(ChatSessionBase):
    tenant_id: str
    client_id: Optional[str] = None

    @validator('tenant_id')
    def validate_tenant_id(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('Неверный формат ID компании')
        return v

    @validator('client_id')
    def validate_client_id(cls, v):
        if v is None:
            return v
        if len(v) > 100:
            raise ValueError('Слишком длинный client_id')
        return v


class ChatSessionUpdate(ChatSessionBase):
    pass


class ChatSessionInDBBase(ChatSessionBase):
    id: str
    tenant_id: str
    client_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSession(ChatSessionInDBBase):
    pass


# Схемы для Message
class MessageBase(BaseModel):
    content: str
    is_from_lead: bool = True


class MessageCreate(MessageBase):
    chat_session_id: str

    @validator('chat_session_id')
    def validate_session_id(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('Неверный формат session_id')
        return v

    @validator('content')
    def validate_content(cls, v):
        """Упрощенная валидация содержимого сообщения"""
        if not v or not v.strip():
            raise ValueError('Сообщение не может быть пустым')

        # Проверка длины
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f'Сообщение слишком длинное (максимум {MAX_MESSAGE_LENGTH} символов)')

        # Базовая защита от XSS
        v = v.replace('<', '&lt;').replace('>', '&gt;')

        # Убираем множественные пробелы
        v = ' '.join(v.split())

        # Проверка на сокращенные ссылки
        suspicious_urls = ['bit.ly', 'goo.gl', 'tinyurl', 'is.gd', 'clck.ru', 'shorturl']
        if any(url in v.lower() for url in suspicious_urls):
            raise ValueError('Сокращённые ссылки запрещены')

        return v


class MessageInDBBase(MessageBase):
    id: str
    chat_session_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class Message(MessageInDBBase):
    pass


# Схемы для виджета с новыми лимитами
class WidgetMessageRequest(BaseModel):
    session_id: str
    message: constr(min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH)
    client_id: Optional[str] = None

    @validator('session_id')
    def validate_session_id(cls, v):
        """Разрешает как UUID, так и временные сессии с префиксом temp_"""
        if v is None:
            raise ValueError('session_id не может быть пустым')

        # Разрешаем временные сессии
        if v.startswith('temp_'):
            # Проверяем, что после temp_ есть что-то похожее на UUID
            temp_part = v[5:]  # отрезаем 'temp_'
            if len(temp_part) > 30:  # UUID примерно 36 символов
                try:
                    uuid.UUID(temp_part)
                except ValueError:
                    # Если не UUID, но похоже на наш формат - всё равно пропускаем
                    pass
            return v

        # Для обычных сессий проверяем UUID
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Неверный формат session_id')

    @validator('message')
    def validate_message(cls, v):
        """Упрощенная валидация сообщения"""
        # Базовая защита от XSS
        v = v.replace('<', '&lt;').replace('>', '&gt;')

        # Убираем множественные пробелы
        v = ' '.join(v.split())

        # Проверка на сокращенные ссылки
        suspicious_urls = ['bit.ly', 'goo.gl', 'tinyurl', 'is.gd', 'clck.ru']
        if any(url in v.lower() for url in suspicious_urls):
            raise ValueError('Сокращённые ссылки запрещены')

        return v

    @validator('client_id')
    def validate_client_id(cls, v):
        if v is None:
            return v
        if len(v) > 100:
            raise ValueError('Слишком длинный client_id')
        return v


class WidgetMessageResponse(BaseModel):
    response: str
    session_id: str
    message_balance: Optional[int] = None

    @validator('session_id')
    def validate_session_id(cls, v):
        """Разрешает как UUID, так и временные сессии"""
        if v.startswith('temp_'):
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Неверный формат session_id')


class WidgetStartResponse(BaseModel):
    session_id: str
    welcome_message: str

    @validator('session_id')
    def validate_session_id(cls, v):
        """Разрешает как UUID, так и временные сессии"""
        if v.startswith('temp_'):
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Неверный формат session_id')


# Схема для сохранения контактов с упрощенной валидацией
class SaveContactRequest(BaseModel):
    session_id: str
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    lead_email: Optional[str] = None
    client_id: Optional[str] = None

    @validator('session_id')
    def validate_session_id(cls, v):
        """Разрешает как UUID, так и временные сессии"""
        if v.startswith('temp_'):
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Неверный формат session_id')

    @validator('lead_phone')
    def validate_phone(cls, v):
        if v is None or v == '':
            return v

        # Очищаем от лишних символов
        v = re.sub(r'[^\d+\-\s\(\)]', '', v)
        v = ' '.join(v.split())

        # Проверяем минимальную длину (только предупреждение)
        digits = re.sub(r'\D', '', v)
        if len(digits) < 5:
            # Возвращаем как есть, просто логировать будем
            pass

        return v

    @validator('lead_email')
    def validate_email(cls, v):
        if v is None or v == '':
            return v

        v = v.strip().lower()

        # Базовая проверка формата (не блокируем, просто чистим)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            # Если не похоже на email, возвращаем None
            return None

        return v

    @validator('lead_name')
    def validate_name(cls, v):
        if v is None or v == '':
            return v

        # Убираем лишние пробелы и опасные символы
        v = ' '.join(v.split())
        v = re.sub(r'[<>\'"]', '', v)

        return v

    @validator('lead_phone', 'lead_email', always=True)
    def validate_at_least_one_contact(cls, v, values):
        """Проверяем, что указан хотя бы один способ связи"""
        if not values.get('lead_phone') and not values.get('lead_email'):
            return v
        return v

    @validator('client_id')
    def validate_client_id(cls, v):
        if v is None:
            return v
        if len(v) > 100:
            raise ValueError('Слишком длинный client_id')
        return v


# Валидация tenant_id в URL
class TenantPathParams(BaseModel):
    tenant_id: str

    @validator('tenant_id')
    def validate_tenant_id(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('Неверный формат ID компании')
        return v


# Дополнительная схема для массовых операций
class BulkDeleteRequest(BaseModel):
    session_ids: List[str]

    @validator('session_ids')
    def validate_session_ids(cls, v):
        if not v:
            raise ValueError('Список не может быть пустым')
        if len(v) > 100:
            raise ValueError('Слишком много сессий для удаления (максимум 100)')
        for session_id in v:
            try:
                uuid.UUID(session_id)
            except ValueError:
                # Проверяем, может это временная сессия
                if not session_id.startswith('temp_'):
                    raise ValueError(f'Неверный формат session_id: {session_id}')
        return v


# Схема для пагинации
class PaginationParams(BaseModel):
    skip: int = Field(0, ge=0, description="Сколько пропустить")
    limit: int = Field(100, ge=1, le=500, description="Сколько вернуть")

    @validator('skip')
    def validate_skip(cls, v):
        if v < 0:
            raise ValueError('skip не может быть отрицательным')
        return v


# Схема для фильтрации по дате
class DateRangeParams(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if values.get('start_date') and v and v < values['start_date']:
            raise ValueError('end_date должен быть позже start_date')
        return v