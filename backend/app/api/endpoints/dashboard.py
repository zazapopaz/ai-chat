# backend/app/api/endpoints/dashboard.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime, timedelta

from app.crud import crud_tenant, crud_chat_session, crud_message
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatSession, Message
from app.schemas.dashboard import DashboardStats, LeadInfo, SessionsResponse

router = APIRouter(tags=["dashboard"])


@router.get("/{tenant_id}/stats", response_model=DashboardStats)
async def get_dashboard_stats(
        tenant_id: str,
        period_days: int = 7,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить статистику для дашборда"""
    tenant = await crud_tenant.get(db, tenant_id)
    if not tenant or tenant.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    # Рассчитываем дату начала периода
    start_date = datetime.utcnow() - timedelta(days=period_days)

    # Получаем сессии за период
    sessions = await crud_chat_session.get_by_tenant(db, tenant_id)
    sessions_period = [s for s in sessions if s.created_at >= start_date]

    # Статистика
    total_sessions = len(sessions)
    sessions_period_count = len(sessions_period)

    # Считаем лидов (сессии с контактами)
    leads = [s for s in sessions if s.lead_phone or s.lead_email]
    leads_period = [s for s in sessions_period if s.lead_phone or s.lead_email]

    # Сообщения
    all_messages = []
    for session in sessions_period:
        messages = await crud_message.get_by_session(db, session.id)
        all_messages.extend(messages)

    return DashboardStats(
        total_sessions=total_sessions,
        total_leads=len(leads),
        sessions_last_period=sessions_period_count,
        leads_last_period=len(leads_period),
        messages_last_period=len(all_messages),
        active_sessions=len([s for s in sessions_period if s.updated_at > datetime.utcnow() - timedelta(hours=1)]),
        conversion_rate=(len(leads_period) / sessions_period_count * 100) if sessions_period_count > 0 else 0
    )


@router.get("/{tenant_id}/leads", response_model=List[LeadInfo])
async def get_leads(
        tenant_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить список лидов ТОЛЬКО с контактами (для обратной совместимости)"""
    tenant = await crud_tenant.get(db, tenant_id)
    if not tenant or tenant.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    sessions = await crud_chat_session.get_by_tenant(db, tenant_id)

    leads = []
    for session in sessions:
        # ТОЛЬКО сессии с контактами
        if session.lead_phone or session.lead_email:
            # Получаем количество сообщений
            messages_count = await crud_message.get_session_messages_count(db, session.id)

            # Получаем первое сообщение для превью
            messages = await crud_message.get_by_session(db, session.id)
            first_user_message = next((msg.content for msg in messages if msg.is_from_lead), "")

            if len(first_user_message) > 50:
                first_user_message = first_user_message[:50] + "..."

            leads.append(LeadInfo(
                session_id=session.id,
                lead_name=session.lead_name or "Без имени",
                lead_phone=session.lead_phone,
                lead_email=session.lead_email,
                first_message_at=session.created_at,
                last_message_at=session.updated_at,
                messages_count=messages_count,
                page_url=session.session_metadata.get('page_url', '') if session.session_metadata else '',
                preview_message=first_user_message,
                has_contacts=True
            ))

    return leads


@router.get("/{tenant_id}/all-sessions", response_model=SessionsResponse)
async def get_all_sessions(
        tenant_id: str,
        include_anonymous: bool = True,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить ВСЕ сессии чата (с контактами и без)"""
    tenant = await crud_tenant.get(db, tenant_id)
    if not tenant or tenant.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    # Получаем все сессии
    all_sessions = await crud_chat_session.get_by_tenant(db, tenant_id)

    # Сортируем по дате обновления (новые сначала)
    all_sessions.sort(key=lambda x: x.updated_at, reverse=True)

    # Фильтруем если нужно только с контактами
    if not include_anonymous:
        all_sessions = [s for s in all_sessions if s.lead_phone or s.lead_email]

    # Применяем пагинацию
    total_sessions = len(all_sessions)
    paginated_sessions = all_sessions[skip:skip + limit]

    sessions_list = []
    for session in paginated_sessions:
        # Получаем количество сообщений
        messages_count = await crud_message.get_session_messages_count(db, session.id)

        # Получаем первое сообщение от пользователя для превью
        messages = await crud_message.get_by_session(db, session.id)
        first_user_message = next((msg.content for msg in messages if msg.is_from_lead), "Нет сообщений")

        # Обрезаем длинное сообщение
        if len(first_user_message) > 50:
            first_user_message = first_user_message[:50] + "..."

        # Определяем имя для отображения
        lead_name = session.lead_name
        if not lead_name:
            lead_name = "Анонимный пользователь"
            if session.session_metadata:
                # Пробуем извлечь информацию из user_agent
                user_agent = session.session_metadata.get('user_agent', '')
                if 'Mobile' in user_agent:
                    lead_name = "Мобильный пользователь"
                elif 'Chrome' in user_agent:
                    lead_name = "Пользователь Chrome"
                elif 'Firefox' in user_agent:
                    lead_name = "Пользователь Firefox"

        sessions_list.append(LeadInfo(
            session_id=session.id,
            lead_name=lead_name,
            lead_phone=session.lead_phone,
            lead_email=session.lead_email,
            first_message_at=session.created_at,
            last_message_at=session.updated_at,
            messages_count=messages_count,
            page_url=session.session_metadata.get('page_url', '') if session.session_metadata else '',
            preview_message=first_user_message,
            has_contacts=bool(session.lead_phone or session.lead_email)
        ))

    # Статистика по контактам
    with_contacts = sum(1 for s in all_sessions if s.lead_phone or s.lead_email)

    return SessionsResponse(
        sessions=sessions_list,
        total=total_sessions,
        page=skip // limit if limit > 0 else 0,
        limit=limit,
        has_contacts_count=with_contacts,
        anonymous_count=total_sessions - with_contacts
    )


@router.get("/{tenant_id}/sessions/{session_id}/messages", response_model=List[Message])
async def get_session_messages(
        tenant_id: str,
        session_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить все сообщения сессии"""
    tenant = await crud_tenant.get(db, tenant_id)
    if not tenant or tenant.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    session = await crud_chat_session.get(db, session_id)
    if not session or session.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    messages = await crud_message.get_by_session(db, session_id)
    return messages


@router.get("/{tenant_id}/recent-sessions", response_model=List[LeadInfo])
async def get_recent_sessions(
        tenant_id: str,
        hours: int = Query(24, ge=1, le=2160),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить недавние сессии за указанное количество часов"""
    tenant = await crud_tenant.get(db, tenant_id)
    if not tenant or tenant.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    # Рассчитываем дату начала
    start_date = datetime.utcnow() - timedelta(hours=hours)

    # Получаем все сессии
    all_sessions = await crud_chat_session.get_by_tenant(db, tenant_id)

    # Фильтруем по дате
    recent_sessions = [s for s in all_sessions if s.created_at >= start_date]

    # Сортируем по дате обновления (новые сначала)
    recent_sessions.sort(key=lambda x: x.updated_at, reverse=True)

    sessions_list = []
    for session in recent_sessions:
        # Получаем количество сообщений
        messages_count = await crud_message.get_session_messages_count(db, session.id)

        # Получаем первое сообщение для превью
        messages = await crud_message.get_by_session(db, session.id)
        first_user_message = next((msg.content for msg in messages if msg.is_from_lead), "")

        if len(first_user_message) > 50:
            first_user_message = first_user_message[:50] + "..."

        sessions_list.append(LeadInfo(
            session_id=session.id,
            lead_name=session.lead_name or "Анонимный пользователь",
            lead_phone=session.lead_phone,
            lead_email=session.lead_email,
            first_message_at=session.created_at,
            last_message_at=session.updated_at,
            messages_count=messages_count,
            page_url=session.session_metadata.get('page_url', '') if session.session_metadata else '',
            preview_message=first_user_message,
            has_contacts=bool(session.lead_phone or session.lead_email)
        ))

    return sessions_list


# ДОБАВЛЕННЫЙ ENDPOINT ДЛЯ УДАЛЕНИЯ ДИАЛОГОВ
@router.delete("/{tenant_id}/sessions/{session_id}")
async def delete_chat_session(
        tenant_id: str,
        session_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Удалить сессию чата и все её сообщения"""
    tenant = await crud_tenant.get(db, tenant_id)
    if not tenant or tenant.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    session = await crud_chat_session.get(db, session_id)
    if not session or session.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    try:
        # Удаляем сессию (все сообщения удалятся каскадно из-за cascade="all, delete-orphan")
        await db.delete(session)
        await db.commit()

        return {
            "status": "success",
            "message": "Диалог успешно удален",
            "session_id": session_id
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при удалении диалога: {str(e)}"
        )