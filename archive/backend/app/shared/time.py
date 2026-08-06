"""统一业务时区工具。"""

from contextvars import ContextVar
from datetime import date, datetime
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")
_current_date_ctx: ContextVar[str | None] = ContextVar("current_date", default=None)


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


def set_request_date(date_str: str) -> None:
    """设置当前请求的日期。"""
    _current_date_ctx.set(date_str)


def get_request_date() -> date:
    """获取当前请求的日期（来自请求头或服务端时间）。"""
    date_str = _current_date_ctx.get()
    if date_str:
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass
    return beijing_today()


__all__ = [
    "BEIJING_TZ",
    "beijing_now",
    "beijing_today",
    "ensure_beijing_timezone",
    "get_request_date",
    "set_request_date",
]
