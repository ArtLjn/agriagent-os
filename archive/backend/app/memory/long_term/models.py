"""长期记忆 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.shared.database import Base


class MemoryRecord(Base):
    """用户显式确认的长期记忆。"""

    __tablename__ = "memory_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(String(64), nullable=False, unique=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    type = Column(String(32), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="confirmed", index=True)
    source = Column(String(32), nullable=False, default="user_explicit", index=True)
    importance = Column(Float, nullable=False, default=0.8)
    confidence = Column(Float, nullable=False, default=1.0)
    superseded_by_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    archived_at = Column(DateTime, nullable=True)


__all__ = ["MemoryRecord"]
