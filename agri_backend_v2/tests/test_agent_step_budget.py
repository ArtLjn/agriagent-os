"""步数硬上限、审批写入与独立收尾的回归测试，不访问外部服务。"""

from __future__ import annotations

import asyncio
import json
import pytest

from agent.domains.harness.runtime import engine as react
from agent.domains.harness.runtime import finalization, planner
from agent.domains.harness.runtime.turn import StopReason, Turn
from agent.domains.harness.tools.base import Skill, SkillResult
from agent.domains.harness.tools.registry import SkillRegistry


class _WorkOrderSkill(Skill):
    """模拟普通写工具：无立即收尾标记，成功后还可继续登记工时。"""

    def __init__(self, *, error: str | None = None) -> None:
        self._meta = {
            "name": "create_work_order",
            "description": "创建农事作业单",
            "risk_level": "write_confirm",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
        self.calls = 0
        self.error = error

    async def execute(self, params, ctx) -> SkillResult:
        self.calls += 1
        return SkillResult(
            data={
                "id": 41 + self.calls,
                "operation_type": "浇水",
                "operation_date": "2026-10-21",
            }
            if not self.error
            else {"code": "invalid_cycle", "message": self.error},
            error=self.error,
        )


class _ReadSkill(_WorkOrderSkill):
    def __init__(self) -> None:
        super().__init__()
        self._meta.update(name="get_crop_cycle_detail", risk_level="read")

    async def execute(self, params, ctx) -> SkillResult:
        self.calls += 1
        return SkillResult(data={"id": 1, "name": "芒果"})


class _BusinessClient:
    def __init__(self, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.parametrize(
    ("answer", "evidence", "accepted"),
    [
        ("总收入：100000 元（已结算）\n- **已结算收入**：100000 元", True, True),
        ("总收入：100000 元（已结算）", False, False),
        ("总成本：1000 元（1000 元未结算，0.00 元已结算）", True, True),
        ("我已为您结算所有账单。", True, False),
        ("总收入（已结算），已创建新账单。", True, False),
    ],
)
@pytest.mark.parametrize("fenced", [False, True])
def test_financial_status_is_not_a_new_settlement_action(
    answer, evidence, accepted, fenced
):
    turn = Turn(user_input="财务分析")
    turn.emit(
        "tool_finished",
        {
            "tool_call_id": "summary",
            "result": {"settled_income": 100000, "settled_cost": 0} if evidence else {},
        },
    )
    content = json.dumps(
        {
            "outcome": "completed",
            "answer": answer,
            "remaining_actions": [],
            "evidence_tool_call_ids": ["summary"],
        },
        ensure_ascii=False,
    )
    if fenced:
        content = f"```json\n{content}\n```"
    if accepted:
        assert finalization.parse_finalization(content, turn, None).answer == answer
    else:
        with pytest.raises(ValueError, match="finalization_write_without_commit"):
            finalization.parse_finalization(content, turn, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("valid_summary", "unfinished_plan"), [(True, False), (False, False), (True, True)]
)
async def test_repeated_reads_stop_tools_and_finalize_existing_results(
    monkeypatch, valid_summary, unfinished_plan
):
    summary = (
        react._LlmResult(
            full_content=json.dumps(
                {
                    "outcome": "completed",
                    "answer": "已查到芒果茬口，编号 1。",
                    "remaining_actions": [],
                    "evidence_tool_call_ids": ["read-1"],
                },
                ensure_ascii=False,
            )
        )
        if valid_summary
        else _tool("get_crop_cycle_detail", "forbidden-read")
    )
    skills, calls, approvals, approve = _runtime(
        monkeypatch,
        [
            _tool("get_crop_cycle_detail", "read-1"),
            _tool("get_crop_cycle_detail", "read-2"),
            _tool("get_crop_cycle_detail", "blocked-read"),
            summary,
        ],
        skills=[_ReadSkill()],
        plan=(
            planner.Plan(
                goal="查看全部茬口",
                steps=[planner.Step("查看其他茬口", "query_crop_cycles", {})],
            )
            if unfinished_plan
            else None
        ),
    )
    turn = Turn(user_input="查询芒果茬口", max_steps=10)
    events = [event async for event in react.run_turn(turn, approve)]
    assert skills[0].calls == 2
    assert not approvals
    assert len(calls) == 4
    assert calls[-1]["tools"] == []
    assert calls[-1]["tool_choice"] == "none"
    assert calls[-1]["max_tokens"] == finalization.FINALIZATION_MAX_TOKENS
    closed_call = next(
        msg
        for msg in calls[-1]["messages"]
        if msg.get("tool_call_id") == "blocked-read"
    )
    assert json.loads(closed_call["content"])["code"] == "execution_stopped"
    assert "芒果" in turn.final_answer
    assert "步数上限" not in turn.final_answer
    types = [event["type"] for event in events]
    assert types.count("doom_loop_warning") == 1
    assert types.count("final_answer") == types.count("done") == 1
    if valid_summary and not unfinished_plan:
        assert turn.status == "completed"
        assert turn.task_state is None
        assert types.count("turn.completed") == 1
    else:
        assert turn.status == "terminated"
        assert turn.stop_reason == StopReason.DOOM_LOOP_DETECTED
        assert types.count("turn.terminated") == 1


@pytest.mark.asyncio
async def test_duplicate_read_waits_for_inflight_batch_before_single_summary(
    monkeypatch,
):
    class SlowRead(_ReadSkill):
        def __init__(self):
            super().__init__()
            self._meta["name"] = "query_other_records"
            self._meta["execution"] = {"mode": "parallel_safe"}

        async def execute(self, params, ctx):
            self.calls += 1
            await asyncio.sleep(0.01)
            return SkillResult(data={"income": 100})

    repeated, slow = _ReadSkill(), SlowRead()
    repeated._meta["execution"] = {"mode": "parallel_safe"}
    _, calls, _, approve = _runtime(
        monkeypatch,
        [
            _tool(repeated.name, "read-1"),
            _tool(repeated.name, "read-2"),
            react._LlmResult(
                tool_calls=[
                    {"id": "late-read", "name": slow.name, "arguments": {}},
                    {"id": "blocked-read", "name": repeated.name, "arguments": {}},
                ]
            ),
            react._LlmResult(
                full_content=json.dumps(
                    {
                        "outcome": "completed",
                        "answer": "查询得到收入 100 元。",
                        "remaining_actions": [],
                        "evidence_tool_call_ids": ["late-read"],
                    },
                    ensure_ascii=False,
                )
            ),
        ],
        skills=[repeated, slow],
    )
    turn = Turn(user_input="查询收入", max_steps=10)
    events = [event async for event in react.run_turn(turn, approve)]
    assert repeated.calls == 2
    assert slow.calls == 1
    assert len(calls) == 4
    assert any(
        msg.get("tool_call_id") == "late-read" and "100" in msg["content"]
        for msg in calls[-1]["messages"]
    )
    assert turn.status == "completed"
    assert sum(event["type"] == "final_answer" for event in events) == 1


@pytest.mark.asyncio
async def test_repeated_write_still_terminates_without_summary_call(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("写入死循环不能进入只读收尾")
        yield

    monkeypatch.setattr(react, "_call_llm_stream", forbidden)
    tracker = react.verify.CallTracker()
    tracker.record("create_work_order", {}, risk_level="write_confirm")
    turn = Turn(user_input="创建工单")
    turn.emit("tool_finished", {"tool_call_id": "write", "result": {"id": 1}})
    events = [
        event
        async for event in react._emit_doom_loop_terminal(
            turn, "重复写入", tracker=tracker
        )
    ]
    assert turn.stop_reason == StopReason.DOOM_LOOP_DETECTED
    assert events[-1]["type"] == "turn.terminated"


def _tool(name: str, call_id: str) -> react._LlmResult:
    return react._LlmResult(tool_calls=[{"id": call_id, "name": name, "arguments": {}}])


def _answer(outcome="completed", *, remaining=None, evidence=None) -> react._LlmResult:
    return react._LlmResult(
        full_content=json.dumps(
            {
                "outcome": outcome,
                "answer": "浇水工单已创建，编号 42。"
                + ("工时尚未登记。" if remaining else ""),
                "remaining_actions": remaining or [],
                "evidence_tool_call_ids": evidence or ["write-1"],
            },
            ensure_ascii=False,
        )
    )


def _runtime(monkeypatch, responses, *, skills=None, plan=None, approved=True):
    skills = skills or [_ReadSkill(), _WorkOrderSkill()]
    registry = SkillRegistry.from_skills(skills)
    calls, approvals = [], []

    async def prepare(turn):
        turn.messages = [
            {"role": "user", "content": "帮我给芒果茬口创建明天的浇水工单"},
            {"role": "assistant", "content": "请选择茬口：1. 芒果"},
            {"role": "user", "content": turn.user_input},
        ]
        return react._TurnRuntime(
            registry,
            registry.exposed_tools(),
            registry,
            react.verify.CallTracker(),
            {"plan": plan},
        )

    async def llm(messages, tools, **kwargs):
        calls.append({"messages": messages, "tools": tools, **kwargs})
        response = responses[len(calls) - 1]
        if isinstance(response, Exception):
            raise response
        yield response

    async def approve(_turn_id):
        approvals.append(_turn_id)
        return approved, "用户确认" if approved else "用户拒绝"

    monkeypatch.setattr(react, "_prepare_turn_runtime", prepare)
    monkeypatch.setattr(react, "_call_llm_stream", llm)
    monkeypatch.setattr(react, "_build_identity_headers", lambda turn: {})
    monkeypatch.setattr(react, "BusinessClient", _BusinessClient)
    monkeypatch.setattr(react.tokenizer, "must_compress", lambda usage: False)
    monkeypatch.setattr(react.tokenizer, "should_compress", lambda usage: False)
    return skills, calls, approvals, approve


@pytest.mark.asyncio
async def test_last_step_write_finishes_without_extra_decision_or_duplicate_write(
    monkeypatch,
):
    responses = [
        _tool("get_crop_cycle_detail", "read-1"),
        _tool("create_work_order", "write-1"),
        _answer(),
    ]
    skills, calls, approvals, approve = _runtime(monkeypatch, responses)
    turn = Turn(user_input="1", max_steps=2)
    events = [event async for event in react.run_turn(turn, approve)]
    types = [event["type"] for event in events]

    assert turn.status == "completed"
    assert turn.step_count == turn.max_steps == 2
    assert "42" in turn.final_answer
    assert [skill.calls for skill in skills] == [1, 1]
    assert len(approvals) == 1
    assert len(calls) == 3
    assert calls[-1]["tools"] == []
    assert calls[-1]["tool_choice"] == "none"
    assert calls[-1]["max_tokens"] == finalization.FINALIZATION_MAX_TOKENS
    assert types.count("step.started") == types.count("step.completed") == 2
    assert types.count("operation_committed") == 1
    assert (
        types.count("final_answer")
        == types.count("turn.completed")
        == types.count("done")
        == 1
    )
    assert "turn.terminated" not in types


@pytest.mark.asyncio
async def test_write_does_not_force_early_finalization(monkeypatch):
    skills, calls, _, approve = _runtime(
        monkeypatch,
        [
            _tool("create_work_order", "write-1"),
            _tool("get_crop_cycle_detail", "read-1"),
            react._LlmResult(
                full_content="浇水工单已创建，编号 42；芒果茬口信息已查询。"
            ),
        ],
    )
    turn = Turn(user_input="创建工单并查询茬口信息", max_steps=3)
    _ = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "completed"
    assert len(calls) == 3
    assert calls[1]["tools"]
    assert [skill.calls for skill in skills] == [1, 1]
    assert len(turn.committed_operations) == 1
    assert turn.committed_result is None


@pytest.mark.asyncio
async def test_partial_completion_retains_commit_and_remaining_work(monkeypatch):
    _, _, _, approve = _runtime(
        monkeypatch,
        [
            _tool("create_work_order", "write-1"),
            _answer("partial", remaining=["登记工时"]),
        ],
    )
    turn = Turn(user_input="创建浇水工单并登记工时", max_steps=1)
    events = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "terminated"
    assert turn.stop_reason == StopReason.STEP_BUDGET_EXHAUSTED
    assert "42" in turn.final_answer
    assert "工时尚未登记" in turn.final_answer
    assert not any(event["type"] == "turn.completed" for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        RuntimeError("模型不可用"),
        react._LlmResult(full_content=""),
        react._LlmResult(full_content="无效 JSON"),
        _tool("create_work_order", "repeat-write"),
        _answer(evidence=["不存在的调用"]),
    ],
)
async def test_finalization_failure_never_repeats_write_or_loses_committed_id(
    monkeypatch, response
):
    skills, calls, _, approve = _runtime(
        monkeypatch, [_tool("create_work_order", "write-1"), response]
    )
    turn = Turn(user_input="创建工单", max_steps=1)
    events = [event async for event in react.run_turn(turn, approve)]
    assert skills[1].calls == 1
    assert len(calls) == 2
    assert turn.step_count == 1
    assert turn.status == "terminated"
    assert "42" in turn.final_answer
    assert "已确认执行成功" in turn.final_answer
    assert sum(event["type"] == "done" for event in events) == 1


@pytest.mark.asyncio
async def test_finalization_timeout_uses_commit_evidence(monkeypatch):
    _, calls, _, approve = _runtime(
        monkeypatch, [_tool("create_work_order", "write-1")]
    )
    normal_call = react._call_llm_stream

    async def llm(messages, tools, **kwargs):
        if not tools:
            await asyncio.sleep(1)
        async for item in normal_call(messages, tools, **kwargs):
            yield item

    monkeypatch.setattr(react, "_call_llm_stream", llm)
    monkeypatch.setattr(finalization, "FINALIZATION_TIMEOUT_SECONDS", 0.01)
    turn = Turn(user_input="创建工单", max_steps=1)
    _ = [event async for event in react.run_turn(turn, approve)]
    assert len(calls) == 1
    assert turn.status == "terminated"
    assert "42" in turn.final_answer


@pytest.mark.asyncio
@pytest.mark.parametrize("approved,error", [(False, None), (True, "茬口不存在")])
async def test_rejection_and_failure_are_not_overwritten_by_step_budget(
    monkeypatch, approved, error
):
    skill = _WorkOrderSkill(error=error)
    _, calls, _, approve = _runtime(
        monkeypatch, [_tool(skill.name, "write-1")], skills=[skill], approved=approved
    )
    turn = Turn(user_input="创建工单", max_steps=1)
    events = [event async for event in react.run_turn(turn, approve)]
    assert turn.stop_reason == (
        StopReason.TOOL_FAILED if approved else StopReason.APPROVAL_REJECTED
    )
    assert not turn.committed_operations
    assert len(calls) == 1
    assert not any(event["type"] == "operation_committed" for event in events)


@pytest.mark.asyncio
async def test_unfinished_plan_blocks_model_claim_of_full_success(monkeypatch):
    plan = planner.Plan(
        goal="创建工单并登记工时",
        steps=[
            planner.Step(
                description="登记工时", skill="add_labor_to_work_order", args={}
            ),
        ],
    )
    _, _, _, approve = _runtime(
        monkeypatch, [_tool("create_work_order", "write-1"), _answer()], plan=plan
    )
    turn = Turn(user_input=plan.goal, max_steps=1)
    _ = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "terminated"
    assert "42" in turn.final_answer


def test_continuation_budget_estimate_receives_recent_task_context():
    messages = planner.budget_estimate_messages(
        "1",
        memory_snapshot={
            "messages": [
                {"role": "user", "content": "创建明天的浇水工单"},
                {"role": "assistant", "content": "请选择茬口：1. 芒果"},
            ]
        },
        task_state={"goal": "创建浇水工单", "status": "awaiting_input"},
    )
    request = json.loads(messages[-1]["content"])
    assert request["user_request"] == "1"
    assert request["recent_messages"][0]["content"] == "创建明天的浇水工单"
    assert "创建浇水工单" in request["task_state"]


@pytest.mark.parametrize(
    "result",
    [
        {"status": "needs_information"},
        {"status": "ready"},
        {"success": False},
        {"error": "invalid_cycle"},
        {},
    ],
)
def test_pending_and_error_results_are_not_commit_evidence(result):
    turn = Turn()
    assert not finalization.record_committed_operation(
        turn, _WorkOrderSkill(), {}, result, "write-1"
    )
    assert not turn.committed_operations


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["completed", "needs_information", "partial"])
async def test_read_only_finalization_preserves_outcome_without_commit(
    monkeypatch, outcome
):
    answer = react._LlmResult(
        full_content=json.dumps(
            {
                "outcome": outcome,
                "answer": "芒果茬口编号为 1。"
                if outcome == "completed"
                else "需要确认作业日期。",
                "evidence_tool_call_ids": ["read-1"],
                "remaining_actions": [],
            },
            ensure_ascii=False,
        )
    )
    _, _, _, approve = _runtime(
        monkeypatch, [_tool("get_crop_cycle_detail", "read-1"), answer]
    )
    turn = Turn(user_input="查询茬口", max_steps=1)
    _ = [event async for event in react.run_turn(turn, approve)]
    assert not turn.committed_operations
    expected = {
        "completed": StopReason.MODEL_COMPLETED,
        "needs_information": StopReason.USER_INPUT_REQUIRED,
        "partial": StopReason.STEP_BUDGET_EXHAUSTED,
    }
    assert turn.stop_reason == expected[outcome]


@pytest.mark.asyncio
async def test_multiple_plan_writes_have_distinct_commit_evidence(monkeypatch):
    call = _tool("make_plan", "plan-1")
    call.tool_calls[0]["arguments"] = {
        "goal": "创建两条不同日期的浇水工单",
        "steps": [
            {
                "description": "明天浇水",
                "skill": "create_work_order",
                "args": {"day": "明天"},
            },
            {
                "description": "后天浇水",
                "skill": "create_work_order",
                "args": {"day": "后天"},
            },
        ],
    }
    ids = ["plan-1-1-create_work_order", "plan-1-2-create_work_order"]
    skills, _, approvals, approve = _runtime(monkeypatch, [call, _answer(evidence=ids)])
    turn = Turn(user_input="创建两条不同日期的浇水工单", max_steps=1)
    events = [event async for event in react.run_turn(turn, approve)]
    assert skills[1].calls == len(approvals) == 2
    assert [item["tool_call_id"] for item in turn.committed_operations] == ids
    assert [item["result"]["id"] for item in turn.committed_operations] == [42, 43]
    assert sum(event["type"] == "operation_committed" for event in events) == 2
    assert turn.status == "completed"


@pytest.mark.asyncio
async def test_requested_read_finalization_failure_is_not_budget_exhaustion(
    monkeypatch,
):
    skill = _ReadSkill()
    skill._meta["finalize_after_success"] = True
    _, _, _, approve = _runtime(
        monkeypatch,
        [_tool(skill.name, "read-1"), RuntimeError("收尾不可用")],
        skills=[skill],
    )
    turn = Turn(user_input="查看茬口", max_steps=20)
    _ = [event async for event in react.run_turn(turn, approve)]
    assert turn.step_count == 1
    assert turn.stop_reason == StopReason.LLM_FAILED
    assert turn.status == "failed"


@pytest.mark.asyncio
async def test_cancelled_finalization_closes_model_stream(monkeypatch):
    closed = asyncio.Event()

    async def chat_stream(*args, **kwargs):
        try:
            await asyncio.sleep(1)
            yield {"type": "done", "tool_calls": []}
        finally:
            closed.set()

    monkeypatch.setattr(react, "chat_stream", chat_stream)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            _ = [
                item
                async for item in react._call_llm_stream([], [], tool_choice="none")
            ]
    assert closed.is_set()


@pytest.mark.asyncio
async def test_plan_with_failed_write_cannot_be_reported_as_completed(monkeypatch):
    call = _tool("make_plan", "plan-1")
    call.tool_calls[0]["arguments"] = {
        "goal": "创建两条浇水工单",
        "steps": [
            {"description": "首条工单", "skill": "create_work_order", "args": {}},
            {"description": "第二条工单", "skill": "failed_write", "args": {}},
        ],
    }
    success, failure = _WorkOrderSkill(), _WorkOrderSkill(error="茬口不存在")
    failure._meta["name"] = "failed_write"
    _, _, _, approve = _runtime(
        monkeypatch,
        [call, _answer(evidence=["plan-1-1-create_work_order"])],
        skills=[success, failure],
    )
    turn = Turn(user_input="创建两条浇水工单", max_steps=1)
    events = [event async for event in react.run_turn(turn, approve)]
    assert turn.status == "terminated"
    assert len(turn.committed_operations) == 1
    assert "42" in turn.final_answer
    plan_events = [event for event in events if event["type"] == "plan_step_done"]
    assert [event["data"]["status"] for event in plan_events] == ["done", "failed"]


@pytest.fixture(autouse=True)
def isolate_personalization_storage(monkeypatch):
    """预算回归不访问部署环境中的真实用户记忆。"""
    from unittest.mock import AsyncMock
    monkeypatch.setattr(react.memory, "get_personalization_context", AsyncMock(return_value={}))
