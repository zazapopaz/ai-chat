# app/api/deps.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.core.config import settings
from app.database import get_db
from app.schemas.user import TokenData
# Убираем прямой импорт crud_user
# from app.crud import crud_user

security = HTTPBearer(auto_error=False)


async def get_current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
):
    """Получить текущего пользователя из JWT токена"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = None
        if credentials and credentials.credentials:
            token = credentials.credentials
        else:
            token = request.cookies.get("access_token")

        if not token:
            raise credentials_exception

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    # Импортируем здесь, чтобы избежать циклического импорта
    from app.crud import crud_user
    user = await crud_user.get_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user
