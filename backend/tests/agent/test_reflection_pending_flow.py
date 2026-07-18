from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.reflector import (
    ReflectionDecision,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.agent.executor.pending_actions import handle_pending_action
from app.agent.reflector.models import ReflectionIssue
from app.agent.router import SkillRouter
from app.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_action_presenter import (
    build_confirm_message,
    build_plan_confirm_message,
)
from app.infra.pending_actions import (
    get_pending,
    get_pending_plan,
    remove_pending,
    store_pending,
    store_pending_plan,
)
from app.models.farm import Farm


def _tool(name: str, description: str = ""):
    return SimpleNamespace(name=name, description=description)


def _write_tool(name: str):
    return SimpleNamespace(
        name=name,
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行写操作"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=["get_farm_status"],
        ),
    )


def _blocked_result(trigger: ReflectionTrigger) -> ReflectionResult:
    return ReflectionResult(
        trigger=trigger,
        decision=ReflectionDecision.BLOCK_WRITE,
        reason="Reflection 拦截了风险写操作。",
        issues=[
            ReflectionIssue(
                code="reflection_blocked_for_test",
                severity=ReflectionSeverity.BLOCKER,
                message="Reflection 拦截了风险写操作。",
                suggested_decision=ReflectionDecision.BLOCK_WRITE,
            )
        ],
    )


@pytest.fixture(autouse=True)
def clean_pending_state(db_session, monkeypatch):
    if db_session.query(Farm).filter(Farm.id == 1).first() is None:
        db_session.add(Farm(id=1, name="Reflection 测试农场"))
        db_session.commit()
    monkeypatch.setattr(
        "app.infra.pending_actions.SessionLocal",
        lambda: db_session,
        raising=False,
    )
    remove_pending(1)
    yield
    remove_pending(1)


@pytest.mark.asyncio
async def test_pending_plan_reflection_blocks_storage_and_returns_tool_messages():
    message = "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了"
    router_decision = SkillRouter().route(
        message,
        [_tool("manage_workers"), _tool("create_operation_work_order")],
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
                        },
                    },
                ],
            ),
        ],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "session_id": "reflection-plan",
        "router_decision": router_decision,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[
                _write_tool("manage_workers"),
                _write_tool("create_operation_work_order"),
            ],
        ),
        patch("app.agent.runtime.tool_executor.get_collector"),
        patch("app.agent.runtime.tool_pending.ReflectorService") as reflector_cls,
    ):
        reflector_cls.return_value.check_pending_plan.return_value = _blocked_result(
            ReflectionTrigger.PRE_WRITE_PLAN
        )

        result = await _parallel_tool_node(state)

    assert get_pending_plan(1, session_id="reflection-plan") is None
    returned_messages = result["messages"]
    assert len(returned_messages) == 2
    assert {message.tool_call_id for message in returned_messages} == {
        "tc-worker",
        "tc-work-order",
    }
    assert all(
        "Reflection 拦截了风险写操作。" in msg.content for msg in returned_messages
    )
    reflector_cls.return_value.check_pending_plan.assert_called_once()


@pytest.mark.asyncio
async def test_pending_action_reflection_blocks_storage_and_returns_tool_message():
    message = "记一笔化肥 200 元"
    state = {
        "messages": [
            HumanMessage(content=message),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc-cost",
                        "name": "create_cost_record",
                        "args": {"amount": 200, "category": "化肥"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "session_id": "reflection-action",
    }
    create_cost_record = _write_tool("create_cost_record")

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[create_cost_record],
        ),
        patch("app.agent.runtime.tool_executor.get_collector"),
        patch("app.agent.runtime.tool_pending.ReflectorService") as reflector_cls,
    ):
        reflector_cls.return_value.check_write_plan.return_value = _blocked_result(
            ReflectionTrigger.PRE_WRITE_PLAN
        )

        result = await _parallel_tool_node(state)

    assert get_pending(1, session_id="reflection-action") is None
    returned_message = result["messages"][0]
    assert returned_message.tool_call_id == "tc-cost"
    assert "Reflection 拦截了风险写操作。" in returned_message.content
    create_cost_record.ainvoke.assert_not_awaited()
    reflector_cls.return_value.check_write_plan.assert_called_once()


@pytest.mark.asyncio
async def test_confirmed_pending_action_reflection_blocks_execution():
    store_pending(
        1,
        "create_cost_record",
        {"amount": 200, "category": "化肥", "record_type": "cost"},
        original_input="记一笔化肥 200 元",
        session_id="reflection-action-confirm",
    )

    with (
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
        patch("app.agent.executor.pending_actions.ReflectorService") as reflector_cls,
    ):
        reflector_cls.return_value.check_write_plan.return_value = _blocked_result(
            ReflectionTrigger.PRE_EXECUTION
        )

        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
            session_id="reflection-action-confirm",
        )

    assert decision.handled is True
    assert decision.status == "failed"
    assert decision.reply == "执行失败：Reflection 拦截了风险写操作。"
    pending_action = get_pending(1, session_id="reflection-action-confirm")
    assert pending_action is not None
    mock_execute.assert_not_awaited()
    reflector_cls.return_value.check_write_plan.assert_called_once_with(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        skill_name="create_cost_record",
        params={"amount": 200, "category": "化肥", "record_type": "cost"},
        confirmation_text=build_confirm_message(
            "create_cost_record",
            {"amount": 200, "category": "化肥", "record_type": "cost"},
            original_input="记一笔化肥 200 元",
        ),
        trace_metadata={
            "farm_id": 1,
            "session_id": "reflection-action-confirm",
            "phase": "confirm_pending_action",
            "action_id": pending_action.action_id,
            "tool_name": "create_cost_record",
            "legacy_tool_name": "create_cost_record",
            "resolved_capability": "manage_cost",
            "resolved_operation": "create_record",
            "operation_risk": "write_confirm",
        },
    )


@pytest.mark.asyncio
async def test_confirmed_pending_plan_reflection_blocks_execution():
    store_pending_plan(
        farm_id=1,
        session_id="reflection-plan-confirm",
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
                "params": {
                    "workers": "王大妈",
                    "unit_names": "5号棚",
                    "operation_type": "采收",
                },
                "depends_on": ["create_worker"],
            },
        ],
    )

    with (
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
        patch("app.agent.executor.pending_actions.ReflectorService") as reflector_cls,
    ):
        reflector_cls.return_value.check_pending_plan.return_value = _blocked_result(
            ReflectionTrigger.PRE_EXECUTION
        )

        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
            session_id="reflection-plan-confirm",
        )

    pending_plan = get_pending_plan(1, session_id="reflection-plan-confirm")
    assert decision.handled is True
    assert decision.status == "failed"
    assert decision.reply == "执行失败：Reflection 拦截了风险写操作。"
    assert pending_plan is not None
    mock_execute.assert_not_awaited()
    reflector_cls.return_value.check_pending_plan.assert_called_once_with(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        steps=pending_plan.steps,
        confirmation_text=build_plan_confirm_message(pending_plan.steps),
        trace_metadata={
            "farm_id": 1,
            "session_id": "reflection-plan-confirm",
            "phase": "confirm_pending_plan",
            "plan_id": pending_plan.plan_id,
            "tool_names": [
                "manage_workers",
                "create_operation_work_order",
            ],
            "resolved_operations": [
                {
                    "legacy_tool_name": "manage_workers",
                    "resolved_capability": "manage_workers",
                    "resolved_operation": "manage_worker",
                    "operation_risk": "write_confirm",
                },
                {
                    "legacy_tool_name": "create_operation_work_order",
                    "resolved_capability": "manage_work_orders",
                    "resolved_operation": "create_work_order",
                    "operation_risk": "write_confirm",
                },
            ],
        },
    )
