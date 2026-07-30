"""Agent Runtime LLM 调用与请求内重试。"""

import asyncio
import logging
import time as _time
from collections.abc import Callable

from langchain_core.messages import SystemMessage

from app.agent.runtime.llm_support import (
    _LLM_SEMAPHORE,
    _build_circuit_key,
    _record_llm_failure,
    _record_llm_success,
)
from app.shared.config import settings
from app.shared import llm as llm_client_manager

logger = logging.getLogger(__name__)


async def _invoke_llm_with_retry(
    *,
    model_role: str,
    raw_llm,
    llm,
    selected_tools: list,
    system: SystemMessage,
    messages: list,
    collector,
    input_summary: str,
    get_llm_func: Callable,
    bind_llm_func: Callable,
    max_retries: int,
    tool_choice: str = "auto",
):
    """执行 LLM 调用和请求内重试。"""
    start = _time.perf_counter()
    response = None
    circuit_key = _build_circuit_key(raw_llm)
    async with _LLM_SEMAPHORE:
        for attempt in range(max_retries):
            try:
                raw_llm, llm, circuit_key = _refresh_retry_llm(
                    attempt=attempt,
                    model_role=model_role,
                    raw_llm=raw_llm,
                    llm=llm,
                    selected_tools=selected_tools,
                    get_llm_func=get_llm_func,
                    bind_llm_func=bind_llm_func,
                    tool_choice=tool_choice,
                )
                response = await _invoke_llm_attempt(
                    attempt=attempt,
                    max_retries=max_retries,
                    model_role=model_role,
                    raw_llm=raw_llm,
                    llm=llm,
                    circuit_key=circuit_key,
                    selected_tools=selected_tools,
                    system=system,
                    messages=messages,
                    tool_choice=tool_choice,
                )
                break
            except TimeoutError as exc:
                if _handle_llm_error(
                    exc=exc,
                    attempt=attempt,
                    max_retries=max_retries,
                    raw_llm=raw_llm,
                    circuit_key=circuit_key,
                    collector=collector,
                    input_summary=input_summary,
                    model_role=model_role,
                    selected_tool_names=_selected_tool_names(selected_tools),
                    tool_choice=tool_choice,
                    message_count=len(messages),
                    start=start,
                ):
                    raise
            except Exception as exc:
                if _handle_llm_error(
                    exc=exc,
                    attempt=attempt,
                    max_retries=max_retries,
                    raw_llm=raw_llm,
                    circuit_key=circuit_key,
                    collector=collector,
                    input_summary=input_summary,
                    model_role=model_role,
                    selected_tool_names=_selected_tool_names(selected_tools),
                    tool_choice=tool_choice,
                    message_count=len(messages),
                    start=start,
                ):
                    raise
    duration_ms = int((_time.perf_counter() - start) * 1000)
    model_name = getattr(raw_llm, "model_name", "unknown")
    return response, raw_llm, llm, circuit_key, duration_ms, model_name


async def _invoke_llm_attempt(
    *,
    attempt: int,
    max_retries: int,
    model_role: str,
    raw_llm,
    llm,
    circuit_key: str,
    selected_tools: list,
    system: SystemMessage,
    messages: list,
    tool_choice: str,
):
    timeout_seconds = _llm_attempt_timeout_seconds()
    started_at = _time.perf_counter()
    _log_llm_attempt_started(
        attempt=attempt,
        max_retries=max_retries,
        model_role=model_role,
        raw_llm=raw_llm,
        circuit_key=circuit_key,
        selected_tools=selected_tools,
        tool_choice=tool_choice,
        timeout_seconds=timeout_seconds,
        message_count=len(messages),
    )
    try:
        response = await asyncio.wait_for(
            llm.ainvoke([system] + messages),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        _log_llm_attempt_timeout(
            attempt=attempt,
            max_retries=max_retries,
            raw_llm=raw_llm,
            circuit_key=circuit_key,
            started_at=started_at,
            timeout_seconds=timeout_seconds,
        )
        raise
    _record_llm_success(circuit_key)
    return response


def _llm_attempt_timeout_seconds() -> float:
    """返回 Agent LLM 单次调用硬超时，兜住 provider/代理长期不返回。"""
    cb = settings.circuit_breaker_config
    return max(1.0, cb.retry_backoff_base * (2**cb.retry_max) * 2)


def _selected_tool_names(selected_tools: list) -> list[str]:
    return [str(getattr(tool, "name", tool)) for tool in selected_tools]


def _log_llm_attempt_started(
    *,
    attempt: int,
    max_retries: int,
    model_role: str,
    raw_llm,
    circuit_key: str,
    selected_tools: list,
    tool_choice: str,
    timeout_seconds: float,
    message_count: int,
) -> None:
    logger.info(
        (
            "event=llm_call_started attempt=%d/%d role=%s key=%s model=%s "
            "selected_tools=%d tool_choice=%s timeout_seconds=%.1f message_count=%d"
        ),
        attempt + 1,
        max_retries,
        model_role,
        circuit_key,
        getattr(raw_llm, "model_name", "unknown"),
        len(selected_tools),
        tool_choice,
        timeout_seconds,
        message_count,
    )


def _log_llm_attempt_timeout(
    *,
    attempt: int,
    max_retries: int,
    raw_llm,
    circuit_key: str,
    started_at: float,
    timeout_seconds: float,
) -> None:
    logger.warning(
        (
            "event=llm_call_timeout attempt=%d/%d key=%s model=%s "
            "latency_ms=%d timeout_seconds=%.1f"
        ),
        attempt + 1,
        max_retries,
        circuit_key,
        getattr(raw_llm, "model_name", "unknown"),
        int((_time.perf_counter() - started_at) * 1000),
        timeout_seconds,
    )


def _refresh_retry_llm(
    *,
    attempt: int,
    model_role: str,
    raw_llm,
    llm,
    selected_tools: list,
    get_llm_func: Callable,
    bind_llm_func: Callable,
    tool_choice: str,
):
    """重试时重新获取模型并按本轮工具重新绑定。"""
    if attempt <= 0:
        return raw_llm, llm, _build_circuit_key(raw_llm)
    raw_llm = get_llm_func(role=model_role)
    circuit_key = _build_circuit_key(raw_llm)
    llm = bind_llm_func(
        raw_llm,
        selected_tools,
        log_no_tools=False,
        tool_choice=tool_choice,
    )
    return raw_llm, llm, circuit_key


def _handle_llm_error(
    *,
    exc: Exception,
    attempt: int,
    max_retries: int,
    raw_llm,
    circuit_key: str,
    collector,
    input_summary: str,
    model_role: str,
    selected_tool_names: list[str],
    tool_choice: str,
    message_count: int,
    start: float,
) -> bool:
    """记录失败并判断是否应立即抛出。"""
    duration_ms = int((_time.perf_counter() - start) * 1000)
    model_name = getattr(raw_llm, "model_name", "unknown")
    _record_llm_failure(circuit_key, exc)
    error_level = llm_client_manager.classify_error(exc)
    if error_level == llm_client_manager.ErrorLevel.MODEL:
        logger.warning(
            "LLM 不可恢复错误，跳过重试 | key=%s | model=%s | level=%s",
            circuit_key,
            model_name,
            error_level.value,
        )
        _record_llm_error_trace(
            collector=collector,
            model_name=model_name,
            input_summary=input_summary,
            model_role=model_role,
            circuit_key=circuit_key,
            selected_tool_names=selected_tool_names,
            tool_choice=tool_choice,
            message_count=message_count,
            duration_ms=duration_ms,
            exc=exc,
        )
        return True
    logger.warning(
        "LLM 重试 | attempt=%d/%d | key=%s | model=%s | latency_ms=%d | error=%s",
        attempt + 1,
        max_retries,
        circuit_key,
        model_name,
        duration_ms,
        str(exc)[:120],
    )
    if attempt == max_retries - 1:
        _record_llm_error_trace(
            collector=collector,
            model_name=model_name,
            input_summary=input_summary,
            model_role=model_role,
            circuit_key=circuit_key,
            selected_tool_names=selected_tool_names,
            tool_choice=tool_choice,
            message_count=message_count,
            duration_ms=duration_ms,
            exc=exc,
        )
        return True
    return False


def _record_llm_error_trace(
    *,
    collector,
    model_name: str,
    input_summary: str,
    model_role: str,
    circuit_key: str,
    selected_tool_names: list[str],
    tool_choice: str,
    message_count: int,
    duration_ms: int,
    exc: Exception,
) -> None:
    code = "llm_call_timeout" if isinstance(exc, TimeoutError) else "llm_call_failed"
    collector.record(
        node_type="llm_call",
        node_name=model_name,
        input_data={
            "input_summary": input_summary,
            "provider": circuit_key.split("/", 1)[0]
            if "/" in circuit_key
            else "unknown",
            "model": model_name,
            "role": model_role,
            "selected_tools": list(selected_tool_names),
            "tool_choice": tool_choice,
            "message_count": message_count,
            "timeout_seconds": _llm_attempt_timeout_seconds(),
        },
        output_data={
            "error": {
                "code": code,
                "message": str(exc)[:300],
                "recover": "retry_or_failover_provider",
            }
        },
        duration_ms=duration_ms,
        error_message=str(exc),
        status="timeout" if code == "llm_call_timeout" else "error",
    )


__all__ = ["_invoke_llm_with_retry"]
