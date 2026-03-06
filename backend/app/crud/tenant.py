# backend/app/crud/tenant.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate


class CRUDTenant:
    async def get(self, db: AsyncSession, tenant_id: str) -> Optional[Tenant]:
        """Получить тенанта по ID"""
        result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def get_by_owner(self, db: AsyncSession, owner_id: str) -> List[Tenant]:
        """Получить все тенанты пользователя"""
        result = await db.execute(select(Tenant).filter(Tenant.owner_id == owner_id))
        return result.scalars().all()

    async def create(self, db: AsyncSession, tenant_in: TenantCreate, owner_id: str) -> Tenant:
        """Создать новый тенант"""
        db_tenant = Tenant(
            **tenant_in.model_dump(),
            owner_id=owner_id
        )
        db.add(db_tenant)
        await db.commit()
        await db.refresh(db_tenant)
        return db_tenant

    async def update(self, db: AsyncSession, tenant: Tenant, tenant_in: TenantUpdate) -> Tenant:
        """Обновить тенант"""
        update_data = tenant_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(tenant, field, value)

        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant

    async def delete(self, db: AsyncSession, tenant_id: str) -> bool:
        """Удалить тенант"""
        tenant = await self.get(db, tenant_id)
        if tenant:
            await db.delete(tenant)
            await db.commit()
            return True
        return False


crud_tenant = CRUDTenant()