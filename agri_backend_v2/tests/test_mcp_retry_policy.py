"""MCP 重试边界和工具异常结构化契约测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.domains.harness.runtime import engine as react
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.mcp import client as mcp_client
from agent.domains.harness.tools.context import SkillContext


class _FlakyClient:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def call_tool(self, _name: str, _arguments: dict) -> dict:
        self.calls += 1
        if self.calls <= self.failures:
            raise TimeoutError("temporary MCP transport failure")
        return {"status": "ok"}


@pytest.mark.asyncio
async def test_read_mcp_call_retries_transient_failure_once(monkeypatch) -> None:
    client = _FlakyClient(failures=1)
    records: list[dict] = []
    monkeypatch.setattr(
        mcp_client,
        "record",
        lambda **kwargs: records.append(kwargs),
    )
    monkeypatch.setattr(mcp_client, "_mcp_retry_delay", lambda _attempt: 0)

    result = await mcp_client.call_mcp_with_retry(
        client,
        "query_workers",
        {},
        risk_level="read",
    )

    assert result == {"status": "ok"}
    assert client.calls == 2
    assert [item["attempt"] for item in records] == [1, 2]
    assert all(item["node_type"] == "mcp_call" for item in records)
    assert all(item["layer"] == "resource" for item in records)


@pytest.mark.asyncio
async def test_write_mcp_call_does_not_retry_without_explicit_contract(
    monkeypatch,
) -> None:
    client = _FlakyClient(failures=1)
    monkeypatch.setattr(mcp_client, "_mcp_retry_delay", lambda _attempt: 0)

    with pytest.raises(mcp_client.McpCallError) as exc_info:
        await mcp_client.call_mcp_with_retry(
            client,
            "create_worker",
            {"name": "张三"},
            risk_level="write_confirm",
        )

    assert client.calls == 1
    assert exc_info.value.attempt == 0
    assert exc_info.value.classified.category.value == "transient"


@pytest.mark.asyncio
async def test_idempotent_write_can_retry_only_when_explicitly_enabled(
    monkeypatch,
) -> None:
    client = _FlakyClient(failures=1)
    monkeypatch.setattr(mcp_client, "_mcp_retry_delay", lambda _attempt: 0)

    result = await mcp_client.call_mcp_with_retry(
        client,
        "commit_plan",
        {"plan_id": "plan-1"},
        risk_level="write_confirm",
        idempotency_key="idem-1",
        allow_idempotent_write_retry=True,
    )

    assert result == {"status": "ok"}
    assert client.calls == 2


class _RetryableResultClient:
    def __init__(self) -> None:
        self.calls = 0

    async def call_tool(self, _name: str, _arguments: dict) -> dict:
        self.calls += 1
        return {"error": "busy", "message": "服务繁忙", "retryable": True}


@pytest.mark.asyncio
async def test_exhausted_business_retry_keeps_attempt_and_category(monkeypatch) -> None:
    client = _RetryableResultClient()
    monkeypatch.setattr(mcp_client, "_mcp_retry_delay", lambda _attempt: 0)

    result = await mcp_client.call_mcp_with_retry(
        client,
        "query_workers",
        {},
        risk_level="read",
    )

    assert client.calls == 2
    assert result["attempt"] == 1
    assert result["category"] == "transient"


@pytest.mark.asyncio
async def test_skill_context_uses_same_mcp_retry_policy(monkeypatch) -> None:
    client = _FlakyClient(failures=1)
    monkeypatch.setattr(mcp_client, "_mcp_retry_delay", lambda _attempt: 0)
    ctx = SkillContext(business_client=client, turn=Turn(user_input="查询工人"))

    result = await ctx.call_mcp_tool("query_workers", {}, risk_level="read")

    assert result["status"] == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_mcp_failure_observation_keeps_category_and_attempt() -> None:
    class FailedSkill:
        name = "query_workers"

        async def execute(self, _args, _ctx):
            raise mcp_client.McpCallError(
                "query_workers",
                mcp_client.classify_exception(TimeoutError("temporary")),
                1,
            )

    events = [
        event
        async for event in react._run_skill_call(
            turn=Turn(user_input="查询工人"),
            skill=FailedSkill(),
            args={},
            skill_ctx=SimpleNamespace(),
            rationale="查询",
            state=react._SkillExecState(),
            tool_call_id="call-1",
        )
    ]

    finished = next(event for event in events if event["type"] == "tool_finished")
    observation = next(event for event in events if event["type"] == "observation")
    assert finished["data"]["error"]["code"] == "mcp_llm_transient_error"
    assert finished["data"]["error"]["category"] == "transient"
    assert finished["data"]["error"]["attempt"] == 1
    assert observation["data"]["error_info"]["retryable"] is True
