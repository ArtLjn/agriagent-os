"""运行时错误分类与 LLM 恢复策略。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """决定错误是否可以自动恢复的稳定分类。"""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    MODEL = "model"
    RESOURCE = "resource"


@dataclass(frozen=True)
class ClassifiedError:
    """异常的可观测分类，避免调用方重复猜测异常类型。"""

    category: ErrorCategory
    retryable: bool
    code: str
    message: str


class LlmStreamError(RuntimeError):
    """LLM 流结束异常，保留是否已向客户端发送过增量。"""

    def __init__(
        self,
        classified: ClassifiedError,
        *,
        stream_started: bool,
        attempt: int = 0,
    ) -> None:
        super().__init__(classified.message)
        self.classified = classified
        self.stream_started = stream_started
        self.attempt = attempt


def classify_exception(exc: Exception) -> ClassifiedError:
    """按 Provider/网络异常的稳定信号分类，不依赖具体 SDK 类。"""
    status_code = getattr(exc, "status_code", None)
    error_code = str(getattr(exc, "code", "") or "").lower()
    name = type(exc).__name__.lower()
    message = str(exc)
    lowered = f"{error_code} {name} {message}".lower()

    if isinstance(status_code, int) and status_code in {408, 425, 429}:
        return _classified(ErrorCategory.TRANSIENT, "llm_transient_error", message)
    if isinstance(status_code, int) and status_code >= 500:
        return _classified(ErrorCategory.TRANSIENT, "llm_provider_unavailable", message)

    if isinstance(exc, MemoryError) or any(
        marker in lowered
        for marker in ("context_length", "out of memory", "quota", "capacity")
    ):
        return _classified(ErrorCategory.RESOURCE, "llm_resource_exhausted", message)

    if any(
        marker in lowered
        for marker in (
            "timeout",
            "connection",
            "connecterror",
            "networkerror",
            "remoteprotocol",
            "readerror",
            "reset",
            "temporarily unavailable",
        )
    ):
        return _classified(ErrorCategory.TRANSIENT, "llm_transient_error", message)

    if isinstance(status_code, int) and status_code in {401, 403, 404, 422}:
        return _classified(ErrorCategory.PERMANENT, "llm_request_rejected", message)
    if any(
        marker in lowered
        for marker in ("invalid_request", "authentication", "permission")
    ):
        return _classified(ErrorCategory.PERMANENT, "llm_request_rejected", message)

    return _classified(ErrorCategory.MODEL, "llm_model_error", message)


def _classified(category: ErrorCategory, code: str, message: str) -> ClassifiedError:
    return ClassifiedError(
        category=category,
        retryable=category is ErrorCategory.TRANSIENT,
        code=code,
        message=message,
    )


def error_payload(
    classified: ClassifiedError,
    *,
    attempt: int = 0,
    stream_started: bool = False,
) -> dict[str, Any]:
    """构造可直接放入 SSE/Observation 的错误上下文。"""
    return {
        "code": classified.code,
        "category": classified.category.value,
        "message": classified.message,
        "retryable": classified.retryable,
        "attempt": attempt,
        "stream_started": stream_started,
    }
