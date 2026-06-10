"""Pending Plan 内存存取 API 测试。"""

import pytest

from app.infra.pending_actions import (
    get_pending_plan,
    remove_pending,
    store_pending_plan,
)


pytestmark = pytest.mark.no_db


def test_store_pending_plan_keeps_steps_and_dependencies():
    remove_pending(1)

    plan_id = store_pending_plan(
        farm_id=1,
        session_id="session-a",
        raw_user_input="先建茬口，再记种子钱",
        router_decision={"route": "plan", "confidence": 0.91},
        steps=[
            {
                "step_id": "step-1",
                "tool_name": "create_crop_cycle",
                "params": {"crop_name": "玉米"},
            },
            {
                "step_id": "step-2",
                "tool_name": "create_cost_record",
                "params": {"category": "种子", "amount": 120},
                "depends_on": ["step-1"],
            },
        ],
    )

    pending_plan = get_pending_plan(1, session_id="session-a")

    assert pending_plan is not None
    assert pending_plan.plan_id == plan_id
    assert pending_plan.farm_id == 1
    assert pending_plan.session_id == "session-a"
    assert pending_plan.raw_user_input == "先建茬口，再记种子钱"
    assert pending_plan.router_decision == {"route": "plan", "confidence": 0.91}
    assert len(pending_plan.steps) == 2
    assert pending_plan.steps[0].step_index == 0
    assert pending_plan.steps[0].depends_on == []
    assert pending_plan.steps[1].step_index == 1
    assert pending_plan.steps[1].depends_on == ["step-1"]

    remove_pending(1, session_id="session-a")

    assert get_pending_plan(1, session_id="session-a") is None
