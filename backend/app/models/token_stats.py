"""Token 日用量统计模型。"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, Numeric, String, UniqueConstraint
from app.core.database import Base


class TokenDailyStats(Base):
    """按日汇总的 Token 用量统计。"""

    __tablename__ = "token_daily_stats"
    __table_args__ = (
        UniqueConstraint(
            "farm_id", "date", "model", "call_type", name="uq_token_stats"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    model = Column(String(100), nullable=False)
    call_type = Column(String(20), nullable=False)  # chat / daily_advice / report
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    request_count = Column(Integer, default=0)
    estimated_cost_cny = Column(Numeric(10, 6), default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
