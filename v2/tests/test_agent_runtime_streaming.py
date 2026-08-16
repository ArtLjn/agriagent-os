"""Agent Runtime 的 Registry、并行 Tool 和终态收口测试。"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from agent.config import settings
from agent.core import react
from agent.core.turn import StopReason, Turn, TurnPhase
from agent.infra import sse, turn_store
from agent.skills.base import Skill, SkillResult
from agent.skills.registry import SkillRegistry


class _ReadSkill(Skill):
    def __init__(self, name: str, delay: float = 0.0, error: str | None = None) -> None:
        self._meta = {
            "name": name,
            "description": name,
            "risk_level": "read",
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

    with pytest.raises(ValueError, match="duplicate skill name"):
        SkillRegistry.from_skills([first, _ReadSkill("first")])


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

    assert events == [
        {
            "seq": 0,
            "type": "stream_timeout",
            "data": {
                "code": "stream_timeout",
                "message": "事件流等待超时，Turn 仍未发布终态。",
                "turn_id": "turn-1",
            },
            "terminal": False,
        }
    ]


@pytest.mark.asyncio
async def test_stream_replays_terminal_state_when_done_event_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(turn_store, "read_events", lambda *args: _empty_events())
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


async def _empty_events(*_args):
    return []


async def _active_turn(*_args):
    return {"status": "running"}


async def _completed_turn(*_args):
    return {"status": "completed"}
