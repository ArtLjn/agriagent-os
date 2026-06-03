"""农场模型 — 通过 user_id 关联用户。"""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class Farm(Base):
    """农场模型，作为多租户隔离的顶层实体。"""

    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=True)
    user_id = Column(String(36), unique=True, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
