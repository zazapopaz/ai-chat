# backend/app/schemas/dashboard.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class DashboardStats(BaseModel):
    total_sessions: int
    total_leads: int
    sessions_last_period: int
    leads_last_period: int
    messages_last_period: int
    active_sessions: int
    conversion_rate: float


class LeadInfo(BaseModel):
    session_id: str
    lead_name: Optional[str]
    lead_phone: Optional[str]
    lead_email: Optional[str]
    first_message_at: datetime
    last_message_at: datetime
    messages_count: int
    page_url: str
    preview_message: Optional[str] = None
    has_contacts: Optional[bool] = False

    class Config:
        from_attributes = True


class SessionsResponse(BaseModel):
    sessions: List[LeadInfo]
    total: int
    page: int
    limit: int
    has_contacts_count: int
    anonymous_count: int


class PromptUpdate(BaseModel):
    ai_prompt: str
    company_knowledge_base: str


class WidgetSettingsUpdate(BaseModel):
    consultant_name: str
    button_color: str
    welcome_message: str
    typing_delay: int  # мс
    response_delay: int  # мс
    widget_position: str  # 'bottom-right', 'bottom-left', etc.