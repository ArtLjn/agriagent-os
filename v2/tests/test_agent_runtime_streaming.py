"""Agent Runtime 的 Registry、并行 Tool 和终态收口测试。"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from agent.config import settings
from agent.core import react
from agent.core.turn import StopReason, Turn, TurnPhase
from agent.infra import sse, turn_store
from agent.infra import trace as trace_infra
from agent.skills.base import McpSkill, OperationSkill, Skill, SkillResult
from agent.skills.registry import SkillRegistry, SkillRegistryError


class _ReadSkill(Skill):
    def __init__(self, name: str, delay: float = 0.0, error: str | None = None) -> None:
        self._meta = {
            "name": name,
            "description": name,
            "risk_level": "read",
            "execution": {"mode": "parallel_safe"},
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
        self.delay = delay
        self.error = error

    async def execute(self, params: dict, ctx) -> SkillResult:
        await asyncio.sleep(self.delay)
        if self.error:
            return SkillResult(error=self.error)
        return SkillResult(data={"skill": self.name})


def test_skill_registry_indexes_and_rejects_duplicate_names() -> None:
    first = _ReadSkill("first")
    registry = SkillRegistry.from_skills([first])

    assert registry.get("first") is first
    assert registry.require("first") is first
    assert registry.exposed_tools()[0]["function"]["name"] == "first"

    with pytest.raises(SkillRegistryError, match="duplicate_skill_name"):
        SkillRegistry.from_skills([first, _ReadSkill("first")])


def test_skill_registry_rejects_invalid_schema_with_context() -> None:
    skill = _ReadSkill("bad-schema")
    skill._meta["parameters"] = {
        "type": "object",
        "properties": {},
        "required": ["missing"],
    }

    with pytest.raises(SkillRegistryError, match="invalid_skill_schema.*bad-schema"):
        SkillRegistry.from_skills([skill])


def test_skill_registry_rejects_mcp_skill_without_tool_name() -> None:
    skill = McpSkill()
    skill._meta = {
        "name": "missing-mcp-tool",
        "description": "invalid",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }

    with pytest.raises(SkillRegistryError, match="mcp_tool_missing.*missing-mcp-tool"):
        SkillRegistry.from_skills([skill])


def test_parallel_safe_requires_explicit_read_only_capability() -> None:
    default_skill = Skill()
    default_skill._meta = {
        "name": "default-serial",
        "description": "默认串行",
        "risk_level": "read",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }
    assert default_skill.parallel_safe is False

    write_skill = _ReadSkill("parallel-write")
    write_skill._meta["risk_level"] = "write_confirm"
    with pytest.raises(SkillRegistryError, match="parallel_write_forbidden"):
        SkillRegistry.from_skills([write_skill])


def test_operation_execution_policy_overrides_aggregate_defaults() -> None:
    source = _ReadSkill("aggregate")
    source._meta["execution"] = {"mode": "serial"}
    source._meta["operations"] = {
        "query": {
            "tool_name": "query_aggregate",
            "description": "查询聚合结果",
            "risk_level": "read",
            "execution": {"mode": "parallel_safe", "max_concurrency": 3},
            "parameters": [],
            "required": [],
        }
    }

    operation = OperationSkill(source, "query")

    assert operation.execution_mode == "parallel_safe"
    assert operation.max_concurrency == 3
    assert operation.parallel_safe is True


def test_runtime_keeps_registry_as_the_skill_lookup(monkeypatch) -> None:
    skill = _ReadSkill("runtime-lookup")
    monkeypatch.setattr(react.skill_loader, "load_all", lambda: [skill])
    monkeypatch.setattr(react.memory, "snapshot", lambda _key: {})
    monkeypatch.setattr(react.context, "build_initial_messages", lambda *_args: [])

    registry, _tools, lookup, _tracker, _plan_box = react._setup_turn_runtime(
        Turn(user_input="验证注册表")
    )

    assert lookup is registry
    assert "runtime-lookup" in registry
    assert registry.get("runtime-lookup") is skill


def test_turn_records_structured_error_without_breaking_legacy_fields() -> None:
    turn = Turn(user_input="测试错误契约")

    details = turn.record_error(
        "tool_timeout",
        "业务查询超时",
        phase=TurnPhase.TOOL_EXECUTING,
        tool_name="get_weather",
        retryable=True,
        attempt=2,
        stop_reason=StopReason.TOOL_FAILED,
    )

    assert turn.status == "failed"
    assert turn.error == "tool_timeout"
    assert turn.error_code == "tool_timeout"
    assert turn.error_message == "业务查询超时"
    assert turn.phase == TurnPhase.TERMINAL
    assert turn.stop_reason == StopReason.TOOL_FAILED
    assert details == {
        "code": "tool_timeout",
        "message": "业务查询超时",
        "phase": "tool_executing",
        "tool_name": "get_weather",
        "retryable": True,
        "attempt": 2,
    }
    assert turn.snapshot()["error_details"] == details


def test_sse_error_and_observation_keep_structured_error_context() -> None:
    error = sse.error_event(
        "业务查询超时",
        "tool_timeout",
        phase="tool_executing",
        tool_name="get_weather",
        retryable=True,
        attempt=2,
    )
    observation = sse.observation(
        "get_weather",
        None,
        error="业务查询超时",
        error_info=error["data"],
    )

    assert error["data"]["retryable"] is True
    assert error["data"]["attempt"] == 2
    assert observation["data"]["error_info"]["code"] == "tool_timeout"


def test_done_is_the_only_terminal_event_marker() -> None:
    assert turn_store._TERMINAL_EVENTS == {"done"}


def test_trace_id_is_stable_and_request_id_remains_compatible() -> None:
    first = trace_infra.init_trace(turn_id="turn-trace-1")
    trace_infra.clear_trace()
    second = trace_infra.init_trace(turn_id="turn-trace-1")

    try:
        assert first.trace_id == "trace_turn-trace-1"
        assert second.trace_id == first.trace_id
        assert first.request_id == first.trace_id
        assert second.request_id == second.trace_id
    finally:
        trace_infra.clear_trace()


def test_record_event_reports_not_yet_persisted() -> None:
    trace_infra.collector._event_queue.clear()  # type: ignore[attr-defined]
    result = trace_infra.record_event(
        {
            "event_id": "evt-1",
            "trace_id": "trace-turn-1",
            "turn_id": "turn-1",
            "conversation_id": "conversation-1",
            "type": "started",
            "seq": 1,
            "terminal": False,
        }
    )

    assert result == {
        "accepted": True,
        "persisted": False,
        "status": "not_yet_persisted",
        "storage": "traceEvents",
    }
    trace_infra.collector._event_queue.clear()  # type: ignore[attr-defined]


class _EnvelopeRedis:
    def __init__(self) -> None:
        self.state = {
            "trace_id": "trace_turn-envelope",
            "request_id": "trace_turn-envelope",
            "conversation_id": "conversation-envelope",
        }
        self.sequence = 0
        self.rows: list[tuple[str, dict[str, str]]] = []

    async def hsetnx(self, _key: str, field: str, value: str) -> bool:
        if field in self.state:
            return False
        self.state[field] = value
        return True

    async def hget(self, _key: str, field: str) -> str | None:
        return self.state.get(field)

    async def hgetall(self, _key: str) -> dict[str, str]:
        return dict(self.state)

    async def incr(self, _key: str) -> int:
        self.sequence += 1
        return self.sequence

    async def xadd(self, _key: str, fields: dict[str, str], **_kwargs) -> str:
        stream_id = f"{fields['seq']}-0"
        self.rows.append((stream_id, dict(fields)))
        return stream_id

    async def xrange(self, _key: str, **_kwargs) -> list[tuple[str, dict[str, str]]]:
        return list(self.rows)

    async def expire(self, *_args) -> bool:
        return True


@pytest.mark.asyncio
async def test_publish_event_envelope_replays_with_stable_ids(monkeypatch) -> None:
    redis = _EnvelopeRedis()
    handed_off: list[dict] = []

    async def fake_update(_turn_id: str, **fields) -> None:
        redis.state.update({name: str(value) for name, value in fields.items()})

    monkeypatch.setattr(turn_store, "get_client", lambda: redis)
    monkeypatch.setattr(turn_store, "update_turn", fake_update)
    monkeypatch.setattr(turn_store, "record_event", handed_off.append)

    assert (
        await turn_store.publish_event(
            "turn-envelope",
            {
                "type": "started",
                "data": {"phase": "reasoning", "step": 2},
            },
        )
        == 1
    )
    assert (
        await turn_store.publish_event(
            "turn-envelope", {"type": "error", "data": {"code": "x"}}
        )
        == 2
    )
    assert (
        await turn_store.publish_event(
            "turn-envelope", {"type": "done", "data": {"status": "failed"}}
        )
        == 3
    )
    assert (
        await turn_store.publish_event(
            "turn-envelope", {"type": "done", "data": {"status": "failed"}}
        )
        == 3
    )

    events = await turn_store.read_events("turn-envelope")
    replay = await turn_store.read_events("turn-envelope", after_seq=1)
    assert [event["seq"] for event in events] == [1, 2, 3]
    assert [event["event_id"] for event in replay] == [
        event["event_id"] for event in events[1:]
    ]
    assert all(event["trace_id"] == "trace_turn-envelope" for event in events)
    assert all(event["conversation_id"] == "conversation-envelope" for event in events)
    assert [event["event_type"] for event in events] == ["started", "error", "done"]
    assert [event["status_after"] for event in events] == [
        "running",
        "failed",
        "failed",
    ]
    assert [event["terminal"] for event in events] == [False, False, True]
    assert len({event["event_id"] for event in events}) == 3
    assert len(handed_off) == 3
    assert handed_off[-1]["event_id"] == events[-1]["event_id"]


def test_sse_event_includes_standard_event_id_line() -> None:
    payload = json.loads(
        sse.sse_event("started", {"seq": 1}, event_id="evt-1")
        .split("data: ", 1)[1]
        .strip()
    )
    assert "id: evt-1" in sse.sse_event("started", {"seq": 1}, event_id="evt-1")
    assert payload == {"seq": 1}


@pytest.mark.asyncio
async def test_read_only_tool_calls_run_in_parallel() -> None:
    slow = _ReadSkill("slow", delay=0.08)
    fast = _ReadSkill("fast", delay=0.01)
    turn = Turn(user_input="查询两个状态")
    tracker = react.verify.CallTracker()
    context = SimpleNamespace()
    calls = [
        {"id": "slow-call", "name": "slow", "arguments": {}},
        {"id": "fast-call", "name": "fast", "arguments": {}},
    ]

    started = time.monotonic()
    events = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=calls,
            rationale="并行查询",
            skill_index={"slow": slow, "fast": fast},
            skill_ctx=context,
            approval_waiter=lambda _: _approve(),
            turn=turn,
            tracker=tracker,
            plan_box={"plan": None},
        )
    ]
    elapsed = time.monotonic() - started

    assert elapsed < 0.14
    assert [event["type"] for event in events].count("action") == 2
    observations = [event for event in events if event["type"] == "observation"]
    assert [event["data"]["tool_name"] for event in observations] == ["fast", "slow"]
    assert [message["tool_call_id"] for message in turn.messages] == [
        "slow-call",
        "fast-call",
    ]
    started = [event for event in events if event["type"] == "tool_started"]
    finished = [event for event in events if event["type"] == "tool_finished"]
    assert {event["data"]["tool_call_id"] for event in started} == {
        "slow-call",
        "fast-call",
    }
    assert {event["data"]["tool_call_id"] for event in finished} == {
        "slow-call",
        "fast-call",
    }


@pytest.mark.asyncio
async def test_doom_loop_stops_before_next_llm_call_with_final_answer() -> None:
    turn = Turn(user_input="重复调用")
    tracker = react.verify.CallTracker()
    for _ in range(3):
        tracker.record("get_weather", {"location": "苏州"})

    events = [
        event
        async for event in react._run_single_reasoning_step(
            turn=turn,
            tools_schema=[],
            tracker=tracker,
            plan_box={"plan": None},
            skill_index={},
            skill_ctx=SimpleNamespace(),
            approval_waiter=_approve,
        )
    ]

    assert turn.status == "failed"
    assert turn.stop_reason == StopReason.DOOM_LOOP_DETECTED
    assert [event["type"] for event in events][-4:] == [
        "error",
        "final_answer_start",
        "final_answer_delta",
        "final_answer",
    ]
    assert not any(event["type"] == "context_usage" for event in events)


@pytest.mark.asyncio
async def test_long_running_skill_emits_heartbeat(monkeypatch) -> None:
    monkeypatch.setattr(react, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    skill = _ReadSkill("slow-heartbeat", delay=0.03)
    events = [
        event
        async for event in react._run_skill_call(
            turn=Turn(user_input="等待查询"),
            skill=skill,
            args={},
            skill_ctx=SimpleNamespace(),
            rationale="慢查询",
            state=react._SkillExecState(),
            tool_call_id="heartbeat-call",
        )
    ]

    heartbeats = [event for event in events if event["type"] == "heartbeat"]
    assert heartbeats
    assert heartbeats[0]["data"]["stage"] == "skill:slow-heartbeat"


@pytest.mark.asyncio
async def test_duplicate_tool_call_path_also_emits_doom_loop_final_answer() -> None:
    turn = Turn(user_input="重复工具")
    tracker = react.verify.CallTracker()
    for _ in range(3):
        tracker.record("query_workers", {})

    events = [
        event
        async for event in react._check_duplication(turn, tracker, "query_workers", {})
    ]

    assert turn.stop_reason == StopReason.DOOM_LOOP_DETECTED
    assert any(event["type"] == "doom_loop_warning" for event in events)
    assert events[-1]["type"] == "final_answer"


@pytest.mark.asyncio
async def test_serial_read_only_calls_do_not_run_in_parallel() -> None:
    first = _ReadSkill("serial-first", delay=0.05)
    second = _ReadSkill("serial-second", delay=0.05)
    first._meta["execution"] = {"mode": "serial"}
    second._meta["execution"] = {"mode": "serial"}
    calls = [
        {"id": "serial-1", "name": first.name, "arguments": {}},
        {"id": "serial-2", "name": second.name, "arguments": {}},
    ]

    started = time.monotonic()
    events = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=calls,
            rationale="显式串行",
            skill_index={first.name: first, second.name: second},
            skill_ctx=SimpleNamespace(),
            approval_waiter=_approve,
            turn=Turn(user_input="串行查询"),
            tracker=react.verify.CallTracker(),
            plan_box={"plan": None},
        )
    ]

    assert time.monotonic() - started >= 0.09
    assert [event["type"] for event in events].count("tool_started") == 2


@pytest.mark.asyncio
async def test_mixed_batch_reorders_parallel_and_serial_results() -> None:
    serial = _ReadSkill("serial-result")
    serial._meta["execution"] = {"mode": "serial"}
    parallel = _ReadSkill("parallel-result")
    turn = Turn(user_input="混合批次")

    _ = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=[
                {"id": "serial-call", "name": serial.name, "arguments": {}},
                {"id": "parallel-call", "name": parallel.name, "arguments": {}},
            ],
            rationale="混合调度",
            skill_index={serial.name: serial, parallel.name: parallel},
            skill_ctx=SimpleNamespace(),
            approval_waiter=_approve,
            turn=turn,
            tracker=react.verify.CallTracker(),
            plan_box={"plan": None},
        )
    ]

    assert [message["tool_call_id"] for message in turn.messages] == [
        "serial-call",
        "parallel-call",
    ]


@pytest.mark.asyncio
async def test_write_calls_and_hitl_are_serialized() -> None:
    first = _ReadSkill("write-first", delay=0.04)
    second = _ReadSkill("write-second", delay=0.04)
    first._meta["risk_level"] = "write_confirm"
    second._meta["risk_level"] = "write_confirm"
    active_approvals = 0
    max_active_approvals = 0

    async def approve_serially(_: str) -> tuple[bool, str]:
        nonlocal active_approvals, max_active_approvals
        active_approvals += 1
        max_active_approvals = max(max_active_approvals, active_approvals)
        await asyncio.sleep(0.01)
        active_approvals -= 1
        return True, "同意"

    calls = [
        {"id": "write-1", "name": first.name, "arguments": {}},
        {"id": "write-2", "name": second.name, "arguments": {}},
    ]
    events = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=calls,
            rationale="写入串行",
            skill_index={first.name: first, second.name: second},
            skill_ctx=SimpleNamespace(),
            approval_waiter=approve_serially,
            turn=Turn(user_input="串行写入"),
            tracker=react.verify.CallTracker(),
            plan_box={"plan": None},
        )
    ]

    assert max_active_approvals == 1
    assert [event["type"] for event in events].count("approval_required") == 2
    assert [event["type"] for event in events].count("tool_started") == 2


@pytest.mark.asyncio
async def test_invalid_or_duplicate_tool_call_id_stops_batch() -> None:
    skill = _ReadSkill("lookup")
    turn = Turn(user_input="无效调用")
    events = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=[
                {"id": "same", "name": skill.name, "arguments": {}},
                {"id": "same", "name": skill.name, "arguments": {}},
            ],
            rationale="调用身份校验",
            skill_index={skill.name: skill},
            skill_ctx=SimpleNamespace(),
            approval_waiter=_approve,
            turn=turn,
            tracker=react.verify.CallTracker(),
            plan_box={"plan": None},
        )
    ]

    assert [event["type"] for event in events] == ["error"]
    assert events[0]["data"]["code"] == "invalid_tool_call"
    assert turn.status == "failed"


@pytest.mark.asyncio
async def test_parallel_tool_calls_respect_single_turn_limit(monkeypatch) -> None:
    skills = [_ReadSkill(f"read-{index}", delay=0.05) for index in range(3)]
    calls = [
        {"id": f"call-{index}", "name": skill.name, "arguments": {}}
        for index, skill in enumerate(skills)
    ]
    monkeypatch.setattr(settings, "max_parallel_skills", 1)

    started = time.monotonic()
    _ = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=calls,
            rationale="串行上限",
            skill_index={skill.name: skill for skill in skills},
            skill_ctx=SimpleNamespace(),
            approval_waiter=lambda _: _approve(),
            turn=Turn(user_input="测试并发上限"),
            tracker=react.verify.CallTracker(),
            plan_box={"plan": None},
        )
    ]

    assert time.monotonic() - started >= 0.14


@pytest.mark.asyncio
async def test_parallel_tool_failure_does_not_cancel_other_results() -> None:
    failed = _ReadSkill("failed", delay=0.01, error="查询失败")
    succeeded = _ReadSkill("succeeded", delay=0.05)
    turn = Turn(user_input="查询并行结果")
    calls = [
        {"id": "failed-call", "name": "failed", "arguments": {}},
        {"id": "succeeded-call", "name": "succeeded", "arguments": {}},
    ]

    events = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=calls,
            rationale="失败隔离",
            skill_index={"failed": failed, "succeeded": succeeded},
            skill_ctx=SimpleNamespace(),
            approval_waiter=lambda _: _approve(),
            turn=turn,
            tracker=react.verify.CallTracker(),
            plan_box={"plan": None},
        )
    ]

    observations = [event for event in events if event["type"] == "observation"]
    assert [event["data"]["tool_name"] for event in observations] == [
        "failed",
        "succeeded",
    ]
    assert observations[0]["data"]["error"] == "查询失败"
    assert observations[1]["data"]["result"] == {"skill": "succeeded"}
    assert [message["tool_call_id"] for message in turn.messages] == [
        "failed-call",
        "succeeded-call",
    ]


@pytest.mark.asyncio
async def test_non_retryable_tool_error_stops_before_max_steps() -> None:
    failed = _ReadSkill("permanent-failure", error="参数无效")
    turn = Turn(user_input="触发不可重试错误")

    events = [
        event
        async for event in react._dispatch_tool_calls(
            tool_calls=[{"id": "failed-call", "name": failed.name, "arguments": {}}],
            rationale="错误收口",
            skill_index={failed.name: failed},
            skill_ctx=SimpleNamespace(),
            approval_waiter=_approve,
            turn=turn,
            tracker=react.verify.CallTracker(),
            plan_box={"plan": None},
        )
    ]

    assert turn.stop_reason == StopReason.TOOL_FAILED
    assert turn.error != "max_steps_reached"
    assert turn.final_answer
    assert [event["type"] for event in events][-4:] == [
        "error",
        "final_answer_start",
        "final_answer_delta",
        "final_answer",
    ]


def test_changed_observation_does_not_trigger_doom_loop() -> None:
    tracker = react.verify.CallTracker()
    tracker.record("query", {})
    tracker.record_observation("query", {}, {"count": 1})
    tracker.record("query", {})
    tracker.record_observation("query", {}, {"count": 2})
    tracker.record("query", {})

    assert react.verify.detect_doom_loop(tracker.calls) is None


@pytest.mark.asyncio
async def test_approval_rejection_records_structured_stop_reason() -> None:
    skill = _ReadSkill("write-operation")
    skill._meta["risk_level"] = "write_confirm"
    turn = Turn(user_input="拒绝写操作")

    events = [
        event
        async for event in react._apply_approval_gate(
            turn=turn,
            skill=skill,
            args={},
            rationale="需要用户确认",
            approval_waiter=_reject,
            tool_call_id="write-call",
        )
    ]

    assert events[-1]["type"] == "approval_result"
    assert turn.status == "rejected"
    assert turn.stop_reason == StopReason.APPROVAL_REJECTED
    assert turn.phase == TurnPhase.TERMINAL
    assert turn.error_code == "approval_rejected"


async def _approve(_: str) -> tuple[bool, str]:
    return True, "同意"


async def _reject(_: str) -> tuple[bool, str]:
    return False, "用户拒绝"


@pytest.mark.asyncio
async def test_llm_stream_forwards_deltas_and_final_result(monkeypatch) -> None:
    async def fake_stream(messages, tools):
        yield {
            "type": "retrying",
            "data": {"code": "llm_retrying", "attempt": 1, "delay_ms": 1000},
        }
        yield {"type": "text", "delta": "正在查询"}
        yield {
            "type": "tool_call",
            "id": "status-call",
            "name": "get_status",
            "arguments_delta": "{}",
            "index": 0,
        }
        yield {"type": "done", "tool_calls": []}

    monkeypatch.setattr(react, "chat_stream", fake_stream)
    items = [item async for item in react._call_llm_stream([], [])]

    assert items[0] == {
        "type": "retrying",
        "data": {"code": "llm_retrying", "attempt": 1, "delay_ms": 1000},
    }
    assert items[1] == {
        "type": "assistant_delta",
        "data": {"delta": "正在查询"},
    }
    assert items[2]["type"] == "tool_call_delta"
    assert items[2]["data"] == {
        "tool_call_id": "status-call",
        "name": "get_status",
        "index": 0,
        "arguments_delta": "{}",
    }
    assert isinstance(items[-1], react._LlmResult)


@pytest.mark.asyncio
async def test_max_steps_emits_user_visible_terminal_answer() -> None:
    turn = Turn(user_input="无法完成的任务")
    events = [event async for event in react._finalize_turn(turn)]

    assert turn.status == "failed"
    assert turn.error == "max_steps_reached"
    assert turn.stop_reason == StopReason.STEP_BUDGET_EXHAUSTED
    assert turn.phase == TurnPhase.TERMINAL
    assert any(event["type"] == "error" for event in events)
    assert any(event["type"] == "final_answer" for event in events)
    assert turn.final_answer


@pytest.mark.asyncio
async def test_final_answer_emits_incremental_and_complete_events() -> None:
    turn = Turn(user_input="正常完成")

    events = [
        event
        async for event in react._emit_final_answer(
            turn, "最终答复", None, react.verify.CallTracker()
        )
    ]

    assert [event["type"] for event in events][-3:] == [
        "final_answer_start",
        "final_answer_delta",
        "final_answer",
    ]
    assert events[-2]["data"] == {"delta": "最终答复"}


@pytest.mark.asyncio
async def test_setup_failure_still_emits_terminal_events(monkeypatch) -> None:
    monkeypatch.setattr(
        react,
        "_setup_turn_runtime",
        lambda turn: (_ for _ in ()).throw(RuntimeError("registry invalid")),
    )
    turn = Turn(user_input="初始化失败")

    events = [event async for event in react.run_turn(turn, _approve)]

    assert turn.status == "failed"
    assert turn.stop_reason == StopReason.PIPELINE_CRASH
    assert [event["type"] for event in events][-2:] == ["error", "done"]
    assert events[-2]["data"]["code"] == "pipeline_crash"


@pytest.mark.asyncio
async def test_stream_timeout_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr(turn_store, "read_events", lambda *args: _empty_events())
    monkeypatch.setattr(turn_store, "get_turn", lambda *args: _active_turn())

    events = [
        event async for event in turn_store.stream_events("turn-1", max_wait_seconds=0)
    ]

    assert len(events) == 1
    assert events[0]["seq"] == 0
    assert events[0]["type"] == "stream_timeout"
    assert events[0]["data"] == {
        "code": "stream_timeout",
        "message": "事件流等待超时，Turn 仍未发布终态。",
        "turn_id": "turn-1",
    }
    assert events[0]["terminal"] is False
    assert events[0]["event_id"] == "evt_stream_timeout_turn-1_0"


@pytest.mark.asyncio
async def test_stream_replays_terminal_state_when_done_event_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(turn_store, "read_events", lambda *args: _empty_events())
    monkeypatch.setattr(turn_store, "get_client", lambda: None)
    monkeypatch.setattr(turn_store, "get_turn", lambda *args: _completed_turn())

    events = [
        event
        async for event in turn_store.stream_events(
            "turn-2", max_wait_seconds=0.1, poll_interval=0.01
        )
    ]

    assert events[0]["type"] == "done"
    assert events[0]["terminal"] is True
    assert events[0]["data"] == {"status": "completed", "turn_id": "turn-2"}


@pytest.mark.asyncio
async def test_stream_persists_missing_done_before_replay(monkeypatch) -> None:
    published = []

    async def fake_publish(turn_id, event):
        published.append((turn_id, event))
        return 4

    async def fake_read(turn_id, after_seq):
        if published and after_seq < 4:
            return [
                {
                    "seq": 4,
                    "type": "done",
                    "data": {"status": "completed", "turn_id": turn_id},
                    "terminal": True,
                }
            ]
        return []

    monkeypatch.setattr(turn_store, "get_client", lambda: object())
    monkeypatch.setattr(turn_store, "read_events", fake_read)
    monkeypatch.setattr(turn_store, "publish_event", fake_publish)
    monkeypatch.setattr(turn_store, "get_turn", _completed_turn)

    events = [event async for event in turn_store.stream_events("turn-3")]

    assert published == [
        (
            "turn-3",
            {
                "type": "done",
                "data": {"status": "completed", "turn_id": "turn-3"},
            },
        )
    ]
    assert events[0]["seq"] == 4


async def _empty_events(*_args):
    return []


async def _active_turn(*_args):
    return {"status": "running"}


async def _completed_turn(*_args):
    return {"status": "completed"}
