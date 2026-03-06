# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


# Базовые схемы для User
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=50)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=50)


class UserInDBBase(UserBase):
    id: str
    is_active: bool
    email_verified: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class User(UserInDBBase):
    pass


class UserInDB(UserInDBBase):
    hashed_password: str


# Схемы для регистрации и верификации
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=50)
    full_name: Optional[str] = None


class UserRegisterResponse(BaseModel):
    message: str
    email: str
    requires_verification: bool = True
    # Убираем id и created_at из ответа


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyEmailResponse(BaseModel):
    message: str
    verified: bool


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# Схемы для 2FA
class TwoFactorSettings(BaseModel):
    enabled: bool = False
    method: str = "email"  # email, sms, totp


class TwoFactorEnableRequest(BaseModel):
    password: str


class TwoFactorDisableRequest(BaseModel):
    password: str
    code: str


class TwoFactorVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class TwoFactorStatusResponse(BaseModel):
    enabled: bool
    method: Optional[str] = None


# Схемы для логина с поддержкой 2FA
class LoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    requires_2fa: bool = False
    message: Optional[str] = None
    email: Optional[str] = None


# Схема для токена
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[str] = None