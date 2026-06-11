from unittest.mock import AsyncMock, call, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from types import SimpleNamespace

from app.agent.executor.pending_actions import handle_pending_action
from app.agent.graph import _parallel_tool_node
from app.agent.router import SkillRouter
from app.agent.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_action_presenter import build_plan_confirm_message
from app.infra.pending_actions import (
    PENDING_MARKER,
    _pending_plans,
    get_pending_plan,
    remove_pending,
    store_pending_plan,
)
from app.models.farm import Farm
from app.models.pending_plan import AgentPendingPlan


def _tool(name: str, description: str = ""):
    return SimpleNamespace(name=name, description=description)


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
                    "workers": "王大妈",
                    "unit_names": "5号棚",
                    "operation_type": "采收",
                    "unit_price": 100,
                },
                "depends_on": ["create_worker"],
            },
        ],
    )


@pytest.fixture(autouse=True)
def clean_pending_plan(db_session, monkeypatch):
    if db_session.query(Farm).filter(Farm.id == 2).first() is None:
        db_session.add(Farm(id=2, name="恢复测试农场"))
        db_session.commit()
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
    remove_pending(1)
    remove_pending(2)
    yield
    remove_pending(1)
    remove_pending(2)


@pytest.mark.asyncio
async def test_runtime_tool_flow_stores_pending_plan_without_invoking_write_tools():
    message = "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了"
    router = SkillRouter()
    router_decision = router.route(
        message,
        [_tool("manage_workers"), _tool("create_operation_work_order")],
    )
    manage_workers = SimpleNamespace(
        name="manage_workers",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行工人写入"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=["get_farm_status"],
        ),
    )
    create_work_order = SimpleNamespace(
        name="create_operation_work_order",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行作业单写入"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=["farm_logs"],
        ),
    )
    state = {
        "messages": [
            HumanMessage(content=message),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc-worker",
                        "name": "manage_workers",
                        "args": {
                            "action": "create",
                            "name": "王大妈",
                            "default_pay_type": "daily",
                            "default_unit_price": 100,
                        },
                    },
                ],
            ),
        ],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "session_id": "session4",
        "router_decision": router_decision,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[manage_workers, create_work_order],
        ),
        patch("app.agent.runtime.tool_executor.get_collector"),
    ):
        result = await _parallel_tool_node(state)

    pending_plan = get_pending_plan(1, session_id="session4")
    assert pending_plan is not None
    assert pending_plan.raw_user_input == message
    assert [step.tool_name for step in pending_plan.steps] == [
        "manage_workers",
        "create_operation_work_order",
    ]
    assert pending_plan.steps[0].params == {
        "action": "create",
        "name": "王大妈",
        "default_pay_type": "daily",
        "default_unit_price": 100,
    }
    assert pending_plan.steps[1].params == {
        "workers": "王大妈",
        "unit_names": "5号棚",
        "operation_type": "采收",
        "unit_price": 100,
    }
    assert "请确认将执行 2 步" in result["messages"][0].content
    assert PENDING_MARKER in result["messages"][0].content
    manage_workers.ainvoke.assert_not_awaited()
    create_work_order.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_pending_plan_returns_tool_message_for_each_tool_call():
    message = "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了"
    router_decision = SkillRouter().route(
        message,
        [_tool("manage_workers"), _tool("create_operation_work_order")],
    )
    manage_workers = SimpleNamespace(
        name="manage_workers",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行工人写入"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=["get_farm_status"],
        ),
    )
    create_work_order = SimpleNamespace(
        name="create_operation_work_order",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行作业单写入"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=["farm_logs"],
        ),
    )
    tool_calls = [
        {
            "id": "tc-worker",
            "name": "manage_workers",
            "args": {
                "action": "create",
                "name": "王大妈",
                "default_pay_type": "daily",
                "default_unit_price": 100,
            },
        },
        {
            "id": "tc-work-order",
            "name": "create_operation_work_order",
            "args": {
                "workers": ["王大妈"],
                "unit_names": ["5号棚"],
                "operation_type": "采收",
                "unit_price": 100,
            },
        },
    ]
    state = {
        "messages": [
            HumanMessage(content=message),
            AIMessage(content="", tool_calls=tool_calls),
        ],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "session_id": "session4",
        "router_decision": router_decision,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[manage_workers, create_work_order],
        ),
        patch("app.agent.runtime.tool_executor.get_collector"),
    ):
        result = await _parallel_tool_node(state)

    returned_messages = result["messages"]
    assert len(returned_messages) == len(tool_calls)
    assert {message.tool_call_id for message in returned_messages} == {
        "tc-worker",
        "tc-work-order",
    }
    assert PENDING_MARKER in returned_messages[0].content
    assert "请确认将执行 2 步" in returned_messages[0].content
    assert "已纳入待确认计划" in returned_messages[1].content
    assert get_pending_plan(1, session_id="session4") is not None
    manage_workers.ainvoke.assert_not_awaited()
    create_work_order.ainvoke.assert_not_awaited()


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
                "workers": "王大妈",
                "unit_names": "5号棚",
                "operation_type": "采收",
                "unit_price": 100,
            },
            farm_uid="farm-uid-1",
        ),
    ]


@pytest.mark.asyncio
async def test_handle_pending_plan_confirm_normalizes_legacy_list_args():
    store_pending_plan(
        farm_id=1,
        session_id="session4",
        raw_user_input="今天来了一个工人李1工资100一天他收水稻厉害今天让他去大豆地采收",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[
            {
                "step_id": "create_worker",
                "tool_name": "manage_workers",
                "params": {
                    "action": "create",
                    "name": "李1",
                    "default_unit_price": 100,
                },
            },
            {
                "step_id": "create_work_order",
                "tool_name": "create_operation_work_order",
                "params": {
                    "workers": ["李1"],
                    "unit_names": ["大豆地"],
                    "operation_type": "采收",
                    "unit_price": 100,
                },
                "depends_on": ["create_worker"],
            },
        ],
    )

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

    assert decision.status == "confirmed"
    assert mock_execute.await_args_list[1] == call(
        farm_id=1,
        skill_name="create_operation_work_order",
        params={
            "workers": "李1",
            "unit_names": "大豆地",
            "operation_type": "采收",
            "unit_price": 100,
        },
        farm_uid="farm-uid-1",
    )


@pytest.mark.asyncio
async def test_handle_pending_plan_confirm_recovers_plan_from_database(
    db_session, monkeypatch
):
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
    store_pending_plan(
        farm_id=2,
        session_id="recover-session",
        raw_user_input="王大妈去5号棚收水稻",
        router_decision={
            "selected_tools": ["manage_workers", "create_operation_work_order"]
        },
        steps=[
            {
                "step_id": "create_worker",
                "tool_name": "manage_workers",
                "params": {"action": "create", "name": "王大妈"},
            },
            {
                "step_id": "create_work_order",
                "tool_name": "create_operation_work_order",
                "params": {"workers": ["王大妈"], "unit_names": ["5号棚"]},
            },
        ],
    )
    _pending_plans.clear()

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.side_effect = ["已创建工人", "已创建农事作业单"]
        decision = await handle_pending_action(
            farm_id=2,
            session_id="recover-session",
            message="确认",
            farm_uid="farm-uid-2",
        )

    assert decision.status == "confirmed"
    assert get_pending_plan(2, session_id="recover-session") is None
    db_plan = (
        db_session.query(AgentPendingPlan)
        .filter_by(farm_id=2, session_id="recover-session")
        .one()
    )
    assert db_plan.status == "completed"
    assert [step.status for step in db_plan.steps] == ["executed", "executed"]
    assert mock_execute.await_args_list == [
        call(
            farm_id=2,
            skill_name="manage_workers",
            params={"action": "create", "name": "王大妈"},
            farm_uid="farm-uid-2",
        ),
        call(
            farm_id=2,
            skill_name="create_operation_work_order",
            params={"workers": "王大妈", "unit_names": "5号棚"},
            farm_uid="farm-uid-2",
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
