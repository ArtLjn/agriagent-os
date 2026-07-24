"""PlanDraft 驱动 pending 创建的回归测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.runtime.tool_executor import _parallel_tool_node
from app.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_actions import get_pending, get_pending_plan, remove_pending

pytestmark = pytest.mark.no_db


@pytest.fixture(autouse=True)
def clean_pending_state(monkeypatch):
    monkeypatch.setattr(
        "app.infra.pending_actions._cancel_pending_plan_in_db",
        lambda *_, **__: None,
        raising=False,
    )
    remove_pending(1)
    yield
    remove_pending(1)


def _write_tool(name: str):
    return SimpleNamespace(
        name=name,
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
        ),
    )


@pytest.mark.asyncio
async def test_single_write_pending_action_prefers_validated_plan_draft_params() -> (
    None
):
    tool = _write_tool("create_operation_work_order")
    state = {
        "messages": [
            HumanMessage(content="今天李海去6号棚压蔓工资100一天"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_operation_work_order",
                        "args": {"operation_type": "错误作业"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-plan-action",
        "plan_draft": {
            "route_type": "write_pending_action",
            "validation": {"status": "valid"},
            "steps": [
                {
                    "step_id": "create_work_order",
                    "skill_name": "create_operation_work_order",
                    "params": {
                        "workers": "李海",
                        "unit_names": "6号棚",
                        "operation_type": "压蔓",
                        "unit_price": 100,
                    },
                    "depends_on": [],
                }
            ],
        },
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools", return_value=[tool]
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()
        ),
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-plan-action")
    assert pending is not None
    assert pending.params["operation_type"] == "压蔓"
    assert pending.params["workers"] == "李海"
    assert "错误作业" not in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_crop_cycle_builds_template_preflight_pending_plan() -> None:
    tool = _write_tool("manage_crop_cycle")
    state = {
        "messages": [
            HumanMessage(content="帮我创建一个西瓜茬口8424，大概种植20亩地"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc-cycle",
                        "name": "manage_crop_cycle",
                        "args": {
                            "operation": "create_cycle",
                            "crop_name": "西瓜",
                            "cycle_name": "8424西瓜茬口",
                            "area": "20",
                            "status": "planned",
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-crop-template-preflight",
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools", return_value=[tool]
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()
        ),
        patch(
            "app.infra.pending_actions.pending_plan_service.create_pending_plan",
            return_value=SimpleNamespace(plan_id="plan-crop-template-preflight"),
        ),
    ):
        result = await _parallel_tool_node(state)

    plan = get_pending_plan(1, session_id="sess-crop-template-preflight")
    assert get_pending(1, session_id="sess-crop-template-preflight") is None
    assert plan is not None
    assert [step.tool_name for step in plan.steps] == [
        "manage_crop_templates",
        "manage_crop_cycle",
    ]
    assert plan.steps[0].params == {
        "operation": "create_template",
        "crop_name": "西瓜",
        "variety": "8424",
    }
    assert plan.steps[1].params["operation"] == "create_cycle"
    assert plan.steps[1].params["crop_name"] == "西瓜"
    assert plan.steps[1].depends_on == ["ensure_crop_template"]
    assert "请确认将执行 2 步" in result["messages"][0].content
    assert "确认作物模板" in result["messages"][0].content
    assert "确认管理茬口" not in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_multi_write_pending_plan_is_derived_from_validated_plan_draft_steps() -> (
    None
):
    tools = [
        _write_tool("manage_workers"),
        _write_tool("create_operation_work_order"),
    ]
    state = {
        "messages": [
            HumanMessage(content="新来一个工人李丽工资100一天，今天去6号棚收水稻"),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "tc1", "name": "manage_workers", "args": {"name": "错名"}}
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-plan-plan",
        "plan_draft": {
            "route_type": "write_pending_plan",
            "validation": {"status": "valid"},
            "steps": [
                {
                    "step_id": "create_worker",
                    "skill_name": "manage_workers",
                    "params": {
                        "action": "create",
                        "name": "李丽",
                        "default_pay_type": "daily",
                        "default_unit_price": 100,
                    },
                    "depends_on": [],
                },
                {
                    "step_id": "create_work_order",
                    "skill_name": "create_operation_work_order",
                    "params": {
                        "workers": "李丽",
                        "unit_names": "6号棚",
                        "operation_type": "采收",
                        "unit_price": 100,
                    },
                    "depends_on": ["create_worker"],
                },
            ],
        },
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools", return_value=tools
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()
        ),
        patch(
            "app.infra.pending_actions.pending_plan_service.create_pending_plan",
            return_value=SimpleNamespace(plan_id="plan-1"),
        ),
    ):
        result = await _parallel_tool_node(state)

    plan = get_pending_plan(1, session_id="sess-plan-plan")
    assert plan is not None
    assert [step.tool_name for step in plan.steps] == [
        "manage_workers",
        "create_operation_work_order",
    ]
    assert plan.steps[0].params["name"] == "李丽"
    assert plan.steps[1].depends_on == ["create_worker"]
    assert "错名" not in result["messages"][0].content


@pytest.mark.asyncio
async def test_multi_tool_calls_do_not_use_mismatched_plan_draft_steps() -> None:
    tool = _write_tool("manage_workers")
    state = {
        "messages": [
            HumanMessage(content="我招了一些工人，主自豪，李是四 工资 100一天擅长压瓜"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "manage_workers",
                        "args": {
                            "action": "create",
                            "name": "主自豪",
                            "default_pay_type": "daily",
                            "default_unit_price": "100",
                            "note": "擅长压瓜",
                        },
                    },
                    {
                        "id": "tc2",
                        "name": "manage_workers",
                        "args": {
                            "action": "create",
                            "name": "李是四",
                            "default_pay_type": "daily",
                            "default_unit_price": "100",
                            "note": "擅长压瓜",
                        },
                    },
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-plan-mismatch",
        "plan_draft": {
            "route_type": "write_pending_plan",
            "validation": {"status": "valid"},
            "steps": [
                {
                    "step_id": "create_worker",
                    "skill_name": "manage_workers",
                    "params": {
                        "action": "create",
                        "name": "主自豪",
                        "default_pay_type": "daily",
                        "default_unit_price": "100",
                    },
                    "depends_on": [],
                },
                {
                    "step_id": "create_work_order",
                    "skill_name": "create_operation_work_order",
                    "params": {
                        "workers": "主自豪",
                        "operation_type": "压瓜",
                        "unit_price": "100",
                    },
                    "depends_on": ["create_worker"],
                },
            ],
        },
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools", return_value=[tool]
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()
        ),
        patch(
            "app.infra.pending_actions.pending_plan_service.create_pending_plan",
            return_value=SimpleNamespace(plan_id="plan-mismatch"),
        ),
    ):
        result = await _parallel_tool_node(state)

    plan = get_pending_plan(1, session_id="sess-plan-mismatch")
    assert plan is not None
    assert [step.tool_name for step in plan.steps] == [
        "manage_workers",
        "manage_workers",
    ]
    assert [step.params["name"] for step in plan.steps] == ["主自豪", "李是四"]
    assert "创建压瓜作业单" not in result["messages"][0].content
