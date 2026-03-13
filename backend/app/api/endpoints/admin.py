#backend/app/api/endpoints/admin.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
from jose import JWTError, jwt
import asyncio

from app.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.config import settings
from app.core.auth_limiter import login_attempt_tracker
from app.core.verification import verification_service
from app.core.email import email_service
from app.models.admin import Admin, AdminLog
from app.models.user import User
from app.models.tenant import Tenant
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.schemas.admin import (
    AdminLogin, AdminToken, AdminInDB, AdminCreate,
    AdminDashboardStats, SystemStats, TenantListItem,
    AdminLogEntry, AdminLoginResponse,
    AdminTwoFactorEnableRequest, AdminTwoFactorDisableRequest,
    AdminTwoFactorVerifyRequest, AdminTwoFactorStatusResponse
)

router = APIRouter(tags=["admin"])
security = HTTPBearer(auto_error=False)


def escape_like_search(search_term: str) -> str:
    """
    Экранирует спецсимволы для SQL LIKE запроса
    Заменяет % и _ на экранированные версии
    """
    if not search_term:
        return ""
    escaped = search_term.replace('%', '\\%').replace('_', '\\_')
    return f"%{escaped}%"


async def get_current_admin(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
) -> Admin:
    """Получить текущего админа по токену из заголовка Authorization"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials if credentials else request.cookies.get("admin_access_token")
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access" or payload.get("is_admin") is not True:
            raise credentials_exception
        admin_id: str = payload.get("sub")
        if admin_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if admin is None:
        raise credentials_exception

    return admin


async def log_admin_action(
        db: AsyncSession,
        admin_id: str,
        action: str,
        target_type: str = None,
        target_id: str = None,
        details: dict = None,
        ip_address: str = None
):
    """Логирование действий админа"""
    log = AdminLog(
        id=str(uuid.uuid4()),
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        ip_address=ip_address,
        created_at=datetime.utcnow()
    )
    db.add(log)
    await db.commit()


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
        login_data: AdminLogin,
        response: Response,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Вход для администратора с поддержкой 2FA"""
    client_ip = request.client.host if request and request.client else "unknown"
    email = login_data.email.lower().strip()

    is_blocked, block_message = await login_attempt_tracker.is_blocked(email, client_ip)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=block_message,
        )

    await asyncio.sleep(1)

    result = await db.execute(select(Admin).where(Admin.email == login_data.email))
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(login_data.password, admin.hashed_password):
        await login_attempt_tracker.record_failed_attempt(email, client_ip)
        remaining = await login_attempt_tracker.get_remaining_attempts(email, client_ip)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Неверный email или пароль. Осталось попыток: {remaining}"
        )

    if admin.two_factor_enabled:
        code = await verification_service.create_2fa_code(admin.email)

        await email_service.send_2fa_email(
            to_email=admin.email,
            full_name=admin.full_name,
            code=code
        )

        await log_admin_action(
            db, admin.id, "2fa_requested",
            ip_address=request.client.host
        )

        return AdminLoginResponse(
            requires_2fa=True,
            message="Код подтверждения отправлен на email",
            email=admin.email
        )

    admin.last_login = datetime.utcnow()
    db.add(admin)
    await db.commit()

    await login_attempt_tracker.record_successful_attempt(email, client_ip)

    await log_admin_action(
        db, admin.id, "login",
        ip_address=request.client.host
    )

    access_token = create_access_token(data={"sub": admin.id, "is_admin": True})
    response.set_cookie(
        key="admin_access_token",
        value=access_token,
        httponly=True,
        secure=(settings.ENVIRONMENT != "development"),
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return AdminLoginResponse(
        access_token=access_token,
        token_type="bearer",
        requires_2fa=False,
        admin=AdminInDB.model_validate(admin)
    )


@router.post("/verify-2fa", response_model=AdminToken)
async def verify_admin_2fa(
        verify_data: AdminTwoFactorVerifyRequest,
        response: Response,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Подтверждение 2FA кода при входе админа"""
    client_ip = request.client.host
    email = verify_data.email.lower().strip()

    is_valid = await verification_service.verify_2fa_code(
        email,
        verify_data.code
    )

    if not is_valid:
        await login_attempt_tracker.record_failed_attempt(email, client_ip)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный код подтверждения"
        )

    result = await db.execute(select(Admin).where(Admin.email == email))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Администратор не найден"
        )

    admin.last_login = datetime.utcnow()
    db.add(admin)
    await db.commit()

    await login_attempt_tracker.record_successful_attempt(email, client_ip)

    await log_admin_action(
        db, admin.id, "login_2fa",
        ip_address=request.client.host
    )

    access_token = create_access_token(data={"sub": admin.id, "is_admin": True})
    response.set_cookie(
        key="admin_access_token",
        value=access_token,
        httponly=True,
        secure=(settings.ENVIRONMENT != "development"),
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return AdminToken(
        access_token=access_token,
        token_type="bearer",
        admin=AdminInDB.model_validate(admin)
    )


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie("admin_access_token", path="/")
    return {"message": "Выход выполнен"}


@router.post("/me/enable-2fa")
async def enable_admin_2fa(
        request_data: AdminTwoFactorEnableRequest,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_admin: Admin = Depends(get_current_admin)
):
    """Включение двухфакторной аутентификации для админа"""

    if not verify_password(request_data.password, current_admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль"
        )

    current_admin.two_factor_enabled = True
    db.add(current_admin)
    await db.commit()

    await email_service.send_2fa_enabled_notification(
        to_email=current_admin.email,
        full_name=current_admin.full_name
    )

    await log_admin_action(
        db, current_admin.id, "enable_2fa",
        ip_address=request.client.host
    )

    return {"message": "Двухфакторная аутентификация включена"}


@router.post("/me/disable-2fa")
async def disable_admin_2fa(
        request_data: AdminTwoFactorDisableRequest,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_admin: Admin = Depends(get_current_admin)
):
    """Отключение двухфакторной аутентификации"""

    if not verify_password(request_data.password, current_admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль"
        )

    is_valid = await verification_service.verify_2fa_code(
        current_admin.email,
        request_data.code
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный код подтверждения"
        )

    current_admin.two_factor_enabled = False
    db.add(current_admin)
    await db.commit()

    await email_service.send_2fa_disabled_notification(
        to_email=current_admin.email,
        full_name=current_admin.full_name
    )

    await log_admin_action(
        db, current_admin.id, "disable_2fa",
        ip_address=request.client.host
    )

    return {"message": "Двухфакторная аутентификация отключена"}


@router.get("/me/2fa-status", response_model=AdminTwoFactorStatusResponse)
async def get_admin_2fa_status(
        current_admin: Admin = Depends(get_current_admin)
):
    """Получение статуса 2FA для текущего админа"""
    return AdminTwoFactorStatusResponse(
        enabled=current_admin.two_factor_enabled,
        email=current_admin.email
    )


@router.post("/create", response_model=AdminInDB)
async def create_admin(
        admin_data: AdminCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_admin: Admin = Depends(get_current_admin)
):
    """Создать нового администратора (только для супер-админа)"""
    if not current_admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только супер-админ может создавать новых администраторов"
        )

    existing = await db.execute(select(Admin).where(Admin.email == admin_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Администратор с таким email уже существует"
        )

    new_admin = Admin(
        id=str(uuid.uuid4()),
        email=admin_data.email,
        hashed_password=get_password_hash(admin_data.password),
        full_name=admin_data.full_name,
        is_superadmin=admin_data.is_superadmin,
        two_factor_enabled=admin_data.two_factor_enabled,
        created_at=datetime.utcnow()
    )

    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)

    await log_admin_action(
        db,
        current_admin.id,
        "create_admin",
        target_type="admin",
        target_id=new_admin.id,
        details={"email": new_admin.email, "is_superadmin": new_admin.is_superadmin},
        ip_address=request.client.host
    )

    return new_admin


@router.get("/dashboard", response_model=AdminDashboardStats)
async def get_admin_dashboard(
        request: Request,
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin)
):
    """Получить статистику для админ-панели"""
    try:
        await log_admin_action(db, admin.id, "view_dashboard", ip_address=request.client.host)

        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)

        total_tenants = await db.execute(select(func.count()).select_from(Tenant))
        total_tenants_val = total_tenants.scalar() or 0

        total_users = await db.execute(select(func.count()).select_from(User))
        total_users_val = total_users.scalar() or 0

        total_sessions = await db.execute(select(func.count()).select_from(ChatSession))
        total_sessions_val = total_sessions.scalar() or 0

        total_messages = await db.execute(select(func.count()).select_from(Message))
        total_messages_val = total_messages.scalar() or 0

        active_tenants = await db.execute(
            select(func.count()).select_from(Tenant).where(Tenant.is_active == True)
        )
        active_tenants_val = active_tenants.scalar() or 0

        messages_24h = await db.execute(
            select(func.count()).select_from(Message).where(Message.created_at > day_ago)
        )
        messages_24h_val = messages_24h.scalar() or 0

        sessions_24h = await db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.created_at > day_ago)
        )
        sessions_24h_val = sessions_24h.scalar() or 0

        top_tenants_query = await db.execute(
            select(
                Tenant.id,
                Tenant.company_name,
                User.email.label("owner_email"),
                Tenant.is_active,
                Tenant.message_balance,
                Tenant.created_at,
                func.count(ChatSession.id).label("sessions_count")
            )
            .join(User, User.id == Tenant.owner_id)
            .outerjoin(ChatSession, ChatSession.tenant_id == Tenant.id)
            .group_by(Tenant.id, User.email)
            .order_by(desc("sessions_count"))
            .limit(10)
        )
        top_tenants = top_tenants_query.all()

        recent_logs_query = await db.execute(
            select(AdminLog, Admin.email.label("admin_email"))
            .join(Admin, Admin.id == AdminLog.admin_id)
            .order_by(desc(AdminLog.created_at))
            .limit(20)
        )
        recent_logs = recent_logs_query.all()

        chart_data = {"sessions": [], "messages": [], "leads": []}
        for i in range(7):
            date = now - timedelta(days=i)
            next_date = date + timedelta(days=1)

            day_sessions = await db.execute(
                select(func.count()).select_from(ChatSession).where(
                    ChatSession.created_at.between(date, next_date)
                )
            )
            day_messages = await db.execute(
                select(func.count()).select_from(Message).where(
                    Message.created_at.between(date, next_date)
                )
            )
            day_leads = await db.execute(
                select(func.count()).select_from(ChatSession).where(
                    ChatSession.created_at.between(date, next_date),
                    (ChatSession.lead_phone != None) | (ChatSession.lead_email != None)
                )
            )

            chart_data["sessions"].insert(0, day_sessions.scalar() or 0)
            chart_data["messages"].insert(0, day_messages.scalar() or 0)
            chart_data["leads"].insert(0, day_leads.scalar() or 0)

        return AdminDashboardStats(
            system=SystemStats(
                total_tenants=total_tenants_val,
                total_users=total_users_val,
                total_sessions=total_sessions_val,
                total_messages=total_messages_val,
                total_leads=0,
                active_tenants=active_tenants_val,
                suspended_tenants=total_tenants_val - active_tenants_val,
                messages_last_24h=messages_24h_val,
                sessions_last_24h=sessions_24h_val,
                leads_last_24h=0,
            ),
            top_tenants=[{
                "id": t.id,
                "company_name": t.company_name,
                "owner_email": t.owner_email,
                "is_active": t.is_active,
                "message_balance": t.message_balance,
                "message_usage": 0,
                "created_at": t.created_at,
                "last_activity": None,
                "sessions_today": 0,
                "leads_today": 0
            } for t in top_tenants],
            recent_logs=[{
                "id": log.id,
                "admin_email": admin_email,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at
            } for log, admin_email in recent_logs],
            chart_data=chart_data
        )
    except Exception as e:
        print(f"Ошибка в dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/tenants", response_model=List[TenantListItem])
async def get_all_tenants(
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        search: Optional[str] = Query(None, min_length=1, max_length=100),
        is_active: Optional[bool] = None
):
    """
    Получить список всех тенантов с защитой от SQL инъекций
    """
    query = select(Tenant, User.email).join(User, User.id == Tenant.owner_id)

    if search:
        search_term = escape_like_search(search)
        query = query.where(
            or_(
                Tenant.company_name.ilike(search_term, escape='\\'),
                User.email.ilike(search_term, escape='\\')
            )
        )

    if is_active is not None:
        query = query.where(Tenant.is_active == is_active)

    query = query.order_by(desc(Tenant.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    tenants = result.all()

    return [{
        "id": t.id,
        "company_name": t.company_name,
        "owner_email": email,
        "is_active": t.is_active,
        "message_balance": t.message_balance,
        "message_usage": 0,
        "created_at": t.created_at,
        "last_activity": None,
        "sessions_today": 0,
        "leads_today": 0
    } for t, email in tenants]


@router.get("/tenants/search", response_model=List[TenantListItem])
async def search_tenants_advanced(
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin),
        company: Optional[str] = Query(None, min_length=2, max_length=100, description="Поиск по названию компании"),
        email: Optional[str] = Query(None, min_length=5, max_length=100, description="Поиск по email владельца"),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100)
):
    """
    Расширенный поиск с раздельными полями для большей безопасности
    """
    if not company and not email:
        raise HTTPException(
            status_code=400,
            detail="Укажите хотя бы один параметр для поиска (company или email)"
        )

    query = select(Tenant, User.email).join(User, User.id == Tenant.owner_id)

    conditions = []

    if company:
        company_term = escape_like_search(company)
        conditions.append(Tenant.company_name.ilike(company_term, escape='\\'))

    if email:
        email_term = escape_like_search(email)
        conditions.append(User.email.ilike(email_term, escape='\\'))

    if conditions:
        query = query.where(or_(*conditions))

    query = query.order_by(desc(Tenant.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    tenants = result.all()

    return [{
        "id": t.id,
        "company_name": t.company_name,
        "owner_email": email_val,
        "is_active": t.is_active,
        "message_balance": t.message_balance,
        "message_usage": 0,
        "created_at": t.created_at,
        "last_activity": None,
        "sessions_today": 0,
        "leads_today": 0
    } for t, email_val in tenants]


@router.post("/tenants/{tenant_id}/toggle")
async def toggle_tenant_status(
        tenant_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin)
):
    """Заблокировать/разблокировать тенант"""
    if not admin.is_superadmin:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    tenant.is_active = not tenant.is_active
    db.add(tenant)

    await log_admin_action(
        db, admin.id, "toggle_tenant",
        target_type="tenant",
        target_id=tenant_id,
        details={"new_status": tenant.is_active},
        ip_address=request.client.host
    )

    await db.commit()

    return {"status": "success", "is_active": tenant.is_active}


@router.post("/tenants/{tenant_id}/balance")
async def add_tenant_balance(
        tenant_id: str,
        request: Request,
        amount: int = Query(..., gt=0, le=1000000),
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin)
):
    """Пополнить баланс сообщений тенанта"""
    if not admin.is_superadmin:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    tenant.message_balance += amount
    db.add(tenant)

    await log_admin_action(
        db, admin.id, "add_balance",
        target_type="tenant",
        target_id=tenant_id,
        details={"amount": amount, "new_balance": tenant.message_balance},
        ip_address=request.client.host
    )

    await db.commit()

    return {
        "status": "success",
        "new_balance": tenant.message_balance,
        "added": amount
    }


@router.post("/tenants/{tenant_id}/deduct-balance")
async def deduct_tenant_balance(
        tenant_id: str,
        request: Request,
        amount: int = Query(..., gt=0, le=1000000),
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin)
):
    """Списать сообщения с баланса тенанта"""
    if not admin.is_superadmin:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    if tenant.message_balance < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно сообщений. Доступно: {tenant.message_balance}"
        )

    tenant.message_balance -= amount
    db.add(tenant)

    await log_admin_action(
        db, admin.id, "deduct_balance",
        target_type="tenant",
        target_id=tenant_id,
        details={"amount": amount, "new_balance": tenant.message_balance},
        ip_address=request.client.host
    )

    await db.commit()

    return {
        "status": "success",
        "new_balance": tenant.message_balance,
        "deducted": amount
    }


@router.get("/tenants/{tenant_id}/details")
async def get_tenant_details(
        tenant_id: str,
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin)
):
    """Получить детальную информацию о компании"""
    if not admin:
        raise HTTPException(status_code=401, detail="Не авторизован")

    tenant_result = await db.execute(
        select(Tenant, User.email).join(User, User.id == Tenant.owner_id).where(Tenant.id == tenant_id)
    )
    tenant_data = tenant_result.first()

    if not tenant_data:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    tenant, owner_email = tenant_data

    total_sessions = await db.execute(
        select(func.count()).select_from(ChatSession).where(ChatSession.tenant_id == tenant_id)
    )
    total_sessions_val = total_sessions.scalar() or 0

    day_ago = datetime.utcnow() - timedelta(days=1)
    active_sessions = await db.execute(
        select(func.count()).select_from(ChatSession).where(
            ChatSession.tenant_id == tenant_id,
            ChatSession.updated_at > day_ago
        )
    )
    active_sessions_val = active_sessions.scalar() or 0

    leads = await db.execute(
        select(func.count()).select_from(ChatSession).where(
            ChatSession.tenant_id == tenant_id,
            (ChatSession.lead_phone != None) | (ChatSession.lead_email != None)
        )
    )
    leads_val = leads.scalar() or 0

    messages_result = await db.execute(
        select(func.count()).select_from(Message)
        .join(ChatSession, ChatSession.id == Message.chat_session_id)
        .where(ChatSession.tenant_id == tenant_id)
    )
    messages_val = messages_result.scalar() or 0

    recent_sessions_query = await db.execute(
        select(ChatSession)
        .where(ChatSession.tenant_id == tenant_id)
        .order_by(desc(ChatSession.created_at))
        .limit(10)
    )
    recent_sessions = recent_sessions_query.scalars().all()

    sessions_data = []
    for session in recent_sessions:
        msg_count = await db.execute(
            select(func.count()).select_from(Message).where(Message.chat_session_id == session.id)
        )
        msg_count_val = msg_count.scalar() or 0

        last_msg = await db.execute(
            select(Message)
            .where(Message.chat_session_id == session.id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        last_msg_obj = last_msg.scalar_one_or_none()

        sessions_data.append({
            "id": session.id,
            "lead_name": session.lead_name or "Аноним",
            "lead_phone": session.lead_phone,
            "lead_email": session.lead_email,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages_count": msg_count_val,
            "last_message": last_msg_obj.content if last_msg_obj else None,
            "has_contacts": bool(session.lead_phone or session.lead_email)
        })

    return {
        "tenant": {
            "id": tenant.id,
            "company_name": tenant.company_name,
            "website_url": tenant.website_url,
            "owner_email": owner_email,
            "is_active": tenant.is_active,
            "message_balance": tenant.message_balance,
            "created_at": tenant.created_at,
            "widget_config": tenant.widget_config,
            "ai_prompt": tenant.ai_prompt
        },
        "stats": {
            "total_sessions": total_sessions_val,
            "active_sessions": active_sessions_val,
            "total_leads": leads_val,
            "total_messages": messages_val,
            "conversion_rate": round((leads_val / total_sessions_val * 100) if total_sessions_val > 0 else 0, 2)
        },
        "recent_sessions": sessions_data
    }


@router.get("/tenants/{tenant_id}/all-sessions")
async def get_tenant_all_sessions(
        tenant_id: str,
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100)
):
    """Получить все сессии компании с пагинацией"""
    if not admin:
        raise HTTPException(status_code=401, detail="Не авторизован")

    tenant = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Тенант не найден")

    total = await db.execute(
        select(func.count()).select_from(ChatSession).where(ChatSession.tenant_id == tenant_id)
    )
    total_val = total.scalar() or 0

    sessions_query = await db.execute(
        select(ChatSession)
        .where(ChatSession.tenant_id == tenant_id)
        .order_by(desc(ChatSession.created_at))
        .offset(skip)
        .limit(limit)
    )
    sessions = sessions_query.scalars().all()

    sessions_data = []
    for session in sessions:
        msg_count = await db.execute(
            select(func.count()).select_from(Message).where(Message.chat_session_id == session.id)
        )

        first_msg = await db.execute(
            select(Message)
            .where(Message.chat_session_id == session.id, Message.is_from_lead == True)
            .order_by(Message.created_at)
            .limit(1)
        )
        first_msg_obj = first_msg.scalar_one_or_none()

        sessions_data.append({
            "id": session.id,
            "lead_name": session.lead_name or "Анонимный пользователь",
            "lead_phone": session.lead_phone,
            "lead_email": session.lead_email,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages_count": msg_count.scalar() or 0,
            "preview": first_msg_obj.content[:100] + "..." if first_msg_obj and len(first_msg_obj.content) > 100 else (
                first_msg_obj.content if first_msg_obj else ""),
            "has_contacts": bool(session.lead_phone or session.lead_email)
        })

    return {
        "total": total_val,
        "sessions": sessions_data,
        "page": skip // limit + 1 if limit > 0 else 1,
        "total_pages": (total_val + limit - 1) // limit if limit > 0 else 1
    }


@router.get("/tenants/{tenant_id}/leads")
async def get_tenant_leads(
        tenant_id: str,
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100)
):
    """Получить все лиды компании (сессии с контактами)"""
    if not admin:
        raise HTTPException(status_code=401, detail="Не авторизован")

    tenant = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Тенант не найден")

    total = await db.execute(
        select(func.count()).select_from(ChatSession).where(
            ChatSession.tenant_id == tenant_id,
            (ChatSession.lead_phone != None) | (ChatSession.lead_email != None)
        )
    )
    total_val = total.scalar() or 0

    leads_query = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.tenant_id == tenant_id,
            (ChatSession.lead_phone != None) | (ChatSession.lead_email != None)
        )
        .order_by(desc(ChatSession.created_at))
        .offset(skip)
        .limit(limit)
    )
    leads = leads_query.scalars().all()

    leads_data = []
    for lead in leads:
        msg_count = await db.execute(
            select(func.count()).select_from(Message).where(Message.chat_session_id == lead.id)
        )

        leads_data.append({
            "id": lead.id,
            "lead_name": lead.lead_name or "Не указано",
            "lead_phone": lead.lead_phone,
            "lead_email": lead.lead_email,
            "created_at": lead.created_at,
            "updated_at": lead.updated_at,
            "messages_count": msg_count.scalar() or 0
        })

    return {
        "total": total_val,
        "leads": leads_data,
        "page": skip // limit + 1 if limit > 0 else 1,
        "total_pages": (total_val + limit - 1) // limit if limit > 0 else 1
    }


@router.get("/tenants/{tenant_id}/session/{session_id}/messages")
async def get_session_messages_admin(
        tenant_id: str,
        session_id: str,
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin)
):
    """Получить все сообщения конкретной сессии"""
    if not admin:
        raise HTTPException(status_code=401, detail="Не авторизован")

    session = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == tenant_id
        )
    )
    session_obj = session.scalar_one_or_none()

    if not session_obj:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    messages_query = await db.execute(
        select(Message)
        .where(Message.chat_session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = messages_query.scalars().all()

    return [{
        "id": msg.id,
        "content": msg.content,
        "is_from_lead": msg.is_from_lead,
        "created_at": msg.created_at,
        "sender": "Клиент" if msg.is_from_lead else "Бот"
    } for msg in messages]


@router.get("/logs", response_model=List[AdminLogEntry])
async def get_admin_logs(
        db: AsyncSession = Depends(get_db),
        admin: Admin = Depends(get_current_admin),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        admin_id: Optional[str] = None,
        action: Optional[str] = None
):
    """Получить логи действий администраторов"""
    if not admin.is_superadmin:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    query = select(AdminLog, Admin.email).join(Admin, Admin.id == AdminLog.admin_id)

    if admin_id:
        query = query.where(AdminLog.admin_id == admin_id)
    if action:
        query = query.where(AdminLog.action == action)

    query = query.order_by(desc(AdminLog.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    logs = result.all()

    return [{
        "id": log.id,
        "admin_email": email,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "details": log.details,
        "ip_address": log.ip_address,
        "created_at": log.created_at
    } for log, email in logs]
