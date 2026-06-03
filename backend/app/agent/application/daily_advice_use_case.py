"""Agent 每日建议 use case 入口。"""

from app.agent.application.advice_use_case import get_daily, refresh_daily

__all__ = ["get_daily", "refresh_daily"]
