"""Mongo 双写失败补偿任务模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from app.core.database import Base


class MongoCompensationTask(Base):
    """Mongo 二级写失败后的可重放补偿任务。"""

    __tablename__ = "mongo_compensation_tasks"
    __table_args__ = (
        Index(
            "ix_mongo_compensation_tasks_status_next_retry",
            "status",
            "next_retry_at",
        ),
        Index(
            "ix_mongo_compensation_tasks_object_business",
            "object_type",
            "farm_id",
            "business_id",
        ),
        Index("ix_mongo_compensation_tasks_mysql_id", "mysql_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_type = Column(String(64), nullable=False)
    farm_id = Column(Integer, nullable=False)
    business_id = Column(String(160), nullable=True)
    mysql_id = Column(Integer, nullable=True)
    operation = Column(String(32), nullable=False, default="create")
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )
    next_retry_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
