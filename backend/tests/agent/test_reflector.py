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
    check_tool_failure_write_plan_reply,
    check_tool_result_discarded_reply,
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


def test_check_tool_failure_blocks_write_plan_no_tool_reply() -> None:
    tool_message = ToolMessage(
        content="工具调用失败：写操作缺少明确目标，请补充要操作的对象。",
        tool_call_id="tc-cost",
    )

    result = check_tool_failure_write_plan_reply(
        tool_messages=[tool_message],
        final_text="这个问题可以直接聊，不需要调用工具。",
        plan_draft={
            "route_type": "write_pending_action",
            "steps": [{"skill_name": "manage_farm_logs"}],
        },
        pending_created=False,
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "failed_write_plan_no_tool_reply"


def test_check_tool_result_discarded_reply_requests_regeneration() -> None:
    result = check_tool_result_discarded_reply(
        tool_messages=[
            ToolMessage(
                content="【农场现状】茬口：夏季水稻、夏季大豆",
                tool_call_id="tc-status",
            )
        ],
        final_text="这个问题可以直接聊，不需要调用工具。",
    )

    assert result.decision == ReflectionDecision.RETRY_GENERATION
    assert result.issues[0].code == "tool_result_discarded_reply"


def test_service_blocks_failed_write_plan_no_tool_reply(
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
        tool_messages=[
            ToolMessage(
                content="工具调用失败：写操作缺少明确目标，请补充要操作的对象。",
                tool_call_id="tc-cost",
            )
        ],
        final_text="这个问题可以直接聊，不需要调用工具。",
        selected_tools=[],
        tool_calls=[{"name": "manage_farm_logs"}],
        trace_metadata={
            "plan_draft": {
                "route_type": "write_pending_action",
                "steps": [{"skill_name": "manage_farm_logs"}],
            },
            "pending_created": False,
        },
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "failed_write_plan_no_tool_reply"
    assert collector.records[0]["output_data"]["issues"][0]["code"] == (
        "failed_write_plan_no_tool_reply"
    )


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
        selected_tools=["manage_crop_cycle", "manage_crop_templates"],
        tool_calls=[],
        final_text=(
            "十几亩可以先按 15 亩左右做试种规划。建议先确认地块排水、"
            "租期和预算，再决定是否建茬口。"
        ),
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_required_tool_missing_allows_currently_framed_advice() -> None:
    result = check_required_tool_missing(
        selected_tools=["manage_crop_cycle"],
        tool_calls=[],
        final_text="目前建议先把地块排水和租期确认清楚，后面再决定要不要建茬口。",
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_required_tool_missing_allows_no_need_advice() -> None:
    result = check_required_tool_missing(
        selected_tools=["manage_crop_cycle"],
        tool_calls=[],
        final_text="没有必要马上建茬口，先把地块和租期聊清楚更稳。",
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_required_tool_missing_blocks_template_availability_claim() -> None:
    result = check_required_tool_missing(
        selected_tools=["manage_crop_templates"],
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
        selected_tools=["get_farm_status", "weather"],
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


def test_no_tool_write_success_blocks_selected_write_tool_without_call() -> None:
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))
    plan_draft = {
        "route_type": "write_pending_action",
        "steps": [
            {
                "skill_name": "manage_work_orders",
                "params": {"operation": "create_work_order"},
            }
        ],
        "validation": {"status": "valid"},
    }

    result = service.check_tool_response(
        tool_messages=[],
        final_text="这就为李四好和王阿毛创建今天的芒果苗期作业单。",
        selected_tools=["manage_work_orders"],
        tool_calls=[],
        trace_metadata={
            "user_message": "今天就安排他们去芒果地吧",
            "plan_draft": plan_draft,
            "pending_created": False,
        },
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "no_tool_write_success_claim"
    assert result.issues[0].evidence["selected_tools"] == ["manage_work_orders"]
    assert result.issues[0].evidence["plan_draft"]["route_type"] == (
        "write_pending_action"
    )


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


def test_check_tool_result_final_contradiction_allows_user_and_derived_facts() -> None:
    tool_message = ToolMessage(
        content="【农场现状】当前共有 2 个茬口，欠款 5000 元。",
        tool_call_id="tc-status",
    )

    result = check_tool_result_final_contradiction(
        tool_messages=[tool_message],
        final_text="按你说的 30 亩和每块 1.5 亩，共规划 20 个茬口。",
        fact_sources={
            "total_area_mu": {
                "value": 30,
                "source": "user_input",
            },
            "unit_area_mu": {
                "value": 1.5,
                "source": {"kind": "user_input", "ref": "slot:unit_area_mu"},
            },
            "unit_count": {
                "value": 20,
                "source": {"kind": "derived", "ref": "rule:area_division"},
            },
        },
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_tool_result_final_contradiction_does_not_allow_same_value_wrong_fact() -> (
    None
):
    tool_message = ToolMessage(
        content="查询结果：当前共有 2 个茬口。",
        tool_call_id="tc-status",
    )

    result = check_tool_result_final_contradiction(
        tool_messages=[tool_message],
        final_text="系统里当前共有 3 个茬口。",
        fact_sources={
            "total_area_mu": {
                "value": 3,
                "source": "user_input",
            }
        },
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "tool_result_final_contradiction"


def test_check_tool_result_final_contradiction_still_blocks_tool_fact_mismatch() -> (
    None
):
    tool_message = ToolMessage(
        content="查询结果：当前共有 2 个茬口。",
        tool_call_id="tc-status",
    )

    result = check_tool_result_final_contradiction(
        tool_messages=[tool_message],
        final_text="系统里当前共有 3 个茬口。",
        fact_sources={
            "active_cycle_count": {
                "value": 3,
                "source": {"kind": "tool_result", "ref": "tc-status"},
            }
        },
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "tool_result_final_contradiction"


def test_service_allows_task_graph_fact_sources_in_trace_metadata() -> None:
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))

    result = service.check_tool_response(
        tool_messages=[
            ToolMessage(
                content="【农场现状】当前共有 2 个茬口，欠款 5000 元。",
                tool_call_id="tc-status",
            )
        ],
        final_text="按你说的 30 亩和每块 1.5 亩，共规划 20 个茬口。",
        selected_tools=[],
        tool_calls=[],
        trace_metadata={
            "fact_sources": {
                "total_area_mu": {
                    "value": 30,
                    "source": {"kind": "user_input"},
                },
                "unit_area_mu": {
                    "value": 1.5,
                    "source": {"kind": "user_input"},
                },
                "unit_count": {
                    "value": 20,
                    "source": {"kind": "derived"},
                },
            }
        },
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_tool_result_final_contradiction_allows_plan_advice_numbers() -> None:
    tool_message = ToolMessage(
        content=(
            "【农场现状】\n"
            "茬口：夏季水稻(成熟期(阶段至2026-12-16))、"
            "夏季大豆(播种期(阶段至2026-06-15))\n"
            "本月花费：250元\n"
            "天气：今天晴37°/明天晴37°/后天晴36°"
        ),
        tool_call_id="tc-status",
    )

    result = check_tool_result_final_contradiction(
        tool_messages=[tool_message],
        final_text=(
            "秋季种豆角可以先规划起来。建议 8 月中下旬到 9 月初播种，"
            "10 月到 11 月采收；面积和地块确认后再建档。"
        ),
    )

    assert result.decision == ReflectionDecision.PASS


def test_check_tool_result_final_contradiction_allows_area_clarification() -> None:
    tool_message = ToolMessage(
        content=(
            "【农场现状】 茬口：夏季西瓜(播种育苗期(阶段至2026-08-17)) "
            "欠账：购买大棚膜 5000元(已到期) 本月花费：5000元 "
            "天气：今天晴35°/明天晴35°/后天晴36°"
        ),
        tool_call_id="tc-status",
    )

    result = check_tool_result_final_contradiction(
        tool_messages=[tool_message],
        final_text=(
            "根据目前的记录，系统里还没有录入夏季西瓜的**种植面积**。\n\n"
            "为了帮你规划后续的豆角种植，我们需要确认这块“默认地块”的具体大小。"
            "你是打算按**1亩**来规划，还是有具体的面积数值？告诉我后，我就可以把这两个茬口关联起来啦。"
        ),
    )

    assert result.decision == ReflectionDecision.PASS


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
