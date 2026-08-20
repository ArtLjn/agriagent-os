"""统一业务时区工具（从 archive 迁移）。

提供北京时间工具函数，保证 service 层账单时间字段一致。
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    """返回北京时间的当前时刻。"""
    return datetime.now(BEIJING_TZ)


def beijing_today() -> date:
    """返回北京时间的当前日期。"""
    return beijing_now().date()


def ensure_beijing_timezone(value: datetime | None) -> datetime | None:
    """将 datetime 规范为北京时间；无时区值按北京时间解释。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING_TZ)
    return value.astimezone(BEIJING_TZ)


__all__ = [
    "BEIJING_TZ",
    "beijing_now",
    "beijing_today",
    "ensure_beijing_timezone",
]
