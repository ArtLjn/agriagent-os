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


def test_store_pending_plan_isolated_from_external_mutation():
    remove_pending(1)
    router_decision = {"route": "plan", "metadata": {"confidence": 0.91}}
    steps = [
        {
            "step_id": "step-1",
            "tool_name": "create_crop_cycle",
            "params": {"crop": {"name": "玉米"}},
            "depends_on": ["root"],
            "result_payload": {"created": {"cycle_id": 7}},
            "error_payload": {"errors": []},
        }
    ]

    store_pending_plan(
        farm_id=1,
        session_id="session-a",
        raw_user_input="建玉米茬口",
        router_decision=router_decision,
        steps=steps,
    )
    router_decision["metadata"]["confidence"] = 0.12
    steps[0]["params"]["crop"]["name"] = "小麦"
    steps[0]["depends_on"].append("mutated")
    steps[0]["result_payload"]["created"]["cycle_id"] = 99
    steps[0]["error_payload"]["errors"].append("mutated")

    pending_plan = get_pending_plan(1, session_id="session-a")

    assert pending_plan is not None
    assert pending_plan.router_decision == {
        "route": "plan",
        "metadata": {"confidence": 0.91},
    }
    assert pending_plan.steps[0].params == {"crop": {"name": "玉米"}}
    assert pending_plan.steps[0].depends_on == ["root"]
    assert pending_plan.steps[0].result_payload == {"created": {"cycle_id": 7}}
    assert pending_plan.steps[0].error_payload == {"errors": []}

    remove_pending(1, session_id="session-a")


def test_remove_pending_by_farm_keeps_other_farms():
    remove_pending(1)
    remove_pending(2)
    store_pending_plan(
        farm_id=1,
        session_id="session-a",
        raw_user_input="建玉米茬口",
        router_decision={"route": "plan"},
        steps=[{"tool_name": "create_crop_cycle", "params": {}}],
    )
    store_pending_plan(
        farm_id=2,
        session_id="session-a",
        raw_user_input="建小麦茬口",
        router_decision={"route": "plan"},
        steps=[{"tool_name": "create_crop_cycle", "params": {}}],
    )

    remove_pending(1)

    assert get_pending_plan(1, session_id="session-a") is None
    assert get_pending_plan(2, session_id="session-a") is not None

    remove_pending(2)


def test_remove_pending_by_session_keeps_same_farm_other_sessions():
    remove_pending(1)
    store_pending_plan(
        farm_id=1,
        session_id="session-a",
        raw_user_input="建玉米茬口",
        router_decision={"route": "plan"},
        steps=[{"tool_name": "create_crop_cycle", "params": {}}],
    )
    store_pending_plan(
        farm_id=1,
        session_id="session-b",
        raw_user_input="建小麦茬口",
        router_decision={"route": "plan"},
        steps=[{"tool_name": "create_crop_cycle", "params": {}}],
    )

    remove_pending(1, session_id="session-a")

    assert get_pending_plan(1, session_id="session-a") is None
    assert get_pending_plan(1, session_id="session-b") is not None

    remove_pending(1, session_id="session-b")


def test_get_pending_plan_removes_expired_plan(monkeypatch):
    remove_pending(1)
    monkeypatch.setattr("app.infra.pending_actions.time.time", lambda: 1_000.0)
    store_pending_plan(
        farm_id=1,
        session_id="session-a",
        raw_user_input="建玉米茬口",
        router_decision={"route": "plan"},
        steps=[{"tool_name": "create_crop_cycle", "params": {}}],
    )

    monkeypatch.setattr("app.infra.pending_actions.time.time", lambda: 1_301.0)

    assert get_pending_plan(1, session_id="session-a") is None
    assert get_pending_plan(1, session_id="session-a") is None
