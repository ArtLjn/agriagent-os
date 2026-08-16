"""Agent 错误分类、LLM 重试和断流收口契约测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.core import react
from agent.core.turn import StopReason, Turn
from agent.infra import error_policy, llm


@pytest.mark.parametrize(
    ("exc", "category", "retryable"),
    [
        (TimeoutError("provider timeout"), "transient", True),
        (MemoryError("context length exceeded"), "resource", False),
        (ValueError("invalid_request"), "permanent", False),
        (RuntimeError("model refused the request"), "model", False),
    ],
)
def test_classify_exception_assigns_recovery_category(exc, category, retryable) -> None:
    result = error_policy.classify_exception(exc)

    assert result.category.value == category
    assert result.retryable is retryable
    assert result.code


@pytest.mark.asyncio
async def test_chat_stream_retries_before_first_output(monkeypatch) -> None:
    attempts = 0

    class RetryableError(Exception):
        pass

    async def create(**_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary")

        async def chunks():
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="ok", tool_calls=None)
                    )
                ],
                usage=None,
            )

        return chunks()

    monkeypatch.setattr(llm._async_client.chat.completions, "create", create)
    monkeypatch.setattr(llm, "MAX_RETRIES", 1)
    monkeypatch.setattr(llm, "_retry_delay", lambda _: 0)

    events = [event async for event in llm.chat_stream([], [])]

    assert attempts == 2
    assert events[0]["type"] == "retrying"
    assert events[-1] == {"type": "done", "content": "ok", "tool_calls": []}


@pytest.mark.asyncio
async def test_chat_stream_marks_midstream_failure_without_retry(monkeypatch) -> None:
    attempts = 0

    async def create(**_kwargs):
        nonlocal attempts
        attempts += 1

        async def chunks():
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="partial", tool_calls=None)
                    )
                ],
                usage=None,
            )
            raise ConnectionError("connection reset")

        return chunks()

    monkeypatch.setattr(llm._async_client.chat.completions, "create", create)
    monkeypatch.setattr(llm, "MAX_RETRIES", 2)

    events = [event async for event in llm.chat_stream([], [])]
    error = events[-1]

    assert attempts == 1
    assert error["type"] == "error"
    assert error["data"] == {
        "code": "llm_transient_error",
        "category": "transient",
        "message": "connection reset",
        "retryable": True,
        "attempt": 0,
        "stream_started": True,
    }


@pytest.mark.asyncio
async def test_react_preserves_stream_failure_category_and_final_state() -> None:
    turn = Turn(user_input="流式断流")
    error = error_policy.ClassifiedError(
        error_policy.ErrorCategory.TRANSIENT,
        True,
        "llm_transient_error",
        "connection reset",
    )

    events = [
        event
        async for event in react._handle_llm_error(
            turn,
            error_policy.LlmStreamError(error, stream_started=True, attempt=0),
        )
    ]

    assert events[0]["data"]["code"] == "llm_stream_interrupted"
    assert events[0]["data"]["category"] == "transient"
    assert events[-1]["type"] == "final_answer"
    assert "中断" in events[-1]["data"]["text"]
    assert turn.stop_reason == StopReason.LLM_FAILED
    assert turn.error_details["category"] == "transient"
