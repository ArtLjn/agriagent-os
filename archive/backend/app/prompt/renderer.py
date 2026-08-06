"""Prompt 渲染器。"""

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from jinja2 import Template

from app.shared.time import beijing_now
from app.prompt.models import PromptInput

if TYPE_CHECKING:
    from app.prompt.registry import PromptRegistry

logger = logging.getLogger(__name__)

_WEEKDAY_MAP = ["一", "二", "三", "四", "五", "六", "日"]


def _build_builtin_vars(current_date: date | None = None) -> dict:
    """构建内置模板变量。"""
    now = beijing_now()
    if current_date is None:
        current_date = now.date()
    weekday_cn = f"星期{_WEEKDAY_MAP[current_date.weekday()]}"
    return {
        "current_date": current_date.isoformat(),
        "current_time": now.strftime("%H:%M"),
        "current_weekday": weekday_cn,
        "yesterday": (current_date - timedelta(days=1)).isoformat(),
        "day_before_yesterday": (current_date - timedelta(days=2)).isoformat(),
    }


def render_prompt_input(
    name: str,
    prompt_input: PromptInput,
    *,
    registry: "PromptRegistry | None" = None,
    version: str | None = None,
) -> str:
    """使用结构化输入渲染指定 prompt。"""
    from app.prompt.registry import get_registry

    reg = registry or get_registry()
    template_str = reg.get(name, version)
    variables = prompt_input.as_variables()
    logger.debug(
        "模板渲染 | name=%s | hit=true | vars=%s",
        name,
        list(variables.keys()),
    )
    ctx = {**_build_builtin_vars(prompt_input.current_date), **variables}
    return Template(template_str).render(ctx)


def render_prompt(
    name: str,
    variables: dict | PromptInput | None = None,
    *,
    registry: "PromptRegistry | None" = None,
    current_date: date | None = None,
    version: str | None = None,
) -> str:
    """兼容旧 API 的 prompt 渲染入口。"""
    if isinstance(variables, PromptInput):
        prompt_input = variables
    else:
        prompt_input = PromptInput(variables=variables or {}, current_date=current_date)
    return render_prompt_input(
        name,
        prompt_input,
        registry=registry,
        version=version,
    )
