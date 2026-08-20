from types import SimpleNamespace

import httpx
import pytest
from openai import InternalServerError

from agent.infra import llm


class _TextStream:
    def __init__(self, text: str) -> None:
        self._chunks = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=text, tool_calls=None)
                    )
                ]
            )
        ]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._chunks:
            return self._chunks.pop(0)
        raise StopAsyncIteration


class _UsageStream:
    def __init__(self) -> None:
        self._chunks = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="回答", tool_calls=None)
                    )
                ],
                usage=None,
            ),
            SimpleNamespace(
                choices=[],
                usage=SimpleNamespace(
                    prompt_tokens=120,
                    completion_tokens=18,
                    total_tokens=138,
                    prompt_tokens_details=SimpleNamespace(cached_tokens=32),
                ),
            ),
        ]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._chunks:
            return self._chunks.pop(0)
        raise StopAsyncIteration


def _tool_schema(required: list[str]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "create_worker",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": required,
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_empty_required_stream_arguments_are_repaired(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(
            name="create_worker",
            arguments='{"name":"张三"}',
        ),
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[tool_call]))]
    )

    class Completions:
        async def create(self, **_kwargs):
            return response

    monkeypatch.setattr(
        llm,
        "_async_client",
        SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )

    repaired = await llm._repair_empty_stream_tool_calls(
        [{"role": "user", "content": "新增工人张三"}],
        _tool_schema(["name"]),
        [{"id": "call-0", "name": "create_worker", "arguments": {}}],
        0.3,
    )

    assert repaired == [
        {"id": "call-1", "name": "create_worker", "arguments": {"name": "张三"}}
    ]


@pytest.mark.asyncio
async def test_parameterless_tool_call_does_not_trigger_repair(monkeypatch):
    class Completions:
        async def create(self, **_kwargs):
            raise AssertionError("无必填参数的工具不应触发非流式修复")

    monkeypatch.setattr(
        llm,
        "_async_client",
        SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )
    original = [{"id": "call-0", "name": "create_worker", "arguments": {}}]

    repaired = await llm._repair_empty_stream_tool_calls(
        [], _tool_schema([]), original, 0.3
    )

    assert repaired is original


@pytest.mark.asyncio
async def test_stream_retries_provider_502_before_first_token(monkeypatch):
    response = httpx.Response(502, request=httpx.Request("POST", "https://llm.test"))
    provider_error = InternalServerError("upstream unavailable", response=response, body=None)
    calls = 0

    class Completions:
        async def create(self, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise provider_error
            return _TextStream("天气正常")

    monkeypatch.setattr(
        llm,
        "_async_client",
        SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )
    monkeypatch.setattr(llm, "RETRY_DELAY_SECONDS", 0)

    events = [
        event
        async for event in llm.chat_stream([{"role": "user", "content": "天气如何"}])
    ]

    assert calls == 2
    assert events[-1] == {"type": "done", "content": "天气正常", "tool_calls": []}


@pytest.mark.asyncio
async def test_stream_forwards_provider_usage_in_done_event(monkeypatch):
    class Completions:
        async def create(self, **_kwargs):
            return _UsageStream()

    monkeypatch.setattr(
        llm,
        "_async_client",
        SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )

    events = [event async for event in llm.chat_stream([])]

    assert events[-1]["token_usage"] == {
        "prompt_tokens": 120,
        "completion_tokens": 18,
        "total_tokens": 138,
        "cached_tokens": 32,
    }


def test_provider_502_uses_friendly_message_after_retries() -> None:
    response = httpx.Response(502, request=httpx.Request("POST", "https://llm.test"))
    provider_error = InternalServerError("upstream unavailable", response=response, body=None)

    assert llm._is_retryable(provider_error)
    assert "HTTP 502" in llm._stream_error_message(provider_error)
