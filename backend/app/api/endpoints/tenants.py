#backend/app/api/endpoints/tenants.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.crud import crud_tenant
from app.database import get_db
from app.api.deps import get_current_user
from app.api.dependencies import get_tenant_by_id as get_tenant_by_id_dep
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.tenant import Tenant as TenantSchema, TenantCreate, TenantUpdate, TenantWithCode

router = APIRouter(tags=["tenants"])


@router.get("/", response_model=List[TenantSchema])
async def get_tenants(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить все тенанты текущего пользователя"""
    tenants = await crud_tenant.get_by_owner(db, owner_id=current_user.id)
    return tenants


@router.post("/", response_model=TenantSchema, status_code=status.HTTP_201_CREATED)
async def create_tenant(
        tenant_in: TenantCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Создать новый тенант (компанию)"""
    tenant = await crud_tenant.create(db, tenant_in=tenant_in, owner_id=current_user.id)
    return tenant


@router.get("/{tenant_id}", response_model=TenantSchema)
async def get_tenant(
        tenant: Tenant = Depends(get_tenant_by_id_dep),
        current_user: User = Depends(get_current_user)
):
    """Получить тенант по ID"""
    if tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому тенанту")
    return tenant


@router.put("/{tenant_id}", response_model=TenantSchema)
async def update_tenant(
        tenant_in: TenantUpdate,
        db: AsyncSession = Depends(get_db),
        tenant: Tenant = Depends(get_tenant_by_id_dep),
        current_user: User = Depends(get_current_user)
):
    """Обновить тенант"""
    if tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому тенанту")

    updated_tenant = await crud_tenant.update(db, tenant=tenant, tenant_in=tenant_in)
    return updated_tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
        tenant: Tenant = Depends(get_tenant_by_id_dep),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Удалить тенант"""
    if tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому тенанту")

    await crud_tenant.delete(db, tenant_id=tenant.id)  # db нужно будет получить
    return None


@router.get("/{tenant_id}/widget-code", response_model=TenantWithCode)
async def get_widget_code(
        tenant: Tenant = Depends(get_tenant_by_id_dep),
        current_user: User = Depends(get_current_user)
):
    """Получить код виджета для вставки на сайт"""
    if tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому тенанту")

    # Генерируем код для вставки
    widget_code = f"""
    <!-- AI Chat Widget -->
    <script src="/api/v1/widget/{tenant.id}/widget.js"></script>
    <!-- End AI Chat Widget -->
    """

    # Создаем объект с кодом виджета
    tenant_dict = {**tenant.__dict__}
    tenant_dict["widget_code"] = widget_code.strip()
    tenant_dict.pop("_sa_instance_state", None)

    return tenant_dict