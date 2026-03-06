#backend/app/schemas/tenant.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


# Базовые схемы для Tenant
class TenantBase(BaseModel):
    company_name: str
    website_url: Optional[str] = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    company_name: Optional[str] = None
    website_url: Optional[str] = None
    widget_config: Optional[Dict[str, Any]] = None
    ai_prompt: Optional[str] = None
    company_knowledge_base: Optional[str] = None
    is_active: Optional[bool] = None


class TenantInDBBase(TenantBase):
    id: str
    owner_id: str
    widget_config: Dict[str, Any]
    ai_prompt: str
    company_knowledge_base: str
    is_active: bool
    message_balance: int
    created_at: datetime

    class Config:
        from_attributes = True


class Tenant(TenantInDBBase):
    pass


class TenantWithCode(Tenant):
    widget_code: str