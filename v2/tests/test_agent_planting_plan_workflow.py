from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.core import react
from agent.core.turn import Turn
from agent.infra.trace import collector
from agent.skills import loader
from agent.skills.base import Skill, SkillResult


class _CommitSkill(Skill):
    _meta = {
        "name": "commit_planting_plan",
        "description": "提交种植计划",
        "risk_level": "write_confirm",
        "finalize_after_success": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }

    async def execute(self, params: dict, ctx) -> SkillResult:
        return SkillResult(
            data={
                "status": "committed",
                "template": {"id": 12, "name": "西瓜"},
                "cycle": {"id": 31, "name": "西瓜种植计划"},
                "planting_unit": {"id": 44, "name": "东棚", "area_mu": 5.0},
            }
        )


class _BusinessClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass


def _patch_react_runtime(
    monkeypatch: pytest.MonkeyPatch,
    fake_chat_stream,
) -> None:
    monkeypatch.setattr(react, "BusinessClient", _BusinessClient)
    monkeypatch.setattr(react, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(react.skill_loader, "load_all", lambda: [_CommitSkill()])
    monkeypatch.setattr(
        react.skill_loader,
        "to_openai_tools",
        lambda skills: [skills[0].to_openai_tool()],
    )
    monkeypatch.setattr(react.memory, "snapshot", lambda conversation_id: {})
    monkeypatch.setattr(react.memory, "save_messages", lambda *args: None)
    monkeypatch.setattr(react, "increment_step", lambda: None)
    monkeypatch.setattr(react, "trace_llm_call", lambda **kwargs: None)
    monkeypatch.setattr(react, "trace_tool_call", lambda *args, **kwargs: None)
    monkeypatch.setattr(react, "trace_commit_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        react.tokenizer,
        "compute_usage",
        lambda messages: SimpleNamespace(
            used=1,
            total=100,
            percent=1,
            level="ok",
        ),
    )
    monkeypatch.setattr(react.tokenizer, "must_compress", lambda usage: False)
    monkeypatch.setattr(react.tokenizer, "should_compress", lambda usage: False)


async def _approve(turn_id: str) -> tuple[bool, str]:
    return True, "同意"


def test_manage_planting_plan_projects_two_direct_mcp_tools() -> None:
    skill_dir = Path(loader.__file__).resolve().parent / "manage-planting-plan"
    source = loader._load_skill(skill_dir)
    assert source is not None
    operations = {skill.name: skill for skill in source.operation_skills()}

    assert operations["prepare_planting_plan"].mcp_tool == "prepare_planting_plan"
    commit = operations["commit_planting_plan"]
    assert commit.mcp_tool == "commit_planting_plan"
    assert commit.finalize_after_success is True
    assert commit._inject_operation is False


@pytest.mark.asyncio
async def test_committed_write_gets_finalization_round_beyond_max_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_chat_stream(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield {
                "type": "done",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "commit_planting_plan",
                        "arguments": {},
                    }
                ],
            }
            return
        assert tools == []
        yield {"type": "text", "delta": "种植计划已创建完成。"}
        yield {"type": "done", "tool_calls": []}

    _patch_react_runtime(monkeypatch, fake_chat_stream)

    turn = Turn(user_input="确认创建", max_steps=1)
    events = [event async for event in react.run_turn(turn, _approve)]
    event_types = [event["type"] for event in events]

    assert turn.status == "completed"
    assert turn.step_count == 2
    assert event_types.count("operation_committed") == 1
    assert event_types.count("final_answer") == 1
    assert not any(event.get("data", {}).get("code") == "max_steps" for event in events)


@pytest.mark.asyncio
async def test_committed_write_uses_structured_fallback_when_reply_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_chat_stream(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield {
                "type": "done",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "commit_planting_plan",
                        "arguments": {},
                    }
                ],
            }
            return
        yield {"type": "error", "message": "模型连接中断"}

    _patch_react_runtime(monkeypatch, fake_chat_stream)
    turn = Turn(user_input="确认创建", max_steps=1)
    events = [event async for event in react.run_turn(turn, _approve)]
    event_types = [event["type"] for event in events]

    assert turn.status == "completed"
    assert event_types.count("operation_committed") == 1
    assert event_types.count("write_committed_reply_failed") == 1
    assert event_types.count("final_answer") == 1
    assert "西瓜种植计划" in (turn.final_answer or "")


def test_frontend_records_final_answer_once() -> None:
    index_path = Path(__file__).resolve().parents[1] / "agent" / "static" / "index.html"
    source = index_path.read_text(encoding="utf-8")
    assert "type !== 'final_answer'" in source
    assert source.count("state.currentTurnEvents.push({ type, data:") == 2


def test_trace_distinguishes_committed_write_from_reply_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict] = []
    monkeypatch.setattr(
        collector,
        "record",
        lambda **kwargs: recorded.append(kwargs),
    )

    collector.trace_commit_state(
        {"status": "committed", "cycle": {"id": 31}},
        reply_generated=False,
    )

    assert recorded[0]["node_type"] == "commit_state"
    assert recorded[0]["output_data"]["business_committed"] is True
    assert recorded[0]["output_data"]["reply_generated"] is False
