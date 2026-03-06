# app/api/dependencies.py
from fastapi import Depends, HTTPException, Request, Path
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import Optional

from app.database import get_db
from app.crud import crud_tenant
from app.models.tenant import Tenant


async def get_tenant_by_id(
        tenant_id: str = Path(..., description="ID компании"),
        db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    Зависимость для получения тенанта по ID с валидацией UUID
    """
    try:
        uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Неверный формат ID компании"
        )

    tenant = await crud_tenant.get(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Тенант не найден"
        )

    return tenant


async def get_tenant_for_widget(
        tenant_id: str = Path(..., description="ID компании"),
        db: AsyncSession = Depends(get_db)
) -> Optional[Tenant]:
    """
    Зависимость для виджета - возвращает None вместо 404
    """
    try:
        uuid.UUID(tenant_id)
    except ValueError:
        return None

    return await crud_tenant.get(db, tenant_id)


async def get_active_tenant(
        tenant: Tenant = Depends(get_tenant_by_id)
) -> Tenant:
    if not tenant.is_active:
        raise HTTPException(
            status_code=403,
            detail="Тенант деактивирован"
        )
    return tenant


async def get_tenant_with_balance(
        tenant: Tenant = Depends(get_active_tenant)
) -> Tenant:
    if tenant.message_balance <= 0:
        raise HTTPException(
            status_code=402,
            detail="Лимит сообщений исчерпан"
        )
    return tenant