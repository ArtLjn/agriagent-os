"""用户设置模型 — 持久化用户偏好配置。"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func

from app.core.database import Base


class UserSetting(Base):
    """用户设置，每个用户最多一条记录。"""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    default_city = Column(String(50), nullable=True)
    default_lat = Column(Float, nullable=True)
    default_lon = Column(Float, nullable=True)
    assistant_role = Column(
        String(20), nullable=False, default="warm", server_default="warm"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
