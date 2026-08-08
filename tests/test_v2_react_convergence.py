"""v2 Agent 收敛与 trace 结果测试。"""

import pytest

from agent.core import react
from agent.core.turn import Turn
from agent.skills.base import Skill, SkillResult

from agent.infra.trace.summary import build_trace_request_summary


class _OverviewSkill(Skill):
    _meta = {
        "name": "get_farm_status",
        "description": "查询农场概况",
        "risk_level": "read",
        "finalize_after_success": True,
        "parameters": {"type": "object", "properties": {}, "required": []},
    }

    async def execute(self, _params, _ctx):
        return SkillResult(data={"name": "默认农场"})


class _BusinessClient:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_overview_result_forces_next_llm_call_without_tools(monkeypatch) -> None:
    skill = _OverviewSkill()
    tool_schemas_seen: list[list[dict]] = []

    async def fake_chat_stream(_messages, tools):
        tool_schemas_seen.append(tools)
        if len(tool_schemas_seen) == 1:
            yield {
                "type": "done",
                "tool_calls": [
                    {"id": "call-1", "name": "get_farm_status", "arguments": {}}
                ],
            }
            return
        yield {"type": "text", "delta": "农场概况已获取。"}
        yield {"type": "done", "tool_calls": []}

    monkeypatch.setattr(react, "BusinessClient", _BusinessClient)
    monkeypatch.setattr(react.skill_loader, "load_all", lambda: [skill])
    monkeypatch.setattr(
        react.skill_loader,
        "to_openai_tools",
        lambda _skills: [skill.to_openai_tool()],
    )
    monkeypatch.setattr(react, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(react.memory, "snapshot", lambda _conversation_id: {})
    monkeypatch.setattr(react, "_persist_memory", lambda _turn: None)

    turn = Turn(user_input="你分析一下我的基本信息")

    events = [
        event
        async for event in react.run_turn(turn, lambda _turn_id: None)
    ]

    assert [event["data"]["tool_name"] for event in events if event["type"] == "action"] == [
        "get_farm_status"
    ]
    assert tool_schemas_seen[1] == []
    assert turn.status == "completed"
    assert turn.final_answer == "农场概况已获取。"


def test_failed_turn_trace_summary_is_not_success() -> None:
    summary = build_trace_request_summary(
        [
            {
                "request_id": "req-1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "step_index": 5,
                "node_type": "turn",
                "node_name": "outcome",
                "input_data": {"status": "failed"},
                "output_data": {
                    "status": "failed",
                    "error": {"code": "max_steps_reached"},
                },
                "duration_ms": 0,
                "status": "error",
                "error_message": "max_steps_reached",
            }
        ]
    )

    assert summary is not None
    assert summary["status"] == "failed"
    assert summary["status_reason"] == "max_steps_reached"
