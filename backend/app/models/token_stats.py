"""Token 日用量统计模型。"""

from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, Numeric, String, UniqueConstraint
from app.core.database import Base


class TokenDailyStats(Base):
    """按日汇总的 Token 用量统计。"""

    __tablename__ = "token_daily_stats"
    __table_args__ = (
        UniqueConstraint(
            "farm_id",
            "date",
            "model",
            "call_type",
            name="uq_token_stats",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=True, index=True)
    farm_id = Column(Integer, nullable=False, index=True)
    date = Column(String(10), nullable=False)
    model = Column(String(100), nullable=False)
    call_type = Column(String(20), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    request_count = Column(Integer, default=0)
    estimated_cost_cny = Column(Numeric(10, 6), default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
