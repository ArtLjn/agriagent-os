"""请求日期上下文 — 通过 ContextVar 在中间件和业务层之间传递日期。"""

from contextvars import ContextVar
from datetime import date

_current_date_ctx: ContextVar[str | None] = ContextVar("current_date", default=None)


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
    return date.today()


__all__ = ["get_request_date", "set_request_date"]
