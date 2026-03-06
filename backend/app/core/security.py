# app/core/security.py
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, status, Request
import secrets

from app.core.config import settings

# Настройка для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT настройки
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    enabled=not settings.DEBUG  # Отключаем в режиме разработки
)

# HTTP Bearer схема
security = HTTPBearer(
    scheme_name="JWT",
    auto_error=True,
    description="JWT токен в формате: Bearer <token>"
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля с защитой от timing attack"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Всегда возвращаем False при ошибке для защиты от timing attack
        pwd_context.verify(secrets.token_hex(16), hashed_password)
        return False


def get_password_hash(password: str) -> str:
    """Хэширование пароля с использованием bcrypt"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT токена с expiration"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
        "jti": secrets.token_urlsafe(16)  # Unique JWT ID
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Создание refresh токена (30 дней)"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=30)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
        "jti": secrets.token_urlsafe(16)
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Декодирование JWT токена с обработкой ошибок"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истек",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка проверки токена",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        request: Request = None
) -> dict:
    """Получить текущего пользователя из JWT токена с проверкой"""
    token = credentials.credentials

    # Валидация формата токена
    if not token or len(token.split(".")) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный формат токена",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)

    # Проверка типа токена
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный тип токена",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Проверка subject
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не содержит subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Логирование успешной аутентификации (в продакшене)
    if request and not settings.DEBUG:
        request.state.auth_user = email

    return {"email": email, "jti": payload.get("jti")}


def validate_widget_domain(domain: str) -> bool:
    """Валидация домена для виджета"""
    if "*" in settings.WIDGET_ALLOWED_DOMAINS:
        return True

    # Проверяем точное совпадение или поддомены
    for allowed_domain in settings.WIDGET_ALLOWED_DOMAINS:
        if domain == allowed_domain or domain.endswith(f".{allowed_domain}"):
            return True

    return False


def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """Санитизация пользовательского ввода"""
    if not input_string:
        return ""

    # Обрезаем длину
    input_string = input_string[:max_length]

    # Убираем опасные символы (базовая защита от XSS)
    dangerous_chars = ["<", ">", "script", "javascript:", "onload", "onerror"]
    for char in dangerous_chars:
        input_string = input_string.replace(char, "")

    # Убираем лишние пробелы
    input_string = " ".join(input_string.split())

    return input_string.strip()


def generate_api_key() -> str:
    """Генерация безопасного API ключа для виджета"""
    return f"widget_{secrets.token_urlsafe(32)}"


def verify_api_key(api_key: str) -> bool:
    """Проверка API ключа виджета"""
    if not api_key or not api_key.startswith("widget_"):
        return False

    # В будущем можно проверять в базе данных
    return len(api_key) > 32