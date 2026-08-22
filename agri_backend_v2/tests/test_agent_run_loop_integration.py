"""Agent 路由到 Worker/ReAct 的可执行集成契约测试。

测试边界：FastAPI chat/approve 路由、Worker `_run_turn` 和 ReAct 事件收口使用真实
实现；Redis、LLM、Business MCP、审批等待和 trace 持久化由本文件内的确定性替身提供。
这证明的是进程内协议与事件顺序，不代表真实 Redis/MCP/LLM 或数据库已通过 live smoke。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from agent.api import approve, chat
from agent.domains.harness.runtime import engine as react
from agent.domains.harness.runtime.turn import Turn
from agent.application import worker
from agent.platforms.persistence.redis.coordination import TurnAdmission, TurnLease
from agent.domains.harness.tools.base import Skill, SkillResult
from agent.domains.harness.tools.registry import SkillRegistry
from agent.bootstrap.app import app


TEST_IDENTITY = {
    "user_id": "integration-user",
    "farm_uid": "integration-farm",
    "farm_id": 7,
    "role": "user",
    "scope": "farm:read farm:write",
    "token_id": "integration-token",
    "agent_token": "agent-service-test",
}


class _FakeBusinessClient:
    """代替 FastMCP，只保留业务调用计数和结构化返回。"""

    def __init__(self, calls: list[tuple[str, dict[str, Any]]]) -> None:
        self.calls = calls

    async def __aenter__(self) -> _FakeBusinessClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, dict(arguments)))
        return {"status": "committed", "tool": name, "arguments": arguments}


class _FakeSkill(Skill):
    def __init__(self, name: str, *, write: bool = False) -> None:
        self._meta = {
            "name": name,
            "description": f"测试工具 {name}",
            "risk_level": "write_confirm" if write else "read",
            "finalize_after_success": write,
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": [],
            },
        }

    async def execute(self, params: dict[str, Any], ctx) -> SkillResult:
        result = await ctx.business_client.call_tool(self.name, params)
        return SkillResult(data=result)


@dataclass
class _FakeStore:
    """内存版 Redis/Event Store，保留 seq、幂等和审批状态语义。"""

    turns: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    idempotency: dict[str, dict[str, str]] = field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    dispatches: list[str] = field(default_factory=list)
    worker_runs: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    business_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    approval_required: asyncio.Event = field(default_factory=asyncio.Event)
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    async def claim_idempotency(
        self, **kwargs: str
    ) -> tuple[bool, dict[str, str] | None]:
        request_id = kwargs["client_request_id"]
        previous = self.idempotency.get(request_id)
        if previous is not None:
            return False, previous
        self.idempotency[request_id] = {
            "turn_id": kwargs["turn_id"],
            "request_fingerprint": kwargs["request_fingerprint"],
        }
        return True, None

    async def admit_turn(self, **kwargs: str) -> TurnAdmission:
        turn_id = kwargs["turn_id"]
        lease = TurnLease(
            turn_id=turn_id,
            scope_hash="fake-scope",
            user_scope_hash="fake-user-scope",
            token=f"lease-{turn_id}",
        )
        return TurnAdmission(lease=lease)

    async def save_turn(self, turn: Turn, **kwargs: Any) -> None:
        self.turns[turn.turn_id] = {
            "turn_id": turn.turn_id,
            "conversation_id": turn.conversation_id,
            "memory_key": turn.memory_key,
            "user_input": turn.user_input,
            "user_id": turn.user_id,
            "farm_uid": turn.farm_uid,
            "farm_id": str(turn.farm_id),
            "role": turn.role,
            "token_id": turn.token_id,
            "scope": turn.scope,
            "conversation_revision": turn.conversation_revision,
            "summary_revision": turn.summary_revision,
            "reset_generation": turn.reset_generation,
            "source_status": turn.context_source_status,
            "context_source_status": turn.context_source_status,
            "scope_hash": kwargs["scope_hash"],
            "lease_token": kwargs["lease_token"],
            "status": "accepted",
        }

    async def update_turn(self, turn_id: str, **fields: Any) -> None:
        self.turns[turn_id].update(fields)

    async def get_turn(self, turn_id: str) -> dict[str, Any] | None:
        state = self.turns.get(turn_id)
        return dict(state) if state else None

    async def append_message(self, **message: Any) -> str:
        self.messages.append(message)
        return f"message-{len(self.messages)}"

    async def publish_event(self, turn_id: str, event: dict[str, Any]) -> int:
        events = self.events.setdefault(turn_id, [])
        if event["type"] == "done" and any(item["type"] == "done" for item in events):
            return next(item["seq"] for item in events if item["type"] == "done")
        item = {
            "seq": len(events) + 1,
            "event_id": f"evt_{turn_id}_{len(events) + 1}",
            "type": event["type"],
            "data": dict(event.get("data") or {}),
            "terminal": event["type"] == "done",
        }
        state = self.turns[turn_id]
        for metadata_field in (
            "conversation_revision",
            "summary_revision",
            "reset_generation",
        ):
            item[metadata_field] = int(state.get(metadata_field, 0) or 0)
        item["source_status"] = str(
            state.get("source_status")
            or state.get("context_source_status")
            or "empty"
        )
        item["context_source_status"] = item["source_status"]
        item["data"].update(
            {
                "conversation_revision": item["conversation_revision"],
                "summary_revision": item["summary_revision"],
                "reset_generation": item["reset_generation"],
                "source_status": item["source_status"],
                "context_source_status": item["context_source_status"],
            }
        )
        events.append(item)
        async with self.changed:
            self.changed.notify_all()
        return item["seq"]

    async def stream_events(
        self, turn_id: str, *, after_seq: int = 0
    ) -> AsyncGenerator[dict[str, Any], None]:
        next_seq = after_seq
        while True:
            pending = [
                event
                for event in self.events.get(turn_id, [])
                if event["seq"] > next_seq
            ]
            if pending:
                for event in pending:
                    next_seq = event["seq"]
                    yield dict(event)
                    if event["terminal"]:
                        return
                continue
            async with self.changed:
                await self.changed.wait()

    async def dispatch_turn(self, turn_id: str) -> str:
        self.dispatches.append(turn_id)
        state = await self.get_turn(turn_id)
        assert state is not None
        task = asyncio.create_task(
            worker._run_turn(worker._turn_from_state(state), state)
        )
        task.add_done_callback(
            lambda done: done.exception() if not done.cancelled() else None
        )
        return f"dispatch-{len(self.dispatches)}"

    async def create_approval(self, turn: Turn, event_data: dict[str, Any]) -> None:
        self.approvals[turn.turn_id] = {"status": "pending", **event_data}
        await self.update_turn(
            turn.turn_id,
            status="awaiting_approval",
            pending_approval=event_data,
        )
        self.approval_required.set()

    async def resolve_approval(self, turn_id: str, decision: bool, reason: str) -> bool:
        approval = self.approvals.get(turn_id)
        if not approval or approval.get("status") != "pending":
            return False
        approval.update(status="approved" if decision else "rejected", reason=reason)
        await self.update_turn(
            turn_id,
            status="running" if decision else "rejected",
            approval_decision=approval["status"],
        )
        async with self.changed:
            self.changed.notify_all()
        return True

    async def wait_approval(self, turn_id: str) -> tuple[bool, str]:
        while self.approvals[turn_id]["status"] == "pending":
            await asyncio.sleep(0)
        approval = self.approvals[turn_id]
        return approval["status"] == "approved", approval.get("reason", "")


@pytest.fixture
def fake_runtime(monkeypatch: pytest.MonkeyPatch) -> _FakeStore:
    store = _FakeStore()
    skill = _FakeSkill("fake_lookup")
    write_skill = _FakeSkill("fake_write", write=True)
    registry = SkillRegistry.from_skills([skill, write_skill])
    llm_mode = {"name": "read", "calls": 0}

    async def fake_llm(_messages, tools) -> AsyncGenerator[dict[str, Any], None]:
        llm_mode["calls"] += 1
        if llm_mode["name"] == "read" and llm_mode["calls"] == 1:
            yield {"type": "text", "delta": "开始查询"}
            yield {
                "type": "tool_call",
                "id": "lookup-call-1",
                "name": "fake_lookup",
                "arguments_delta": "{}",
                "index": 0,
            }
            yield {
                "type": "done",
                "tool_calls": [
                    {"id": "lookup-call-1", "name": "fake_lookup", "arguments": {}}
                ],
            }
            return
        if llm_mode["name"] == "write" and llm_mode["calls"] == 1:
            yield {
                "type": "tool_call",
                "id": "write-call-1",
                "name": "fake_write",
                "arguments_delta": json.dumps({"value": "approved"}),
                "index": 0,
            }
            yield {
                "type": "done",
                "tool_calls": [
                    {
                        "id": "write-call-1",
                        "name": "fake_write",
                        "arguments": {"value": "approved"},
                    }
                ],
            }
            return
        yield {
            "type": "text",
            "delta": "最终答复" if llm_mode["name"] == "read" else "写入完成",
        }
        yield {"type": "done", "tool_calls": []}

    def setup_runtime(_turn: Turn, **_kwargs: Any):
        return (
            registry,
            registry.exposed_tools(),
            registry.as_index(),
            react.verify.CallTracker(),
            {"plan": None},
        )

    class BusinessClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.client = _FakeBusinessClient(store.business_calls)

        async def __aenter__(self):
            return await self.client.__aenter__()

        async def __aexit__(self, *args: object) -> None:
            await self.client.__aexit__(*args)

    async def no_op(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def empty_session_view(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "conversation_id": "fake",
            "messages": [],
            "summary": None,
            "conversation_revision": 0,
            "summary_revision": 0,
            "reset_generation": 0,
            "source_status": "empty",
        }

    async def persisted_session_turn(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ready",
            "source_status": "empty",
            "conversation_revision": 1,
            "summary_revision": 0,
            "reset_generation": 0,
        }

    async def persisted_observation(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "ready", "source_status": "empty", "persisted": True}

    async def renew_until_done(_lease, stop: asyncio.Event) -> None:
        await stop.wait()

    monkeypatch.setattr(
        chat, "parse_identity", lambda _authorization: dict(TEST_IDENTITY)
    )
    monkeypatch.setattr(chat, "ensure_mcp_credentials", lambda: None)
    monkeypatch.setattr(chat, "claim_idempotency", store.claim_idempotency)
    monkeypatch.setattr(chat, "admit_turn", store.admit_turn)
    monkeypatch.setattr(chat, "save_turn", store.save_turn)
    monkeypatch.setattr(chat, "append_message", store.append_message)
    monkeypatch.setattr(chat, "publish_event", store.publish_event)
    monkeypatch.setattr(chat, "dispatch_turn", store.dispatch_turn)
    monkeypatch.setattr(chat, "get_turn", store.get_turn)
    monkeypatch.setattr(chat, "update_turn", store.update_turn)
    monkeypatch.setattr(chat, "stream_events", store.stream_events)

    monkeypatch.setattr(
        approve, "parse_identity", lambda _authorization: dict(TEST_IDENTITY)
    )
    monkeypatch.setattr(approve, "get_turn", store.get_turn)
    monkeypatch.setattr(approve, "resolve_approval", store.resolve_approval)

    monkeypatch.setattr(worker, "get_turn", store.get_turn)
    monkeypatch.setattr(worker, "mark_running", lambda _turn_id: _true())
    monkeypatch.setattr(worker, "inspect_turn_lease", lambda _lease: _owned())
    monkeypatch.setattr(worker, "update_turn", store.update_turn)
    monkeypatch.setattr(worker, "publish_event", store.publish_event)
    monkeypatch.setattr(worker, "create_approval", store.create_approval)
    monkeypatch.setattr(worker, "wait_approval", store.wait_approval)
    monkeypatch.setattr(worker, "append_message", store.append_message)
    monkeypatch.setattr(worker, "release_turn", no_op)
    monkeypatch.setattr(worker, "wake_conversation", no_op)
    monkeypatch.setattr(worker, "wake_global_queue", no_op)
    monkeypatch.setattr(worker, "renew_until_done", renew_until_done)
    monkeypatch.setattr(worker, "init_trace", lambda **_kwargs: None)
    monkeypatch.setattr(worker, "flush_now", no_op)
    monkeypatch.setattr(worker, "clear_trace", lambda: None)
    monkeypatch.setattr(worker, "trace_turn_outcome", lambda *_args: None)
    monkeypatch.setattr(worker, "run_turn", react.run_turn)
    monkeypatch.setattr(worker.memory, "get_session_view", empty_session_view)
    monkeypatch.setattr(
        worker.memory, "persist_session_turn", persisted_session_turn
    )
    monkeypatch.setattr(worker.memory, "observe", persisted_observation)

    monkeypatch.setattr(react, "_setup_turn_runtime", setup_runtime)
    monkeypatch.setattr(react, "_skill_router_enabled", lambda: False)
    monkeypatch.setattr(react, "chat_stream", fake_llm)
    monkeypatch.setattr(react, "BusinessClient", BusinessClient)
    monkeypatch.setattr(
        react, "create_delegation_token", lambda *_args, **_kwargs: "delegated"
    )
    monkeypatch.setattr(react, "trace_llm_call", lambda **_kwargs: None)
    monkeypatch.setattr(react, "trace_tool_call", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(react, "trace_commit_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(react, "log_event", lambda *_args, **_kwargs: None)

    store.llm_mode = llm_mode  # type: ignore[attr-defined]
    return store


async def _true() -> bool:
    return True


async def _owned() -> str:
    return "owned"


async def _post_chat(
    client: httpx.AsyncClient,
    *,
    request_id: str,
    conversation_id: str,
    after_seq: int = 0,
) -> httpx.Response:
    return await client.post(
        f"/api/v2/chat?after_seq={after_seq}",
        headers={"Authorization": "Bearer fake"},
        json={
            "message": "执行集成测试",
            "conversation_id": conversation_id,
            "client_request_id": request_id,
        },
    )


def _sse_events(response: httpx.Response) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        if not lines:
            continue
        event_id = next(
            (line.removeprefix("id: ") for line in lines if line.startswith("id:")),
            "",
        )
        event_type = next(
            line.removeprefix("event: ") for line in lines if line.startswith("event:")
        )
        data = next(
            line.removeprefix("data: ") for line in lines if line.startswith("data:")
        )
        events.append({"type": event_type, "sse_event_id": event_id, **json.loads(data)})
    return events


@pytest.mark.asyncio
async def test_chat_worker_normal_chain_and_after_seq_reconnect(
    fake_runtime: _FakeStore,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await _post_chat(
            client, request_id="normal-request", conversation_id="normal-conversation"
        )
        first = _sse_events(response)
        assert response.status_code == 200

        types = [event["type"] for event in first]
        assert types.count("progress") >= 2
        assert (
            types.index("progress")
            < types.index("final_answer")
            < types.index("done")
        )
        assert types.count("done") == 1
        assert first[-1]["type"] == "done"
        assert all(event["sse_event_id"] == event["event_id"] for event in first)
        assert all("trace_id" not in event for event in first)
        assert all("user_id" not in event for event in first)
        assert len(fake_runtime.business_calls) == 1
        assert len(fake_runtime.messages) == 2
        assert len(fake_runtime.dispatches) == 1
        assert len(fake_runtime.worker_runs) == 0

        observation_seq = max(event["seq"] for event in first if event["type"] == "progress")
        reconnected = await _post_chat(
            client,
            request_id="normal-request",
            conversation_id="normal-conversation",
            after_seq=observation_seq,
        )
        replay = _sse_events(reconnected)

    assert reconnected.status_code == 200
    assert replay
    assert all(event["seq"] > observation_seq for event in replay)
    assert [event["type"] for event in replay].count("done") == 1
    assert len(fake_runtime.business_calls) == 1
    assert len(fake_runtime.messages) == 2
    assert len(fake_runtime.dispatches) == 1
    assert len(fake_runtime.events[next(iter(fake_runtime.events))]) > len(first)


@pytest.mark.asyncio
async def test_chat_worker_hitl_approval_result_and_commit(
    fake_runtime: _FakeStore,
) -> None:
    fake_runtime.llm_mode["name"] = "write"  # type: ignore[attr-defined]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        chat_task = asyncio.create_task(
            _post_chat(
                client,
                request_id="approval-request",
                conversation_id="approval-conversation",
            )
        )
        await asyncio.wait_for(fake_runtime.approval_required.wait(), timeout=1)
        turn_id = next(iter(fake_runtime.turns))
        approval_response = await client.post(
            "/api/v2/approve",
            headers={"Authorization": "Bearer fake"},
            json={"turn_id": turn_id, "decision": True, "reason": "测试批准"},
        )
        response = await chat_task

    assert approval_response.status_code == 200
    events = _sse_events(response)
    types = [event["type"] for event in events]
    assert types.index("approval_required") < types.index("approval_result")
    assert types.index("approval_result") < types.index("operation_committed")
    assert (
        types.index("operation_committed")
        < types.index("final_answer")
        < types.index("done")
    )
    assert types.count("done") == 1
    assert len(fake_runtime.business_calls) == 1


@pytest.mark.asyncio
async def test_worker_exception_has_error_final_answer_and_unique_done(
    fake_runtime: _FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failed_run(
        _turn: Turn, _approval_waiter
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise RuntimeError("fake worker runtime failure")
        yield {}  # pragma: no cover - keeps this function an async generator

    monkeypatch.setattr(worker, "run_turn", failed_run)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await _post_chat(
            client, request_id="error-request", conversation_id="error-conversation"
        )

    events = _sse_events(response)
    types = [event["type"] for event in events]
    assert response.status_code == 200
    assert "error" in types
    assert types.index("error") < types.index("final_answer") < types.index("turn.failed") < types.index("done")
    assert types.count("done") == 1
    error = next(event for event in events if event["type"] == "error")
    assert "执行失败" in error["message"] or "fake worker runtime failure" in error["message"]
    final_answer = next(event for event in events if event["type"] == "final_answer")
    assert final_answer["text"]
