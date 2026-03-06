# app/models/user.py
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)  # ДОБАВЛЯЕМ ЭТО ПОЛЕ
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    tenants = relationship("Tenant", back_populates="owner", cascade="all, delete-orphan")