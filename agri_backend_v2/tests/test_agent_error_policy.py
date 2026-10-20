"""Agent 错误分类、LLM 重试和断流收口契约测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.domains.harness.runtime import engine as react
from agent.domains.harness.runtime.turn import StopReason, Turn
from agent.domains.harness.runtime import error_policy
from agent.platforms.llm import client as llm


@pytest.mark.asyncio
@pytest.mark.parametrize("required", [[], ["location"]])
async def test_empty_stream_args_repair_keeps_selected_call_identity(
    monkeypatch, required
) -> None:
    schema = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": required,
            },
        },
    }
    original = [
        {"id": "valid", "name": "other_tool", "arguments": {"id": 6}},
        {"id": "stream-id", "name": "get_weather", "arguments": {}},
    ]
    messages = [
        {"role": "assistant", "content": "需要查询上海市闵行区天气吗？"},
        {"role": "user", "content": "要"},
    ]
    requests = []

    async def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        tool_calls=[
                            SimpleNamespace(
                                id="replacement-id",
                                function=SimpleNamespace(
                                    name="get_weather",
                                    arguments='{"location":"上海市闵行区"}',
                                ),
                            )
                        ]
                    )
                )
            ]
        )

    monkeypatch.setattr(llm._async_client.chat.completions, "create", create)
    repaired = await llm._repair_empty_stream_tool_calls(
        messages, [schema], original, 0.3
    )
    assert repaired == [
        original[0],
        {
            "id": "stream-id",
            "name": "get_weather",
            "arguments": {"location": "上海市闵行区"},
        },
    ]
    assert original[1]["arguments"] == {}
    assert len(requests) == 1
    assert requests[0]["tools"] == [schema]
    assert requests[0]["tool_choice"]["function"]["name"] == "get_weather"
    assert requests[0]["messages"][:-1] == messages


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "arguments", "count"),
    [
        ("delete_worker", '{"name":"张三"}', 1),
        ("search_cities", "broken-json", 1),
        ("search_cities", '["上海"]', 1),
        ("search_cities", "{}", 1),
        ("search_cities", '{"keyword":"上海"}', 2),
        ("search_cities", '{"keyword":"上海"}', 0),
    ],
)
async def test_empty_args_repair_rejects_changed_action_or_invalid_result(
    monkeypatch, name, arguments, count
) -> None:
    schema = {
        "type": "function",
        "function": {
            "name": "search_cities",
            "parameters": {"properties": {"keyword": {"type": "string"}}},
        },
    }
    original = [{"id": "stream-id", "name": "search_cities", "arguments": {}}]

    async def create(**kwargs):
        call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(tool_calls=[call] * count))
            ]
        )

    monkeypatch.setattr(llm._async_client.chat.completions, "create", create)
    assert (
        await llm._repair_empty_stream_tool_calls([], [schema], original, 0.3)
        == original
    )


@pytest.mark.asyncio
async def test_parameterless_stream_call_does_not_request_repair(monkeypatch) -> None:
    async def unexpected(**kwargs):
        raise AssertionError("无参数工具不应发起补救请求")

    monkeypatch.setattr(llm._async_client.chat.completions, "create", unexpected)
    calls = [{"id": "query", "name": "list_crop_templates", "arguments": {}}]
    schema = [
        {
            "type": "function",
            "function": {
                "name": "list_crop_templates",
                "parameters": {"properties": {}},
            },
        }
    ]
    assert await llm._repair_empty_stream_tool_calls([], schema, calls, 0.3) == calls


def test_search_cities_requires_keyword_and_missing_hint_uses_history() -> None:
    from agent.domains.harness.tools import loader
    from agent.domains.harness.tools.base import McpSkill

    skill = next(s for s in loader.load_all() if s.name == "search_cities")
    assert isinstance(skill, McpSkill)
    assert skill.missing_required_params({}) == ["keyword"]
    result = react._missing_params_result(skill, ["keyword"])
    assert result["code"] == "missing_required_params"
    assert "最近对话" in result["message"]


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


def test_classify_mcp_permission_error_as_non_retryable_permission_denied() -> None:
    result = error_policy.classify_exception(
        RuntimeError(
            "Error calling tool manage_user_settings: MCP 工具需要权限: profile:read"
        )
    )

    assert result.code == "permission_denied"
    assert result.category is error_policy.ErrorCategory.PERMANENT
    assert result.retryable is False


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
    assert events[-2]["type"] == "final_answer"
    assert events[-1]["type"] == "turn.failed"
    assert "中断" in events[-2]["data"]["text"]
    assert turn.stop_reason == StopReason.LLM_FAILED
    assert turn.error_details["category"] == "transient"


@pytest.mark.asyncio
async def test_finalization_limits_reach_provider_without_tools(monkeypatch) -> None:
    requests = []

    async def create(**kwargs):
        requests.append(kwargs)

        async def chunks():
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="已完成", tool_calls=None)
                    )
                ],
                usage=None,
            )

        return chunks()

    monkeypatch.setattr(llm._async_client.chat.completions, "create", create)
    events = [
        event
        async for event in llm.chat_stream(
            [],
            [],
            tool_choice="none",
            max_tokens=react.finalization.FINALIZATION_MAX_TOKENS,
        )
    ]
    assert len(requests) == 1
    assert requests[0]["max_tokens"] == react.finalization.FINALIZATION_MAX_TOKENS
    assert requests[0]["tool_choice"] == "none"
    assert "tools" not in requests[0]
    assert events[-1]["type"] == "done"
