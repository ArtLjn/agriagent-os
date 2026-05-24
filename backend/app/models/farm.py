from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class Farm(Base):
    """农场模型，作为多租户隔离的顶层实体。"""

    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
