from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import _parallel_tool_node
from app.agent.reflector import (
    ReflectionDecision,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.agent.reflector.models import ReflectionIssue
from app.agent.router import SkillRouter
from app.agent.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_actions import (
    get_pending,
    get_pending_plan,
    remove_pending,
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
        patch(
            "app.agent.runtime.tool_executor.ReflectorService"
        ) as reflector_cls,
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
    assert all("Reflection 拦截了风险写操作。" in msg.content for msg in returned_messages)
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
        patch(
            "app.agent.runtime.tool_executor.ReflectorService"
        ) as reflector_cls,
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
