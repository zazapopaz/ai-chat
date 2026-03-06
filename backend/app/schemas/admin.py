# backend/app/schemas/admin.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AdminBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class AdminCreate(AdminBase):
    password: str = Field(..., min_length=8, max_length=50)
    is_superadmin: bool = False
    two_factor_enabled: bool = False


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    requires_2fa: bool = False
    message: Optional[str] = None
    email: Optional[str] = None
    admin: Optional['AdminInDB'] = None


class AdminInDB(AdminBase):
    id: str
    is_superadmin: bool
    two_factor_enabled: bool
    is_active: bool = True
    email_verified: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminToken(BaseModel):
    access_token: str
    token_type: str
    admin: AdminInDB


class AdminTwoFactorEnableRequest(BaseModel):
    password: str


class AdminTwoFactorDisableRequest(BaseModel):
    password: str
    code: str


class AdminTwoFactorVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class AdminTwoFactorStatusResponse(BaseModel):
    enabled: bool
    email: str


class SystemStats(BaseModel):
    total_tenants: int
    total_users: int
    total_sessions: int
    total_messages: int
    total_leads: int
    active_tenants: int
    suspended_tenants: int
    messages_last_24h: int
    sessions_last_24h: int
    leads_last_24h: int


class TenantListItem(BaseModel):
    id: str
    company_name: str
    owner_email: str
    is_active: bool
    message_balance: int
    message_usage: int
    created_at: datetime
    last_activity: Optional[datetime]
    sessions_today: int
    leads_today: int


class AdminLogEntry(BaseModel):
    id: str
    admin_email: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminDashboardStats(BaseModel):
    system: SystemStats
    top_tenants: List[TenantListItem]
    recent_logs: List[AdminLogEntry]
    chart_data: Dict[str, List[int]]

AdminLoginResponse.model_rebuild()