#backend/app/crud/chat.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException

from app.models.chat_session import ChatSession
from app.models.message import Message
from app.schemas.chat import ChatSessionCreate, MessageCreate
from app.core.config import settings


class CRUDChatSession:
    async def get(self, db: AsyncSession, session_id: str) -> Optional[ChatSession]:
        """Получить сессию чата по ID"""
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(
            self,
            db: AsyncSession,
            tenant_id: str,
            skip: int = 0,
            limit: int = 100
    ) -> List[ChatSession]:
        """Получить все сессии чата тенанта с пагинацией"""
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.tenant_id == tenant_id)
            .order_by(desc(ChatSession.updated_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_by_tenant(self, db: AsyncSession, tenant_id: str) -> int:
        """Получить количество сессий тенанта"""
        result = await db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.tenant_id == tenant_id)
        )
        return result.scalar()

    async def create(self, db: AsyncSession, session_in: ChatSessionCreate) -> ChatSession:
        """Создать новую сессию чата с защитой от флуда"""
        ip = session_in.session_metadata.get("ip_address", "") if session_in.session_metadata else ""

        # Проверяем, не создавал ли этот IP слишком много сессий
        if ip:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.session_metadata['ip_address'].as_string() == ip,
                    ChatSession.created_at > one_hour_ago
                )
            )
            recent_sessions = result.scalars().all()

            if len(recent_sessions) >= settings.MAX_SESSIONS_PER_IP_PER_HOUR:
                raise HTTPException(
                    status_code=429,
                    detail=f"Слишком много сессий с этого IP. Максимум {settings.MAX_SESSIONS_PER_IP_PER_HOUR} в час"
                )

        # Проверяем, не слишком ли много активных сессий у тенанта
        if session_in.tenant_id:
            one_day_ago = datetime.utcnow() - timedelta(hours=24)
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.tenant_id == session_in.tenant_id,
                    ChatSession.created_at > one_day_ago
                )
            )
            tenant_sessions = result.scalars().all()

            if len(tenant_sessions) >= settings.MAX_SESSIONS_PER_TENANT_PER_DAY:
                raise HTTPException(
                    status_code=429,
                    detail=f"Слишком много сессий для этой компании. Максимум {settings.MAX_SESSIONS_PER_TENANT_PER_DAY} в день"
                )

        # Создаем сессию с явным указанием полей
        db_session = ChatSession(
            tenant_id=session_in.tenant_id,
            client_id=session_in.client_id,
            lead_phone=session_in.lead_phone,
            lead_name=session_in.lead_name,
            lead_email=session_in.lead_email,
            session_metadata=session_in.session_metadata
        )

        db.add(db_session)
        await db.commit()
        await db.refresh(db_session)
        return db_session

    async def update_lead_info(
            self,
            db: AsyncSession,
            session: ChatSession,
            lead_name: str = None,
            lead_phone: str = None,
            lead_email: str = None
    ) -> ChatSession:
        """Обновить информацию о лиде"""
        if lead_name:
            session.lead_name = lead_name
        if lead_phone:
            session.lead_phone = lead_phone
        if lead_email:
            session.lead_email = lead_email

        session.updated_at = datetime.utcnow()
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_active_sessions_count(
            self,
            db: AsyncSession,
            tenant_id: str,
            minutes: int = 5
    ) -> int:
        """Получить количество активных сессий за последние N минут"""
        time_threshold = datetime.utcnow() - timedelta(minutes=minutes)
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.updated_at > time_threshold
            )
        )
        return len(result.scalars().all())

    async def get_by_client_id(
            self,
            db: AsyncSession,
            client_id: str,
            hours: int = 24
    ) -> List[ChatSession]:
        """Получить сессии по client_id за последние N часов"""
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.client_id == client_id,
                ChatSession.created_at > time_threshold
            ).order_by(desc(ChatSession.created_at))
        )
        return result.scalars().all()

    async def delete_old_sessions(self, db: AsyncSession, days: int = 30) -> int:
        """Удалить старые сессии (для очистки)"""
        time_threshold = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(ChatSession).where(ChatSession.created_at < time_threshold)
        )
        old_sessions = result.scalars().all()

        for session in old_sessions:
            await db.delete(session)

        await db.commit()
        return len(old_sessions)

    async def delete(self, db: AsyncSession, session_id: str) -> bool:
        """Удалить сессию по ID"""
        session = await self.get(db, session_id)
        if session:
            await db.delete(session)
            await db.commit()
            return True
        return False


crud_chat_session = CRUDChatSession()


class CRUDMessage:
    async def get_by_session(
            self,
            db: AsyncSession,
            session_id: str,
            skip: int = 0,
            limit: int = 100
    ) -> List[Message]:
        """Получить все сообщения сессии с пагинацией"""
        result = await db.execute(
            select(Message)
            .where(Message.chat_session_id == session_id)
            .order_by(Message.created_at)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_messages_count(self, db: AsyncSession, session_id: str) -> int:
        """Получить количество сообщений в сессии"""
        result = await db.execute(
            select(func.count()).select_from(Message).where(Message.chat_session_id == session_id)
        )
        return result.scalar() or 0

    async def create(self, db: AsyncSession, message_in: MessageCreate) -> Message:
        """Создать новое сообщение с проверками"""

        # Проверяем длину сообщения
        if len(message_in.content) > settings.MAX_MESSAGE_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Сообщение слишком длинное (максимум {settings.MAX_MESSAGE_LENGTH} символов)"
            )

        # Проверяем минимальную длину
        if len(message_in.content.strip()) < settings.MIN_MESSAGE_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="Сообщение не может быть пустым"
            )

        # Проверяем, не слишком ли много сообщений в этой сессии (ВСЕГО, не только от пользователя)
        if message_in.chat_session_id:
            messages_count = await self.get_messages_count(db, message_in.chat_session_id)
            if messages_count >= settings.MAX_MESSAGES_PER_SESSION:
                raise HTTPException(
                    status_code=429,
                    detail=f"Достигнут лимит сообщений в этом диалоге. Максимум {settings.MAX_MESSAGES_PER_SESSION} сообщений"
                )

        # Создаем сообщение
        db_message = Message(
            chat_session_id=message_in.chat_session_id,
            content=message_in.content,
            is_from_lead=message_in.is_from_lead
        )
        db.add(db_message)

        # Обновляем updated_at в сессии
        session_result = await db.execute(
            select(ChatSession).where(ChatSession.id == message_in.chat_session_id)
        )
        session = session_result.scalar_one_or_none()
        if session:
            session.updated_at = datetime.utcnow()
            db.add(session)

        await db.commit()
        await db.refresh(db_message)
        return db_message

    async def get_session_messages_count(self, db: AsyncSession, session_id: str) -> int:
        """Получить количество сообщений в сессии (алиас для совместимости)"""
        return await self.get_messages_count(db, session_id)

    async def get_last_message(self, db: AsyncSession, session_id: str) -> Optional[Message]:
        """Получить последнее сообщение в сессии"""
        result = await db.execute(
            select(Message)
            .where(Message.chat_session_id == session_id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_old_messages(self, db: AsyncSession, days: int = 30) -> int:
        """Удалить старые сообщения (для очистки)"""
        time_threshold = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(Message).where(Message.created_at < time_threshold)
        )
        old_messages = result.scalars().all()

        for message in old_messages:
            await db.delete(message)

        await db.commit()
        return len(old_messages)

    async def get_user_messages_count(self, db: AsyncSession, session_id: str) -> int:
        """Получить количество сообщений от пользователя в сессии"""
        result = await db.execute(
            select(func.count())
            .select_from(Message)
            .where(
                Message.chat_session_id == session_id,
                Message.is_from_lead == True
            )
        )
        return result.scalar() or 0

    async def get_bot_messages_count(self, db: AsyncSession, session_id: str) -> int:
        """Получить количество сообщений от бота в сессии"""
        result = await db.execute(
            select(func.count())
            .select_from(Message)
            .where(
                Message.chat_session_id == session_id,
                Message.is_from_lead == False
            )
        )
        return result.scalar() or 0


crud_message = CRUDMessage()