"""Pending plan 并发与原子性回归测试。"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

import pytest

from app.agent.executor.pending_actions import handle_pending_action
from app.agent.executor.tool_failure_reflection import ToolFailureRepairDecision
from app.agent.pending_plan_models import AgentPendingPlan
from app.agent.pending_plan_service import (
    ConcurrentMutationError,
    confirm_pending_plan,
    create_pending_plan,
    mark_step_executed,
    mark_step_failed,
)
from app.agent.runtime.tool_executor import (
    _call_one_with_session_lock,
    _get_session_lock,
    _session_locks,
    release_session_lock,
)
from app.infra.pending_actions import (
    get_pending_plan,
    remove_pending,
    store_pending_plan,
)
from app.observability import (
    get_counter,
    pending_plan_cas_conflict_total,
    pending_plan_partial_completed_total,
    pending_plan_saga_compensate_total,
    reset_metrics,
)
from app.shared.config import settings


def _create_plan(db_session, *, ttl_seconds: int = 300):
    return create_pending_plan(
        db_session,
        farm_id=1,
        session_id="concurrency-session",
        raw_user_input="先建茬口再记账",
        router_decision={"route": "plan"},
        steps=[
            {"skill_name": "create_crop_cycle", "params": {"crop_name": "番茄"}},
            {"skill_name": "create_cost_record", "params": {"amount": 100}},
        ],
        ttl_seconds=ttl_seconds,
    )


@pytest.fixture(autouse=True)
def clean_pending_plan_state(db_session, monkeypatch):
    reset_metrics()
    monkeypatch.setattr(
        "app.infra.pending_actions.SessionLocal",
        lambda: db_session,
        raising=False,
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions.SessionLocal",
        lambda: db_session,
        raising=False,
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_plan_saga.SessionLocal",
        lambda: db_session,
        raising=False,
    )
    remove_pending(1)
    yield
    remove_pending(1)
    reset_metrics()


def test_confirm_pending_plan_uses_cas_and_increments_version(db_session):
    plan = _create_plan(db_session)

    confirmed = confirm_pending_plan(
        db_session,
        plan_id=plan.plan_id,
        expected_version=0,
        now=datetime.now(),
    )

    assert confirmed.status == "running"
    assert confirmed.version == 1

    with pytest.raises(ConcurrentMutationError):
        confirm_pending_plan(
            db_session,
            plan_id=plan.plan_id,
            expected_version=0,
            now=datetime.now(),
        )
    assert pending_plan_cas_conflict_total() == 1


def test_confirm_pending_plan_can_use_legacy_flag_without_cas(db_session, monkeypatch):
    plan = _create_plan(db_session)
    monkeypatch.setattr(settings.pending_plan, "concurrency_safety", False)

    confirmed = confirm_pending_plan(
        db_session,
        plan_id=plan.plan_id,
        expected_version=999,
        now=datetime.now(),
    )

    assert confirmed.status == "running"
    assert confirmed.version == 1


def test_confirm_pending_plan_expires_inside_transaction(db_session):
    plan = _create_plan(db_session, ttl_seconds=-1)

    with pytest.raises(ConcurrentMutationError, match="确认已超时"):
        confirm_pending_plan(
            db_session,
            plan_id=plan.plan_id,
            expected_version=0,
            now=datetime.now(),
        )

    expired = db_session.query(AgentPendingPlan).filter_by(plan_id=plan.plan_id).one()
    assert expired.status == "expired"
    assert [step.status for step in expired.steps] == ["expired", "expired"]


def test_step_state_guard_makes_repeated_execution_noop(db_session):
    plan = _create_plan(db_session)

    mark_step_executed(
        db_session,
        plan_id=plan.plan_id,
        step_index=0,
        result={"message": "第一次"},
    )
    mark_step_executed(
        db_session,
        plan_id=plan.plan_id,
        step_index=0,
        result={"message": "第二次"},
    )

    refreshed = db_session.query(AgentPendingPlan).filter_by(plan_id=plan.plan_id).one()
    assert refreshed.steps[0].result_json == {"message": "第一次"}
    assert refreshed.steps[0].status == "executed"
    assert refreshed.status == "pending"


def test_mark_step_failed_ignores_already_executed_step(db_session):
    plan = _create_plan(db_session)
    plan.expires_at = datetime.now() + timedelta(seconds=300)
    db_session.commit()

    mark_step_executed(
        db_session,
        plan_id=plan.plan_id,
        step_index=0,
        result={"message": "已执行"},
    )
    mark_step_failed(
        db_session,
        plan_id=plan.plan_id,
        step_index=0,
        error_message="重复失败",
    )

    refreshed = db_session.query(AgentPendingPlan).filter_by(plan_id=plan.plan_id).one()
    assert refreshed.steps[0].status == "executed"
    assert refreshed.steps[0].error_message is None


def test_session_lock_reuses_and_releases_lock():
    _session_locks.clear()

    first = _get_session_lock("session-a")
    second = _get_session_lock("session-a")
    other = _get_session_lock("session-b")

    assert first is second
    assert first is not other

    release_session_lock("session-a")

    assert "session-a" not in _session_locks
    assert "session-b" in _session_locks


@pytest.mark.asyncio
async def test_session_lock_serializes_same_session_and_keeps_other_sessions_parallel():
    _session_locks.clear()
    active = 0
    max_active = 0
    calls: list[str] = []

    async def fake_call_one(**kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        calls.append(kwargs["tc"]["id"])
        await asyncio.sleep(0.01)
        active -= 1
        return SimpleNamespace(content=kwargs["tc"]["id"])

    with patch("app.agent.runtime.tool_executor._call_one", side_effect=fake_call_one):
        await asyncio.gather(
            _call_one_with_session_lock(
                tc={"id": "same-1", "name": "tool", "args": {}},
                tool_map={},
                state={},
                farm_id=1,
                original_input="",
                collector=SimpleNamespace(record=lambda **_: None),
                session_id="same-session",
            ),
            _call_one_with_session_lock(
                tc={"id": "same-2", "name": "tool", "args": {}},
                tool_map={},
                state={},
                farm_id=1,
                original_input="",
                collector=SimpleNamespace(record=lambda **_: None),
                session_id="same-session",
            ),
        )

    assert max_active == 1
    assert calls == ["same-1", "same-2"]

    active = 0
    max_active = 0
    with patch("app.agent.runtime.tool_executor._call_one", side_effect=fake_call_one):
        await asyncio.gather(
            _call_one_with_session_lock(
                tc={"id": "other-1", "name": "tool", "args": {}},
                tool_map={},
                state={},
                farm_id=1,
                original_input="",
                collector=SimpleNamespace(record=lambda **_: None),
                session_id="session-1",
            ),
            _call_one_with_session_lock(
                tc={"id": "other-2", "name": "tool", "args": {}},
                tool_map={},
                state={},
                farm_id=1,
                original_input="",
                collector=SimpleNamespace(record=lambda **_: None),
                session_id="session-2",
            ),
        )

    assert max_active == 2


@pytest.mark.asyncio
async def test_pending_plan_saga_compensates_successful_steps(db_session):
    store_pending_plan(
        farm_id=1,
        session_id="saga-success-session",
        raw_user_input="先建茬口再记账",
        router_decision={"selected_tools": ["create_crop_cycle", "create_cost_record"]},
        steps=[
            {
                "step_id": "create_cycle",
                "tool_name": "create_crop_cycle",
                "params": {"crop_name": "番茄"},
            },
            {
                "step_id": "create_cost",
                "tool_name": "create_cost_record",
                "params": {"amount": 100, "category": "肥料"},
            },
        ],
    )
    no_repair = ToolFailureRepairDecision(
        action="no_repair",
        reason="test",
    )

    with (
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
        patch(
            "app.agent.executor.pending_actions.reflect_tool_failure",
            return_value=no_repair,
        ),
    ):
        mock_execute.side_effect = [
            SimpleNamespace(status="success", reply="已创建茬口 #123", id=123),
            SimpleNamespace(status="failed", reply="记账失败：分类不存在"),
            SimpleNamespace(status="success", reply="已删除茬口 #123。"),
        ]
        decision = await handle_pending_action(
            farm_id=1,
            session_id="saga-success-session",
            message="确认",
            farm_uid="farm-uid-1",
        )

    assert decision.status == "failed"
    assert "已自动撤销前序步骤" in decision.reply
    assert mock_execute.await_args_list == [
        call(
            farm_id=1,
            skill_name="create_crop_cycle",
            params={"crop_name": "番茄"},
            farm_uid="farm-uid-1",
        ),
        call(
            farm_id=1,
            skill_name="create_cost_record",
            params={"amount": 100, "category": "肥料"},
            farm_uid="farm-uid-1",
        ),
        call(
            farm_id=1,
            skill_name="delete_crop_cycle",
            params={"cycle_id": 123},
            farm_uid="farm-uid-1",
        ),
    ]
    refreshed = (
        db_session.query(AgentPendingPlan)
        .filter_by(session_id="saga-success-session")
        .one()
    )
    assert refreshed.status == "failed"
    assert refreshed.steps[0].status == "compensated"
    assert refreshed.steps[1].status == "failed"
    assert pending_plan_saga_compensate_total("success") == 1


@pytest.mark.asyncio
async def test_pending_plan_saga_failure_marks_partial_completed(db_session):
    store_pending_plan(
        farm_id=1,
        session_id="saga-partial-session",
        raw_user_input="先建茬口再记账",
        router_decision={"selected_tools": ["create_crop_cycle", "create_cost_record"]},
        steps=[
            {
                "step_id": "create_cycle",
                "tool_name": "create_crop_cycle",
                "params": {"crop_name": "番茄"},
            },
            {
                "step_id": "create_cost",
                "tool_name": "create_cost_record",
                "params": {"amount": 100, "category": "肥料"},
            },
        ],
    )
    no_repair = ToolFailureRepairDecision(action="no_repair", reason="test")

    with (
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
        patch(
            "app.agent.executor.pending_actions.reflect_tool_failure",
            return_value=no_repair,
        ),
    ):
        mock_execute.side_effect = [
            SimpleNamespace(status="success", reply="已创建茬口 #123", id=123),
            SimpleNamespace(status="failed", reply="记账失败：分类不存在"),
            SimpleNamespace(status="failed", reply="删除茬口失败：已有关联数据"),
        ]
        decision = await handle_pending_action(
            farm_id=1,
            session_id="saga-partial-session",
            message="确认",
            farm_uid="farm-uid-1",
        )

    assert decision.status == "failed"
    assert "操作失败,已自动撤销部分步骤,请联系客服清理" in decision.reply
    refreshed = (
        db_session.query(AgentPendingPlan)
        .filter_by(session_id="saga-partial-session")
        .one()
    )
    assert refreshed.status == "partial_completed"
    assert pending_plan_saga_compensate_total("failed") == 1
    assert pending_plan_partial_completed_total() == 1


@pytest.mark.asyncio
async def test_pending_plan_rejects_non_last_step_without_compensate(db_session):
    store_pending_plan(
        farm_id=1,
        session_id="saga-validation-session",
        raw_user_input="先创建分类再记账",
        router_decision={"selected_tools": ["manage_cost_categories"]},
        steps=[
            {
                "step_id": "create_category",
                "tool_name": "manage_cost_categories",
                "params": {
                    "operation": "manage_category",
                    "action": "create",
                    "name": "肥料",
                },
            },
            {
                "step_id": "create_cost",
                "tool_name": "create_cost_record",
                "params": {"amount": 100, "category": "肥料"},
            },
        ],
    )

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        decision = await handle_pending_action(
            farm_id=1,
            session_id="saga-validation-session",
            message="确认",
        )

    assert decision.status == "failed"
    assert "不支持补偿，只能作为最后一步" in decision.reply
    mock_execute.assert_not_awaited()
    assert get_pending_plan(1, session_id="saga-validation-session") is None
    assert get_counter("pending_plan_saga_compensate_total", {"result": "success"}) == 0
