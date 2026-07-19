"""Agent Runtime LLM 调用与请求内重试。"""

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
                response = await llm.ainvoke([system] + messages)
                _record_llm_success(circuit_key)
                break
            except Exception as exc:
                if _handle_llm_error(
                    exc=exc,
                    attempt=attempt,
                    max_retries=max_retries,
                    raw_llm=raw_llm,
                    circuit_key=circuit_key,
                    collector=collector,
                    input_summary=input_summary,
                    start=start,
                ):
                    raise
    duration_ms = int((_time.perf_counter() - start) * 1000)
    model_name = getattr(raw_llm, "model_name", "unknown")
    return response, raw_llm, llm, circuit_key, duration_ms, model_name


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
    duration_ms: int,
    exc: Exception,
) -> None:
    collector.record(
        node_type="llm_call",
        node_name=model_name,
        input_data=input_summary,
        duration_ms=duration_ms,
        error_message=str(exc),
    )


__all__ = ["_invoke_llm_with_retry"]
