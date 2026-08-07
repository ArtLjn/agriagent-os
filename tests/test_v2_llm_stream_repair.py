from types import SimpleNamespace

import pytest

from agent.infra import llm


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
