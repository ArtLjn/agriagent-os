import pytest
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
    check_tool_result_final_contradiction,
    check_write_plan_consistency,
)
from app.agent.reflector.policy import ReflectionPolicy
from app.infra.pending_actions import PendingPlanStep

pytestmark = pytest.mark.no_db


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


def test_check_required_tool_missing_still_blocks_business_fact() -> None:
    result = check_required_tool_missing(
        selected_tools=["get_debt_summary"],
        tool_calls=[],
        final_text="当前共有欠款 100 元。",
    )

    assert result.decision == ReflectionDecision.REQUIRE_TOOL
    assert result.issues[0].code == "required_tool_missing"


def test_check_required_tool_missing_allows_planting_planning_advice() -> None:
    result = check_required_tool_missing(
        selected_tools=["get_crop_cycles", "get_crop_templates"],
        tool_calls=[],
        final_text=(
            "十几亩可以先按 15 亩左右做试种规划。建议先确认地块排水、"
            "租期和预算，再决定是否建茬口。"
        ),
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_required_tool_missing_allows_currently_framed_advice() -> None:
    result = check_required_tool_missing(
        selected_tools=["get_crop_cycles"],
        tool_calls=[],
        final_text="目前建议先把地块排水和租期确认清楚，后面再决定要不要建茬口。",
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_required_tool_missing_allows_no_need_advice() -> None:
    result = check_required_tool_missing(
        selected_tools=["get_crop_cycles"],
        tool_calls=[],
        final_text="没有必要马上建茬口，先把地块和租期聊清楚更稳。",
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_required_tool_missing_blocks_template_availability_claim() -> None:
    result = check_required_tool_missing(
        selected_tools=["get_crop_templates"],
        tool_calls=[],
        final_text="目前没有黑布林模板，可以新建一个。",
    )

    assert result.decision == ReflectionDecision.REQUIRE_TOOL
    assert result.issues[0].code == "required_tool_missing"


@pytest.mark.parametrize(
    "final_text",
    [
        "我可以查天气、看农场情况，也可以帮你记录账务；写操作会先让你确认。",
        "当前可协助的方向包括账务、种植、农事、用工和天气。",
    ],
)
def test_check_required_tool_missing_allows_capability_intro(final_text: str) -> None:
    result = check_required_tool_missing(
        selected_tools=["get_farm_status", "get_weather_forecast"],
        tool_calls=[],
        final_text=final_text,
    )

    assert result.decision == ReflectionDecision.PASS


def test_no_tool_write_success_claim_is_blocked_and_traced(
    monkeypatch: MonkeyPatch,
) -> None:
    class FakeCollector:
        def __init__(self) -> None:
            self.records = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

    collector = FakeCollector()
    monkeypatch.setattr(
        "app.agent.reflector.service.get_collector",
        lambda: collector,
    )
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))

    result = service.check_tool_response(
        tool_messages=[],
        final_text="已记录李海这个月干了15天压瓜。",
        selected_tools=[],
        tool_calls=[],
        trace_metadata={
            "farm_id": 1,
            "session_id": "no-tool-write-claim",
            "user_message": "李海这个月干了15天压瓜",
            "selected_tools": [],
        },
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "no_tool_write_success_claim"
    assert result.issues[0].evidence["matched_success_phrase"] == "已记录"
    assert result.issues[0].evidence["selected_tools"] == []
    assert collector.records[0]["node_type"] == "reflection_check"
    assert collector.records[0]["output_data"]["issues"][0]["code"] == (
        "no_tool_write_success_claim"
    )
    assert (
        collector.records[0]["input_data"]["user_message"] == "李海这个月干了15天压瓜"
    )


def test_no_tool_write_success_claim_trace_includes_plan_draft_evidence(
    monkeypatch: MonkeyPatch,
) -> None:
    class FakeCollector:
        def __init__(self) -> None:
            self.records = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

    collector = FakeCollector()
    monkeypatch.setattr(
        "app.agent.reflector.service.get_collector",
        lambda: collector,
    )
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))
    plan_draft = {
        "route_type": "write_pending_action",
        "steps": [
            {
                "tool_name": "create_operation_work_order",
                "params": {"worker_name": "李海", "operation_type": "压瓜"},
            }
        ],
        "missing_fields": [],
        "validation": {"status": "passed"},
        "evidence": {"source": "rule_gate"},
    }

    result = service.check_tool_response(
        tool_messages=[],
        final_text="已记录李海这个月干了15天压瓜。",
        selected_tools=[],
        tool_calls=[],
        trace_metadata={
            "user_message": "李海这个月干了15天压瓜",
            "plan_draft": plan_draft,
            "pending_created": False,
        },
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    evidence = result.issues[0].evidence
    assert evidence["failure_stage"] == "response_quality"
    assert evidence["plan_draft"]["route_type"] == "write_pending_action"
    assert evidence["plan_draft"]["validation_status"] == "passed"
    assert evidence["plan_draft"]["steps"] == ["create_operation_work_order"]
    assert evidence["pending_created"] is False
    trace_issue = collector.records[0]["output_data"]["issues"][0]
    assert trace_issue["evidence"]["plan_draft"]["route_type"] == (
        "write_pending_action"
    )
    assert collector.records[0]["input_data"]["plan_draft"] == plan_draft


def test_no_tool_write_success_guard_allows_safe_non_write_replies() -> None:
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))

    greeting = service.check_tool_response(
        tool_messages=[],
        final_text="你好，有什么我可以帮你？",
        selected_tools=[],
        tool_calls=[],
        trace_metadata={"user_message": "你好"},
    )
    explanation = service.check_tool_response(
        tool_messages=[],
        final_text="记录工资前需要先确认工人、日期和金额。",
        selected_tools=[],
        tool_calls=[],
        trace_metadata={"user_message": "为什么不能直接记录工资？"},
    )

    assert greeting.decision == ReflectionDecision.PASS
    assert explanation.decision == ReflectionDecision.PASS


def test_no_tool_write_success_guard_allows_query_options_with_recorded_logs() -> None:
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))

    result = service.check_tool_response(
        tool_messages=[],
        final_text=(
            "你可以选：\n"
            "1. 天气与环境\n"
            "2. 查看已记录的农事操作日志\n"
            "3. 查看当前作物的生长阶段详情"
        ),
        selected_tools=[],
        tool_calls=[],
        trace_metadata={"user_message": "给我几个选项我选择查啥"},
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_tool_result_final_contradiction_blocks_number_mismatch() -> None:
    tool_message = ToolMessage(
        content="查询结果：当前共有 2 个茬口。",
        tool_call_id="tc-status",
    )

    result = check_tool_result_final_contradiction(
        tool_messages=[tool_message],
        final_text="你现在有 3 个茬口。",
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "tool_result_final_contradiction"


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


def test_reflector_service_tool_response_errors_record_trace(
    monkeypatch: MonkeyPatch,
) -> None:
    class BrokenPolicy(ReflectionPolicy):
        def should_run(self, **_kwargs) -> bool:
            raise RuntimeError("policy exploded")

    class FakeCollector:
        def __init__(self) -> None:
            self.records = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

    collector = FakeCollector()
    monkeypatch.setattr(
        "app.agent.reflector.service.get_collector",
        lambda: collector,
    )
    service = ReflectorService(policy=BrokenPolicy())

    result = service.check_tool_response(
        tool_messages=[],
        final_text="普通回复",
        selected_tools=["get_farm_status"],
        tool_calls=[],
        trace_metadata={"farm_id": 1},
    )

    assert result.decision == ReflectionDecision.PASS
    assert collector.records[0]["node_type"] == "reflection_check"
    assert collector.records[0]["output_data"]["issues"][0]["code"] == (
        "reflection_check_failed"
    )
    assert collector.records[0]["input_data"]["farm_id"] == 1


def test_reflector_service_trace_errors_are_best_effort(
    monkeypatch: MonkeyPatch,
) -> None:
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
