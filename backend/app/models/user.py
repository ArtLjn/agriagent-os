"""用户模型 — 独立用户认证体系。"""

import enum

from sqlalchemy import Column, DateTime, String, func

from app.core.database import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    """用户模型，手机号 + 密码注册。"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    nickname = Column(String(50), nullable=False, default="农友")
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(20), nullable=False, default=UserRole.USER.value)
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


