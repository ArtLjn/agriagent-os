from langchain_core.messages import ToolMessage
from pytest import MonkeyPatch

from app.agent.reflector import (
    ReflectionDecision,
    ReflectionIssue,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
    ReflectorService,
)
from app.agent.reflector.checks import (
    check_required_tool_missing,
    check_tool_failure_success_reply,
    check_write_plan_consistency,
)
from app.agent.reflector.policy import ReflectionPolicy
from app.infra.pending_actions import PendingPlanStep


def test_reflection_result_serializes_trace_payload() -> None:
    issue = ReflectionIssue(
        code="missing_required_param",
        severity=ReflectionSeverity.BLOCKER,
        message="写操作缺少 amount 参数。",
        evidence={"field": "amount"},
        suggested_decision=ReflectionDecision.ASK_CLARIFICATION,
    )

    result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        decision=ReflectionDecision.ASK_CLARIFICATION,
        checks=["write_plan_consistency"],
        issues=[issue],
        reason="写操作参数不完整。",
    )

    assert result.has_blocker is True
    assert result.to_trace_payload() == {
        "trigger": "pre_write_plan",
        "decision": "ask_clarification",
        "reason": "写操作参数不完整。",
        "checks": ["write_plan_consistency"],
        "issues": [
            {
                "code": "missing_required_param",
                "severity": "blocker",
                "message": "写操作缺少 amount 参数。",
                "evidence": {"field": "amount"},
                "suggested_decision": "ask_clarification",
            }
        ],
        "metadata": {},
    }


def test_policy_skips_low_risk_chitchat() -> None:
    policy = ReflectionPolicy(enabled=True)

    assert (
        policy.should_run(
            trigger=ReflectionTrigger.PRE_FINAL_RESPONSE,
            intent="greeting",
            selected_tools=[],
            tool_messages=[],
        )
        is False
    )


def test_policy_runs_for_write_trigger() -> None:
    policy = ReflectionPolicy(enabled=True)

    assert (
        policy.should_run(
            trigger=ReflectionTrigger.PRE_WRITE_PLAN,
            intent="agent",
            selected_tools=["create_cost_record"],
            tool_messages=[],
        )
        is True
    )


def test_check_write_plan_consistency_blocks_empty_params() -> None:
    result = check_write_plan_consistency(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name="create_cost_record",
        params={},
        confirmation_text="确认记账：化肥 200元",
    )

    assert result.decision == ReflectionDecision.ASK_CLARIFICATION
    assert result.issues[0].code == "empty_write_params"


def test_check_write_plan_consistency_blocks_confirmation_mismatch() -> None:
    result = check_write_plan_consistency(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name="create_cost_record",
        params={"amount": 200, "category": "化肥"},
        confirmation_text="确认记账：化肥 300元",
    )

    assert result.decision == ReflectionDecision.BLOCK_WRITE
    assert result.issues[0].code == "confirmation_param_mismatch"
    assert result.issues[0].evidence["field"] == "amount"


def test_check_write_plan_consistency_does_not_substring_match_numbers() -> None:
    result = check_write_plan_consistency(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name="create_cost_record",
        params={"amount": 20, "category": "化肥"},
        confirmation_text="确认记账：化肥 200元",
    )

    assert result.decision == ReflectionDecision.BLOCK_WRITE
    assert result.issues[0].code == "confirmation_param_mismatch"


def test_check_tool_failure_success_reply_rewrites_success_claim() -> None:
    tool_message = ToolMessage(
        content="工具调用失败：数据库连接失败",
        tool_call_id="tc-cost",
    )

    result = check_tool_failure_success_reply(
        tool_messages=[tool_message],
        final_text="已执行：记账成功。",
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "failed_tool_success_reply"


def test_check_required_tool_missing_requests_retry() -> None:
    result = check_required_tool_missing(
        selected_tools=["get_farm_status"],
        tool_calls=[],
        final_text="你现在有两个茬口。",
    )

    assert result.decision == ReflectionDecision.REQUIRE_TOOL
    assert result.issues[0].code == "required_tool_missing"


def test_reflector_service_passes_valid_pending_plan() -> None:
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))
    steps = [
        PendingPlanStep(
            step_id="create_worker",
            step_index=0,
            tool_name="manage_workers",
            params={"action": "create", "name": "王大妈"},
            depends_on=[],
        ),
        PendingPlanStep(
            step_id="create_work_order",
            step_index=1,
            tool_name="create_operation_work_order",
            params={"workers": "王大妈", "operation_type": "采收"},
            depends_on=["create_worker"],
        ),
    ]

    result = service.check_pending_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        steps=steps,
        confirmation_text="请确认将执行 2 步：创建工人，创建作业单",
    )

    assert result.decision == ReflectionDecision.PASS


def test_reflector_service_fail_closes_write_check_errors() -> None:
    class BrokenPolicy(ReflectionPolicy):
        def should_run(self, **_kwargs) -> bool:
            raise RuntimeError("policy exploded")

    service = ReflectorService(policy=BrokenPolicy())

    result = service.check_write_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name="create_cost_record",
        params={"amount": 200},
        confirmation_text="确认记账：200元",
    )

    assert result.decision == ReflectionDecision.BLOCK_WRITE
    assert result.issues[0].code == "reflection_check_failed"
    assert result.checks == ["write_plan_consistency"]


def test_reflector_service_tool_response_errors_do_not_break_reply() -> None:
    class BrokenPolicy(ReflectionPolicy):
        def should_run(self, **_kwargs) -> bool:
            raise RuntimeError("policy exploded")

    service = ReflectorService(policy=BrokenPolicy())

    result = service.check_tool_response(
        tool_messages=[],
        final_text="普通回复",
        selected_tools=["get_farm_status"],
        tool_calls=[],
    )

    assert result.decision == ReflectionDecision.PASS
    assert result.issues[0].code == "reflection_check_failed"


def test_reflector_service_trace_errors_are_best_effort(monkeypatch: MonkeyPatch) -> None:
    class BrokenCollector:
        def record(self, **_kwargs) -> None:
            raise RuntimeError("trace down")

    monkeypatch.setattr(
        "app.agent.reflector.service.get_collector",
        lambda: BrokenCollector(),
    )
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))

    result = service.check_write_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name="create_cost_record",
        params={"amount": 200},
        confirmation_text="确认记账：200元",
    )

    assert result.decision == ReflectionDecision.PASS
