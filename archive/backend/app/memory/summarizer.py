"""会话 running summary 生成器。"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Iterable
from typing import Any

from jinja2 import Template
from langchain_core.messages import HumanMessage

from app.agent.runtime.llm_support import (
    _build_circuit_key,
    _record_llm_failure,
    _record_llm_success,
)
from app.shared.config import settings
from app.infra.trace_collector import get_collector
from app.observability import increment_counter
from app.prompt.registry import MEMORY_RUNNING_SUMMARY_PROMPT, get_registry

logger = logging.getLogger(__name__)

SUMMARY_TIMEOUT_SECONDS = 30
NO_SUMMARY_SENTINELS = {"无新增摘要", "无新增摘要。"}


def render_summary_prompt(
    *,
    current_summary: str | None,
    recent_messages: Iterable[Any],
    persona: str | None,
) -> str:
    """渲染会话摘要 prompt。"""
    template = Template(get_registry().get(MEMORY_RUNNING_SUMMARY_PROMPT))
    return template.render(
        current_summary=current_summary or "",
        recent_messages=_format_messages(recent_messages),
        persona=persona or "",
    )


async def generate_summary(
    llm: Any,
    current_summary: str | None,
    old_messages: Iterable[Any] | None,
    persona: str | None,
) -> str | None:
    """调用 LLM 生成追加式会话摘要；失败时返回 None 交给上层降级。"""
    messages = list(old_messages or [])
    circuit_key = _build_circuit_key(llm)
    started = time.perf_counter()

    try:
        prompt = render_summary_prompt(
            current_summary=current_summary,
            recent_messages=messages,
            persona=persona,
        )
        summary_llm = _with_max_tokens(llm, settings.ai.session_summary_max_tokens)
        response = await asyncio.wait_for(
            summary_llm.ainvoke([HumanMessage(content=prompt)]),
            timeout=SUMMARY_TIMEOUT_SECONDS,
        )
        summary = _extract_content(response).strip()
        if summary in NO_SUMMARY_SENTINELS:
            logger.info("会话摘要无新增内容 | key=%s", circuit_key)
            return None
        if not summary:
            raise ValueError("summary response is empty")
    except Exception as exc:
        increment_counter("session_summary_failed_total")
        _record_llm_failure(circuit_key, exc)
        logger.warning("会话摘要生成失败 | key=%s | error=%s", circuit_key, exc)
        return None

    duration_ms = int((time.perf_counter() - started) * 1000)
    _record_llm_success(circuit_key)
    increment_counter("session_summary_generated_total")
    _record_summary_trace(
        prompt=prompt,
        summary=summary,
        message_count=len(messages),
        has_current_summary=bool(current_summary),
        duration_ms=duration_ms,
    )
    return summary


def _format_messages(messages: Iterable[Any]) -> str:
    lines: list[str] = []
    for index, message in enumerate(messages or [], start=1):
        role = (
            _message_attr(message, "role")
            or _message_attr(message, "type")
            or "unknown"
        )
        content = _message_attr(message, "content")
        if content is None:
            content = str(message)
        lines.append(f"{index}. {role}: {content}")
    return "\n".join(lines) if lines else "（暂无新增消息）"


def _message_attr(message: Any, name: str) -> Any:
    if isinstance(message, dict):
        return message.get(name)
    return getattr(message, name, None)


def _extract_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _with_max_tokens(llm: Any, max_tokens: int) -> Any:
    bind = getattr(llm, "bind", None)
    if callable(bind) and not inspect.iscoroutinefunction(bind):
        try:
            bound = bind(max_tokens=max_tokens)
        except TypeError:
            pass
        else:
            if inspect.iscoroutinefunction(getattr(bound, "ainvoke", None)):
                return bound
    return llm


def _record_summary_trace(
    *,
    prompt: str,
    summary: str,
    message_count: int,
    has_current_summary: bool,
    duration_ms: int,
) -> None:
    prompt_tokens = _estimate_tokens(prompt)
    completion_tokens = _estimate_tokens(summary)
    get_collector().record(
        node_type="memory_summary",
        node_name="summary_generated",
        input_data={
            "farm_id": None,
            "session_id": None,
            "message_count": message_count,
            "current_summary_in_prompt": has_current_summary,
        },
        output_data={
            "summary_length": len(summary),
            "summary_preview": summary[:200],
        },
        duration_ms=duration_ms,
        token_usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "max_tokens": settings.ai.session_summary_max_tokens,
            "usage_source": "estimated",
        },
    )


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


__all__ = ["generate_summary", "render_summary_prompt"]
