"""RouterDecision 到 PlanDraft 的适配测试。"""

import pytest

from app.agent.planning import plan_draft_from_router_decision
from app.agent.router.models import IntentFrame, RouterDecision

pytestmark = pytest.mark.no_db


def test_router_decision_adapter_preserves_selected_tools_and_evidence() -> None:
    decision = RouterDecision(
        frames=[
            IntentFrame(
                domain="operation",
                intent="create_work_order",
                risk="write_confirm",
                candidate_tools=["create_operation_work_order"],
                params_hint={
                    "workers": ["李海"],
                    "operation_type": "压瓜",
                    "quantity": 15,
                },
                planning_evidence={
                    "worker": "李海",
                    "operation_type": "压瓜",
                    "quantity": 15,
                    "write_risk": "implicit_farm_labor_work",
                },
                missing_fields=["unit_price_or_default_wage"],
                requires_confirmation=True,
            )
        ],
        selected_tools=["create_operation_work_order"],
    )

    draft = plan_draft_from_router_decision(
        raw_user_input="李海这个月干了15天压瓜",
        decision=decision,
        farm_id=1,
        session_id="sess-1",
    )

    assert draft.route_type == "write_pending_action"
    assert draft.selected_tools == ["create_operation_work_order"]
    assert draft.steps[0].skill_name == "create_operation_work_order"
    assert draft.steps[0].params["operation_type"] == "压瓜"
    assert draft.evidence["worker"] == "李海"
    assert draft.missing_fields == ["unit_price_or_default_wage"]
    assert decision.selected_tools == ["create_operation_work_order"]


def test_router_decision_adapter_creates_clarification_draft() -> None:
    decision = RouterDecision(
        frames=[
            IntentFrame(
                domain="operation",
                intent="clarify_farm_labor_work",
                risk="write_confirm",
                planning_evidence={"worker": "李海", "quantity": 15},
                missing_fields=["operation_type"],
            )
        ],
        selected_tools=[],
        fallback="clarify_farm_labor_work",
        clarification="请补充作业类型。",
    )

    draft = plan_draft_from_router_decision(
        raw_user_input="李海这个月干了15天",
        decision=decision,
    )

    assert draft.route_type == "clarification"
    assert draft.missing_fields == ["operation_type"]
    assert draft.validation is not None
    assert draft.validation.status == "blocked"
    assert draft.validation.safe_route_type == "clarification"
