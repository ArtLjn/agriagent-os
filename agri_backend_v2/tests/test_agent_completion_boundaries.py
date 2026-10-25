"""业务提交、个人记忆核验与只读续查的跨边界回归，不访问真实业务服务。"""

import pytest
from test_agent_step_budget import _answer, _ReadSkill, _runtime, _tool, _WorkOrderSkill

from agent.domains.harness.memory import tools as memory_tools
from agent.domains.harness.runtime import engine as react
from agent.domains.harness.runtime.turn import StopReason, Turn
from agent.domains.harness.tools import loader as skill_loader


@pytest.fixture
def memo_skill():
    skill = _WorkOrderSkill()
    skill._meta.update(name="create_memo", description="保存备忘录，不设置定时通知")
    return skill


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup_weather", [False, True])
async def test_memo_commit_and_optional_weather_do_not_become_personal_memory(
    monkeypatch, memory_assessment_stub, memo_skill, lookup_weather
):
    weather = _ReadSkill()
    weather._meta["name"] = "get_weather"
    reply = "备忘录已保存，编号 42，未设置定时通知。"
    responses = [_tool(memo_skill.name, "memo-1")]
    if lookup_weather:
        responses.append(_tool(weather.name, "weather-1"))
    responses.append(react._LlmResult(full_content=reply))
    _, calls, approvals, approve = _runtime(
        monkeypatch, responses, skills=[memo_skill, weather]
    )
    turn = Turn(
        user_input="提醒我明天早上打药" + ("，并查一下天气" if lookup_weather else ""),
        max_steps=len(responses),
    )
    events = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "completed"
    assert turn.final_answer == reply
    assert memo_skill.calls == len(approvals) == 1
    assert weather.calls == int(lookup_weather)
    assert len(calls) == len(responses)
    assert sum(event["type"] == "final_answer" for event in events) == 1
    assert sum(event["type"] == "done" for event in events) == 1
    assert memory_assessment_stub.call_args.kwargs["business_operations"] == [
        {
            "tool_name": "create_memo",
            "description": memo_skill.description,
            "record_id": 42,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["personal_request", "unavailable"])
@pytest.mark.parametrize("max_steps", [1, 2, 3])
async def test_memory_guard_cannot_deny_commit_or_restart_finalization(
    monkeypatch, memory_assessment_stub, memo_skill, failure, max_steps
):
    if failure == "unavailable":
        memory_assessment_stub.side_effect = TimeoutError("语义核验超时")
    else:
        memory_assessment_stub.return_value = memory_tools.MemoryAssessment(
            requests_persistence=True, claims_persistence=True
        )
    responses = [_tool(memo_skill.name, "memo-1")]
    if max_steps == 1:
        responses.append(_answer(evidence=["memo-1"]))
    else:
        responses.extend(
            [react._LlmResult(full_content="备忘录已保存，我也记住你的长期偏好了。")]
            * (max_steps - 1)
        )
    _, calls, approvals, approve = _runtime(monkeypatch, responses, skills=[memo_skill])
    turn = Turn(user_input="记下明天打药，以后一直叫我老李", max_steps=max_steps)
    events = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "failed"
    assert turn.stop_reason == StopReason.LLM_FAILED
    assert not turn.finalization_pending
    assert memo_skill.calls == len(approvals) == 1
    assert len(calls) == len(responses)
    assert turn.step_count <= turn.max_steps
    assert "42" in turn.final_answer
    assert "无需重复创建" in turn.final_answer
    assert "没有实际执行写入" not in turn.final_answer
    assert "个人长期记忆" in turn.final_answer
    assert any(
        event["type"] == "error"
        and event["data"]["code"] == "memory_completion_unverified"
        for event in events
    )
    assert sum(event["type"] == "final_answer" for event in events) == 1
    assert sum(event["type"] == "done" for event in events) == 1
    if max_steps == 3:
        corrections = [
            msg["content"] for msg in calls[-1]["messages"] if msg["role"] == "system"
        ]
        assert any("不得重复执行" in msg for msg in corrections)
        assert not any("本轮没有任何写工具" in msg for msg in corrections)
    assert sum(event["type"] == "step.completed" for event in events) == turn.step_count


@pytest.mark.asyncio
async def test_model_failure_after_memo_preserves_commit(monkeypatch, memo_skill):
    _, calls, approvals, approve = _runtime(
        monkeypatch,
        [_tool(memo_skill.name, "memo-1"), RuntimeError("模型不可用")],
        skills=[memo_skill],
    )
    turn = Turn(user_input="记下明天打药，并查询天气", max_steps=3)
    events = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "terminated"
    assert turn.stop_reason == StopReason.LLM_FAILED
    assert "42" in turn.final_answer
    assert "无需重复执行" in turn.final_answer
    assert "重新发送" not in turn.final_answer
    assert memo_skill.calls == len(approvals) == 1
    assert len(calls) == 2
    assert sum(event["type"] == "step.completed" for event in events) == turn.step_count
    assert sum(event["type"] == "final_answer" for event in events) == 1
    assert sum(event["type"] == "done" for event in events) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_result",
    [
        {"error": "业务失败"},
        {"success": False},
        {"status": "pending"},
        {"status": "ready"},
        {"status": "failed"},
        {"status": "needs_information"},
    ],
)
async def test_read_fallback_keeps_only_successful_evidence(invalid_result):
    turn = Turn(user_input="查询农场和天气")
    turn.emit(
        "tool_finished", {"tool_call_id": "read-1", "result": {"active_cycles": 4}}
    )
    turn.emit(
        "tool_finished",
        {"tool_call_id": "read-2", "result": {**invalid_result, "marker": "无效结果"}},
    )
    events = [
        event
        async for event in react.finalization.finalize_turn(
            turn, reason=StopReason.LLM_FAILED
        )
    ]
    assert turn.status == "terminated"
    assert '"active_cycles": 4' in turn.final_answer
    assert "无效结果" not in turn.final_answer
    assert "步数上限" not in events[-1]["data"]["message"]
    assert sum(event["type"] == "final_answer" for event in events) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", ["get_farm_status", "get_farm_review", "get_payment_overview"]
)
async def test_shipped_overviews_allow_followup_query(monkeypatch, name):
    # 使用发布目录的真实元数据，执行仍用内存替身，防止再次加回强制收尾标记。
    source = next(skill for skill in skill_loader.load_all() if skill.name == name)
    overview, weather = _ReadSkill(), _ReadSkill()
    overview._meta = source._meta.copy()
    weather._meta["name"] = "get_weather"
    _, calls, _, approve = _runtime(
        monkeypatch,
        [
            _tool(name, "overview-1"),
            _tool(weather.name, "weather-1"),
            react._LlmResult(full_content="查询已完成"),
        ],
        skills=[overview, weather],
    )
    turn = Turn(user_input="查看概览，再查询明天的天气", max_steps=3)
    events = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "completed"
    assert overview.calls == weather.calls == 1
    assert calls[1]["tools"]
    assert len(calls) == 3
    assert not turn.committed_operations
    assert sum(event["type"] == "done" for event in events) == 1
