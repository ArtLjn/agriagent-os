from unittest.mock import AsyncMock, call, patch

import pytest

from app.agent.executor.pending_actions import handle_pending_action
from app.infra.pending_action_presenter import build_plan_confirm_message
from app.infra.pending_actions import (
    get_pending_plan,
    remove_pending,
    store_pending_plan,
)


pytestmark = pytest.mark.no_db


def _store_session4_plan() -> None:
    store_pending_plan(
        farm_id=1,
        session_id="session4",
        raw_user_input="我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[
            {
                "step_id": "create_worker",
                "tool_name": "manage_workers",
                "params": {
                    "action": "create",
                    "name": "王大妈",
                    "default_unit_price": 100,
                },
            },
            {
                "step_id": "create_work_order",
                "tool_name": "create_operation_work_order",
                "params": {
                    "workers": ["王大妈"],
                    "unit_names": ["5号棚"],
                    "operation_type": "采收",
                    "unit_price": 100,
                },
                "depends_on": ["create_worker"],
            },
        ],
    )


@pytest.fixture(autouse=True)
def clean_pending_plan():
    remove_pending(1)
    yield
    remove_pending(1)


@pytest.mark.asyncio
async def test_handle_pending_plan_confirm_executes_steps_in_order():
    _store_session4_plan()

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.side_effect = ["已创建工人", "已创建农事作业单"]
        decision = await handle_pending_action(
            farm_id=1,
            session_id="session4",
            message="确认",
            farm_uid="farm-uid-1",
        )

    assert decision.handled is True
    assert decision.status == "confirmed"
    assert decision.reply == "已执行：\n1. 已创建工人\n2. 已创建农事作业单"
    assert get_pending_plan(1, session_id="session4") is None
    assert mock_execute.await_args_list == [
        call(
            farm_id=1,
            skill_name="manage_workers",
            params={
                "action": "create",
                "name": "王大妈",
                "default_unit_price": 100,
            },
            farm_uid="farm-uid-1",
        ),
        call(
            farm_id=1,
            skill_name="create_operation_work_order",
            params={
                "workers": ["王大妈"],
                "unit_names": ["5号棚"],
                "operation_type": "采收",
                "unit_price": 100,
            },
            farm_uid="farm-uid-1",
        ),
    ]


def test_build_plan_confirm_message_summarizes_multi_step_plan():
    _store_session4_plan()
    plan = get_pending_plan(1, session_id="session4")

    assert plan is not None
    message = build_plan_confirm_message(plan.steps)

    assert "2 个步骤" in message
    assert "创建工人：王大妈" in message
    assert "创建采收作业单" in message
    assert "确认执行吗？" in message


@pytest.mark.asyncio
async def test_handle_pending_plan_cancel_removes_plan_without_execution():
    _store_session4_plan()

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        decision = await handle_pending_action(
            farm_id=1,
            session_id="session4",
            message="取消",
            farm_uid="farm-uid-1",
        )

    assert decision.handled is True
    assert decision.status == "canceled"
    assert get_pending_plan(1, session_id="session4") is None
    mock_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_pending_plan_modify_repeats_confirmation_without_execution():
    _store_session4_plan()

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        decision = await handle_pending_action(
            farm_id=1,
            session_id="session4",
            message="我看看",
            farm_uid="farm-uid-1",
        )

    assert decision.handled is True
    assert decision.status == "modified"
    assert "当前有一条待确认计划" in decision.reply
    assert "创建工人：王大妈" in decision.reply
    assert "创建采收作业单" in decision.reply
    assert get_pending_plan(1, session_id="session4") is not None
    mock_execute.assert_not_awaited()
