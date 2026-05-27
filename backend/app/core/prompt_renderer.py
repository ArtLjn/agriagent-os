"""Prompt 渲染器 — Jinja2 模板渲染 + 内置变量注入。"""

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from jinja2 import Template

if TYPE_CHECKING:
    from app.core.prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)

_WEEKDAY_MAP = ["一", "二", "三", "四", "五", "六", "日"]


def _build_builtin_vars(current_date: date | None = None) -> dict:
    """构建内置模板变量。"""
    if current_date is None:
        current_date = date.today()
    now = datetime.now()
    weekday_cn = f"星期{_WEEKDAY_MAP[current_date.weekday()]}"
    return {
        "current_date": current_date.isoformat(),
        "current_time": now.strftime("%H:%M"),
        "current_weekday": weekday_cn,
        "yesterday": (current_date - timedelta(days=1)).isoformat(),
        "day_before_yesterday": (current_date - timedelta(days=2)).isoformat(),
    }


def render_prompt(
    name: str,
    variables: dict | None = None,
    *,
    registry: "PromptRegistry | None" = None,
    current_date: date | None = None,
    version: str | None = None,
) -> str:
    """渲染指定名称的 prompt 模板。

    Args:
        name: 模板名称（注册表中的 key）。
        variables: 用户自定义变量。
        registry: PromptRegistry 实例，默认使用全局实例。
        current_date: 当前日期，默认使用服务端今天。
        version: 指定版本，默认使用注册表默认版本。

    Returns:
        渲染后的 prompt 字符串。

    Raises:
        KeyError: 模板未注册。
        TemplateError: 模板语法错误。
    """
    from app.core.prompt_registry import get_registry

    reg = registry or get_registry()
    template_str = reg.get(name, version)
    logger.debug(
        "模板渲染 | name=%s | hit=true | vars=%s",
        name,
        list((variables or {}).keys()),
    )

    builtin_vars = _build_builtin_vars(current_date)
    ctx = {**builtin_vars, **(variables or {})}
    template = Template(template_str)
    return template.render(ctx)


__all__ = ["render_prompt"]
