# app/api/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import asyncio
import logging

from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.verification import verification_service
from app.core.email import email_service
from app.core.auth_limiter import login_attempt_tracker
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User as UserModel  # ← ПЕРЕИМЕНОВАЛИ МОДЕЛЬ
from app.schemas.user import (
    User as UserSchema,  # ← ПЕРЕИМЕНОВАЛИ СХЕМУ
    UserRegister,
    UserRegisterResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendVerificationRequest,
    TwoFactorEnableRequest,
    TwoFactorDisableRequest,
    TwoFactorVerifyRequest,
    TwoFactorStatusResponse,
    LoginResponse,
    Token
)
from app.crud import crud_user

router = APIRouter(tags=["authentication"])
logger = logging.getLogger(__name__)


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=(settings.ENVIRONMENT != "development"),
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
        user_in: UserRegister,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Регистрация нового пользователя с подтверждением email"""
    client_ip = request.client.host
    logger.info(f"Регистрация нового пользователя: {user_in.email} с IP {client_ip}")

    # Защита от brute-force при регистрации
    await asyncio.sleep(1)

    # Проверяем, существует ли пользователь
    user = await crud_user.get_by_email(db, email=user_in.email)
    if user:
        logger.info(f"Повторная регистрация для существующего email: {user_in.email}")
        return UserRegisterResponse(
            message="Если email доступен для регистрации, на него будет отправлен код подтверждения.",
            email=user_in.email,
            requires_verification=True
        )

    # Создаем пользователя
    hashed_password = get_password_hash(user_in.password)
    db_user = UserModel(
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        is_active=False,
        email_verified=False
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Создаем код подтверждения
    code = await verification_service.create_verification_code(
        user_in.email,
        purpose="register"
    )

    # Отправляем email с кодом
    await email_service.send_verification_email(
        to_email=user_in.email,
        full_name=user_in.full_name,
        code=code
    )

    logger.info(f"Пользователь {user_in.email} зарегистрирован, код подтверждения отправлен")

    # Явно создаем объект ответа
    response = UserRegisterResponse(
        message="Если email доступен для регистрации, на него будет отправлен код подтверждения.",
        email=user_in.email,
        requires_verification=True
    )

    logger.info(f"Возвращаем ответ: {response}")
    return response


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
        verify_data: VerifyEmailRequest,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Подтверждение email по коду"""
    client_ip = request.client.host
    logger.info(f"Подтверждение email: {verify_data.email} с IP {client_ip}")

    # Проверяем код
    is_valid = await verification_service.verify_code(
        verify_data.email,
        verify_data.code,
        purpose="register"
    )

    if not is_valid:
        logger.warning(f"Неверный код подтверждения для {verify_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или просроченный код подтверждения"
        )

    # Активируем пользователя
    user = await crud_user.get_by_email(db, email=verify_data.email)
    if not user:
        logger.error(f"Пользователь не найден после подтверждения: {verify_data.email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    user.is_active = True
    user.email_verified = True
    db.add(user)
    await db.commit()

    logger.info(f"Email {verify_data.email} успешно подтвержден")

    return VerifyEmailResponse(
        message="Email успешно подтвержден",
        verified=True
    )


@router.post("/resend-verification")
async def resend_verification(
        data: ResendVerificationRequest,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Повторная отправка кода подтверждения"""
    client_ip = request.client.host
    logger.info(f"📧 Повторная отправка кода для {data.email} с IP {client_ip}")

    # Защита от brute-force
    await asyncio.sleep(1)

    # Проверяем, существует ли пользователь
    user = await crud_user.get_by_email(db, email=data.email)
    if not user:
        logger.info(f"Повторная отправка для несуществующего email: {data.email}")
        return {"message": "Если учетная запись существует, код подтверждения отправлен"}

    if user.email_verified:
        logger.info(f"Повторная отправка для подтвержденного email: {data.email}")
        return {"message": "Если учетная запись существует, код подтверждения отправлен"}

    # Создаем новый код
    code = await verification_service.create_verification_code(
        data.email,
        purpose="register"
    )

    # Отправляем email
    await email_service.send_verification_email(
        to_email=data.email,
        full_name=user.full_name,
        code=code
    )

    logger.info(f"Код подтверждения отправлен повторно для {data.email}")

    return {"message": "Если учетная запись существует, код подтверждения отправлен"}


@router.post("/login", response_model=LoginResponse)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        response: Response = None,
        request: Request = None,
        db: AsyncSession = Depends(get_db)
):
    """Вход пользователя с защитой от перебора паролей и поддержкой 2FA"""
    client_ip = request.client.host if request else "unknown"
    email = form_data.username.lower().strip()

    logger.info(f"Попытка входа: {email} с IP {client_ip}")

    # 1. Проверяем, не заблокирован ли пользователь/IP
    is_blocked, block_message = await login_attempt_tracker.is_blocked(email, client_ip)
    if is_blocked:
        logger.warning(f"Заблокированная попытка входа: {email} с IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=block_message
        )

    # 2. Защита от brute-force (искусственная задержка)
    await asyncio.sleep(1)

    # 3. Аутентификация
    user = await crud_user.authenticate(
        db, email=email, password=form_data.password
    )

    if not user:
        # Записываем неудачную попытку
        await login_attempt_tracker.record_failed_attempt(email, client_ip)

        # Получаем оставшиеся попытки для информативного сообщения
        remaining = await login_attempt_tracker.get_remaining_attempts(email, client_ip)

        logger.warning(f"Неудачная попытка входа: {email} с IP {client_ip}. Осталось попыток: {remaining}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Неверный email или пароль. Осталось попыток: {remaining}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Попытка входа в неактивный аккаунт: {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт не активирован. Подтвердите email."
        )

    # Успешный вход - очищаем историю попыток
    await login_attempt_tracker.record_successful_attempt(email, client_ip)

    # Проверяем, включена ли 2FA
    twofa_settings = await verification_service.get_2fa_settings(user.id)

    if twofa_settings and twofa_settings.get("enabled"):
        # Создаем 2FA код
        code = await verification_service.create_2fa_code(user.email)

        # Отправляем код на email
        await email_service.send_2fa_email(
            to_email=user.email,
            full_name=user.full_name,
            code=code
        )

        logger.info(f"2FA код отправлен для {email}")

        return LoginResponse(
            requires_2fa=True,
            message="Код подтверждения отправлен на email",
            email=user.email
        )

    # Если 2FA не включена, сразу выдаем токен
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id},
        expires_delta=access_token_expires
    )
    if response:
        set_auth_cookie(response, access_token)

    logger.info(f"Успешный вход: {email} с IP {client_ip}")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        requires_2fa=False
    )


@router.post("/verify-2fa", response_model=Token)
async def verify_2fa_login(
        verify_data: TwoFactorVerifyRequest,
        request: Request,
        response: Response,
        db: AsyncSession = Depends(get_db)
):
    """Подтверждение 2FA кода при входе"""
    client_ip = request.client.host
    email = verify_data.email.lower().strip()

    logger.info(f"Проверка 2FA кода для {email} с IP {client_ip}")

    # Проверяем код
    is_valid = await verification_service.verify_2fa_code(
        email,
        verify_data.code
    )

    if not is_valid:
        logger.warning(f"Неверный 2FA код для {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный код подтверждения"
        )

    # Получаем пользователя
    user = await crud_user.get_by_email(db, email=email)
    if not user:
        logger.error(f"Пользователь не найден после 2FA: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Выдаем токен
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id},
        expires_delta=access_token_expires
    )
    if response:
        set_auth_cookie(response, access_token)

    logger.info(f"2FA подтвержден для {email}")

    return Token(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"message": "Выход выполнен"}


@router.post("/enable-2fa")
async def enable_2fa(
        request_data: TwoFactorEnableRequest,
        current_user: UserModel = Depends(get_current_user),  # ← ИСПОЛЬЗУЕМ UserModel
        req: Request = None,
        db: AsyncSession = Depends(get_db)
):
    """Включение двухфакторной аутентификации"""
    client_ip = req.client.host if req else "unknown"
    logger.info(f"Включение 2FA для пользователя {current_user.email} с IP {client_ip}")

    # Проверяем пароль для безопасности
    if not verify_password(request_data.password, current_user.hashed_password):
        logger.warning(f"Неверный пароль при включении 2FA для {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль"
        )

    # Сохраняем настройки 2FA
    await verification_service.save_2fa_settings(
        current_user.id,
        current_user.email,
        enabled=True
    )

    # Отправляем уведомление на email
    await email_service.send_2fa_enabled_notification(
        to_email=current_user.email,
        full_name=current_user.full_name
    )

    logger.info(f"2FA включена для {current_user.email}")

    return {"message": "Двухфакторная аутентификация включена"}


@router.post("/disable-2fa")
async def disable_2fa(
        request_data: TwoFactorDisableRequest,
        current_user: UserModel = Depends(get_current_user),  # ← ИСПОЛЬЗУЕМ UserModel
        req: Request = None,
        db: AsyncSession = Depends(get_db)
):
    """Отключение двухфакторной аутентификации"""
    client_ip = req.client.host if req else "unknown"
    logger.info(f"Отключение 2FA для пользователя {current_user.email} с IP {client_ip}")

    # Проверяем пароль
    if not verify_password(request_data.password, current_user.hashed_password):
        logger.warning(f"Неверный пароль при отключении 2FA для {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль"
        )

    # Проверяем 2FA код
    is_valid = await verification_service.verify_2fa_code(
        current_user.email,
        request_data.code
    )

    if not is_valid:
        logger.warning(f"Неверный 2FA код при отключении для {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный код подтверждения"
        )

    # Удаляем настройки 2FA
    await verification_service.delete_2fa_settings(current_user.id)

    # Отправляем уведомление
    await email_service.send_2fa_disabled_notification(
        to_email=current_user.email,
        full_name=current_user.full_name
    )

    logger.info(f"2FA отключена для {current_user.email}")

    return {"message": "Двухфакторная аутентификация отключена"}


@router.get("/2fa-status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(
        current_user: UserModel = Depends(get_current_user)  # ← ИСПОЛЬЗУЕМ UserModel
):
    """Получение статуса 2FA"""
    settings_data = await verification_service.get_2fa_settings(current_user.id)

    return TwoFactorStatusResponse(
        enabled=settings_data.get("enabled", False) if settings_data else False,
        method=settings_data.get("method", "email") if settings_data else None
    )


@router.get("/me", response_model=UserSchema)  # ← ИСПОЛЬЗУЕМ UserSchema для ответа
async def get_current_user_info(
        current_user: UserModel = Depends(get_current_user)  # ← UserModel для параметра
):
    """Получить информацию о текущем пользователе"""
    return current_user


# Добавим endpoint для проверки статуса блокировки (только для админов)
@router.get("/login-attempts/{email}", include_in_schema=False)
async def get_login_attempts(
        email: str,
        request: Request,
        current_user: UserModel = Depends(get_current_user)  # ← ИСПОЛЬЗУЕМ UserModel
):
    """Получить информацию о попытках входа (только для супер-админов)"""
    # Только супер-админ может смотреть чужие попытки
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    client_ip = request.client.host
    remaining = await login_attempt_tracker.get_remaining_attempts(email, client_ip)
    is_blocked, block_msg = await login_attempt_tracker.is_blocked(email, client_ip)

    return {
        "email": email,
        "remaining_attempts": remaining,
        "is_blocked": is_blocked,
        "block_message": block_msg,
        "max_attempts": login_attempt_tracker.max_attempts,
        "block_minutes": login_attempt_tracker.block_minutes
    }
