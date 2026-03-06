# backend/app/models/admin.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_superadmin = Column(Boolean, default=False)
    two_factor_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id = Column(String, ForeignKey("admins.id"), nullable=False)
    action = Column(String, nullable=False)
    target_type = Column(String)
    target_id = Column(String)
    details = Column(JSON)
    ip_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin = relationship("Admin")