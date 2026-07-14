"""Tool executor metadata 权限测试。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.agent.runtime.tool_executor import _parallel_tool_node, _permission_decision
from app.agent.skills.metadata import (
    SkillMetadata,
    SkillPermissionLevel,
    get_skill_metadata,
)
from app.infra.pending_actions import get_pending, remove_pending
from app.models.planting import LaborEntry, OperationWorkOrder, Worker


@pytest.fixture(autouse=True)
def clean_pending_action():
    remove_pending(1)
    yield
    remove_pending(1)


@pytest.mark.asyncio
async def test_parallel_tool_node_restores_trace_round_before_execution():
    """工具节点执行前必须恢复触发它的 LLM 轮次。"""
    state = {
        "messages": [HumanMessage(content="无需工具")],
        "farm_id": 1,
        "trace_round_index": 3,
    }

    with patch("app.agent.runtime.tool_executor.set_round_index") as set_round_index:
        result = await _parallel_tool_node(state)

    set_round_index.assert_called_once_with(3)
    assert result == {"messages": []}


@pytest.mark.asyncio
async def test_read_tool_message_preserves_tool_name_for_direct_return():
    """读工具成功后应在 ToolMessage 上保留工具名，供直返策略判断。"""
    tool = SimpleNamespace(
        name="get_weather_forecast",
        args_schema=None,
        ainvoke=AsyncMock(return_value="城市: 苏州\n未来天数: 3天"),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.READ),
    )
    state = {
        "messages": [
            HumanMessage(content="天气怎么样"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-random",
                        "name": "get_weather_forecast",
                        "args": {"location": "苏州"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=MagicMock(),
        ),
    ):
        result = await _parallel_tool_node(state)

    message = result["messages"][0]
    assert message.name == "get_weather_forecast"
    assert message.tool_call_id == "call-random"


@pytest.mark.asyncio
async def test_write_confirm_metadata_creates_pending_action():
    tool = SimpleNamespace(
        name="metadata_write_tool",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=["metadata_group"],
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            HumanMessage(content="创建一条需要确认的记录"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "metadata_write_tool",
                        "args": {"amount": 100},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "metadata_write_tool"
    assert pending.params == {"amount": 100}
    assert pending.original_input == "创建一条需要确认的记录"
    assert "[PENDING_ACTION]" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()
    collector.record.assert_called_once()
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["status"] == "pending"
    assert output_data["permission_level"] == "write_confirm"
    assert output_data["confirmation_context"] == pending.confirmation_context


@pytest.mark.asyncio
async def test_operation_risk_write_confirm_creates_pending_even_with_read_permission():
    tool = SimpleNamespace(
        name="create_cost_record",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.READ,
            capability="manage_cost",
            operation="create_record",
            legacy_alias="create_cost_record",
            operation_risk="write_confirm",
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            HumanMessage(content="今天买了100元化肥"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_cost_record",
                        "args": {"amount": 100, "category": "化肥"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "create_cost_record"
    assert "[PENDING_ACTION]" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["status"] == "pending"
    assert output_data["resolved_capability"] == "manage_cost"
    assert output_data["resolved_operation"] == "create_record"
    assert output_data["operation_risk"] == "write_confirm"


@pytest.mark.asyncio
async def test_operation_risk_write_high_does_not_execute_directly():
    tool = SimpleNamespace(
        name="delete_crop_cycle",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.READ,
            capability="manage_crop_cycle",
            operation="delete_cycle",
            legacy_alias="delete_crop_cycle",
            operation_risk="write_high",
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="删除这个茬口"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "delete_crop_cycle",
                        "args": {"cycle_id": 1},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "delete_crop_cycle"
    assert "[PENDING_ACTION]" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_manage_workers_pending_stores_resolved_worker_id(
    monkeypatch, db_session
):
    """工人更新确认时应把解析出的真实 worker_id 存入 pending。"""
    worker = Worker(farm_id=1, name="猪八戒", status="active", default_pay_type="daily")
    db_session.add(worker)
    db_session.commit()
    db_session.refresh(worker)
    monkeypatch.setattr(
        "app.agent.runtime.tool_executor.SessionLocal", lambda: db_session
    )
    tool = SimpleNamespace(
        name="manage_workers",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            context_dependencies=["workers"],
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="猪八戒日薪改为100"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "manage_workers",
                        "args": {
                            "action": "update",
                            "name": "猪八戒",
                            "default_pay_type": "daily",
                            "default_unit_price": 100,
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-worker-update",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-worker-update")
    assert pending is not None
    assert pending.params["worker_id"] == worker.id
    assert pending.params["name"] == "猪八戒"
    assert f"工人#{worker.id}" not in result["messages"][0].content
    assert "确认更新工人：猪八戒" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_manage_workers_pending_recovers_full_name_from_original_input(
    monkeypatch, db_session
):
    """当模型把完整姓名截短时，pending 参数应按原话中的工人档案纠正。"""
    worker = Worker(farm_id=1, name="刘俊男", status="active", default_pay_type="daily")
    db_session.add(worker)
    db_session.commit()
    db_session.refresh(worker)
    monkeypatch.setattr(
        "app.agent.runtime.tool_executor.SessionLocal", lambda: db_session
    )
    tool = SimpleNamespace(
        name="manage_workers",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            context_dependencies=["workers"],
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="工人刘俊男日薪改为100"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "manage_workers",
                        "args": {
                            "action": "update",
                            "name": "刘俊",
                            "default_pay_type": "daily",
                            "default_unit_price": 100,
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-worker-full-name",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-worker-full-name")
    assert pending is not None
    assert pending.params["worker_id"] == worker.id
    assert pending.params["name"] == "刘俊男"
    assert "确认更新工人：刘俊男" in result["messages"][0].content


@pytest.mark.asyncio
async def test_settle_labor_pending_preview_accepts_worker_name_alias(
    monkeypatch, db_session
):
    """工资结清确认预览应同时支持 worker_name 参数别名。"""
    worker = Worker(farm_id=1, name="哈哈哈", status="active", default_pay_type="daily")
    db_session.add(worker)
    db_session.flush()
    work_order = OperationWorkOrder(
        farm_id=1,
        cycle_id=None,
        operation_type="定植",
        operation_date=date(2026, 6, 8),
        scope_type="cycle",
    )
    db_session.add(work_order)
    db_session.flush()
    work_order_id = work_order.id
    db_session.add(
        LaborEntry(
            farm_id=1,
            work_order_id=work_order.id,
            worker_id=worker.id,
            quantity=1,
            unit_price=100,
            payable_amount=100,
            paid_amount=0,
            unpaid_amount=100,
            settlement_status="unsettled",
        )
    )
    db_session.commit()
    monkeypatch.setattr(
        "app.agent.runtime.tool_executor.SessionLocal", lambda: db_session
    )
    tool = SimpleNamespace(
        name="settle_labor_payment",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            context_dependencies=["workers", "unpaid_labor"],
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="哈哈哈工资结清了"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "settle_labor_payment",
                        "args": {"worker_name": "哈哈哈"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-labor-alias",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-labor-alias")
    assert pending is not None
    assert pending.confirmation_context["inferred_fields"]["affected_entries"] == [
        {
            "entry_id": 1,
            "work_order_id": work_order_id,
            "worker_name": "哈哈哈",
            "unpaid_amount": "100.00",
        }
    ]
    assert "确认还款：哈哈哈" not in result["messages"][0].content
    assert "确认结算人工" in result["messages"][0].content


@pytest.mark.asyncio
async def test_operation_work_order_pending_uses_worker_default_wage(
    monkeypatch, db_session
):
    worker = Worker(
        farm_id=1,
        name="李海",
        status="active",
        default_pay_type="daily",
        default_unit_price=200,
    )
    db_session.add(worker)
    db_session.commit()
    monkeypatch.setattr(
        "app.agent.runtime.tool_executor.SessionLocal", lambda: db_session
    )
    tool = SimpleNamespace(
        name="create_operation_work_order",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            context_dependencies=["workers"],
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="李海这个月干了15天压瓜"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_operation_work_order",
                        "args": {
                            "operation_type": "压瓜",
                            "workers": "李海",
                            "quantity": 15,
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-default-wage",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-default-wage")
    assert pending is not None
    assert pending.params["unit_price"] == 200
    assert pending.params["unit_price_source"] == "worker_default"
    assert pending.params["pay_type"] == "daily"
    assert pending.confirmation_context["labor"]["payable_amount"] == "3000.00"
    assert "单价：200元（来自工人默认工资）" in result["messages"][0].content


@pytest.mark.asyncio
async def test_legacy_create_work_order_alias_stores_manage_operation_pending():
    tool = SimpleNamespace(
        name="manage_work_orders",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            context_dependencies=["workers"],
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="今天李树去6号棚收水稻"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_operation_work_order",
                        "args": {
                            "operation_type": "采收",
                            "workers": "李树",
                            "unit_names": "6号棚",
                            "no_wage": True,
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-work-order-alias",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-work-order-alias")
    assert pending is not None
    assert pending.skill_name == "create_operation_work_order"
    assert pending.params["operation"] == "create_work_order"
    assert pending.params["operation_type"] == "采收"
    assert "[PENDING_ACTION]" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_manage_work_orders_query_operation_executes_without_pending():
    tool = SimpleNamespace(
        name="manage_work_orders",
        args_schema=None,
        ainvoke=AsyncMock(return_value="匹配的农事作业单：\n- #1 采收"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            context_dependencies=["operation_work_orders"],
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="最近玉米授粉作业有哪些"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "manage_work_orders",
                        "args": {"operation": "query_work_orders"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-work-order-query",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    assert get_pending(1, session_id="sess-work-order-query") is None
    tool.ainvoke.assert_awaited_once_with({"operation": "query_work_orders"})
    assert result["messages"][0].content.startswith("匹配的农事作业单")


@pytest.mark.asyncio
async def test_settle_labor_payment_all_workers_drops_polluted_content_param():
    """全员结算不能把上下文中的单人工人名作为待执行参数。"""
    tool = SimpleNamespace(
        name="settle_labor_payment",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="把所有员工工资结了"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "settle_labor_payment",
                        "args": {"内容": "猪八戒"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-all-workers-pay",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-all-workers-pay")
    assert pending is not None
    assert pending.params == {"scope": "all_unpaid_labor"}
    assert pending.confirmation_context["target"]["worker"] is None
    assert pending.confirmation_context["target"]["scope"] == "all_unpaid_labor"
    assert "全部未付人工" in result["messages"][0].content
    assert "猪八戒" not in result["messages"][0].content
    assert "把所有员工工资结了" in result["messages"][0].content


@pytest.mark.asyncio
async def test_settle_labor_payment_all_workers_collapses_multiple_tool_calls():
    """全员结算的多次单人工具调用应收敛为一次待确认操作。"""
    tool = SimpleNamespace(
        name="settle_labor_payment",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM
        ),
    )
    state = {
        "messages": [
            HumanMessage(content="把所有员工工资结了"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "settle_labor_payment",
                        "args": {"worker": "诸葛四郎"},
                    },
                    {
                        "id": "tc2",
                        "name": "settle_labor_payment",
                        "args": {"worker": "猪八戒"},
                    },
                ],
            ),
        ],
        "farm_id": 1,
        "session_id": "sess-all-workers-batch",
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1, session_id="sess-all-workers-batch")
    assert pending is not None
    assert pending.params == {"scope": "all_unpaid_labor"}
    assert len(result["messages"]) == 1
    content = result["messages"][0].content
    assert content.count("[PENDING_ACTION]") == 1
    assert "全部未付人工" in content
    assert "诸葛四郎" not in content
    assert "猪八戒" not in content


@pytest.mark.asyncio
async def test_registry_operation_risk_overrides_incomplete_read_metadata_for_write_alias():
    tool = SimpleNamespace(
        name="create_cost_record",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.READ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            HumanMessage(content="今天买了100元肥料"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_cost_record",
                        "args": {"amount": 100},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "create_cost_record"
    assert "[PENDING_ACTION]" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["status"] == "pending"
    assert output_data["legacy_tool_name"] == "create_cost_record"
    assert output_data["resolved_capability"] == "manage_cost"
    assert output_data["resolved_operation"] == "create_record"
    assert output_data["operation_risk"] == "write_confirm"


def test_manage_user_settings_query_operation_uses_read_permission():
    class _ManageUserSettingsSkill:
        def name(self):
            return "manage_user_settings"

    metadata = get_skill_metadata(_ManageUserSettingsSkill())
    tool = SimpleNamespace(skill_metadata=metadata)
    state = {"messages": []}

    query_decision = _permission_decision(
        tool,
        "manage_user_settings",
        state,
        {"operation": "query_settings"},
    )
    update_decision = _permission_decision(
        tool,
        "manage_user_settings",
        state,
        {"operation": "update_settings", "display_name": "x"},
    )
    inferred_query_decision = _permission_decision(
        tool,
        "manage_user_settings",
        state,
        {},
    )

    assert query_decision.permission_level == SkillPermissionLevel.READ.value
    assert query_decision.requires_confirmation is False
    assert query_decision.operation == "query_settings"
    assert query_decision.operation_risk == "read"
    assert query_decision.capability == "manage_settings"
    assert update_decision.permission_level == SkillPermissionLevel.WRITE_CONFIRM.value
    assert update_decision.requires_confirmation is True
    assert update_decision.operation == "update_settings"
    assert update_decision.operation_risk == "write_confirm"
    assert inferred_query_decision.permission_level == SkillPermissionLevel.READ.value
    assert inferred_query_decision.requires_confirmation is False
    assert inferred_query_decision.operation == "query_settings"
    assert inferred_query_decision.operation_risk == "read"


@pytest.mark.asyncio
async def test_unknown_permission_on_legacy_write_skill_creates_pending_action():
    tool = SimpleNamespace(
        name="create_cost_record",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SimpleNamespace(permission_level="unknown_permission"),
    )
    state = {
        "messages": [
            HumanMessage(content="买了100块化肥"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_cost_record",
                        "args": {"amount": 100, "category": "化肥"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "create_cost_record"
    assert pending.params == {"amount": 100, "category": "化肥"}
    assert "[PENDING_ACTION]" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguous_debt_direction_clarifies_without_pending_action():
    """方向不完整的赊账记账不能创建 pending，需先追问谁欠谁。"""
    tool = SimpleNamespace(
        name="create_cost_record",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SimpleNamespace(permission_level="write_confirm"),
    )
    state = {
        "messages": [
            HumanMessage(content="张三赊账130"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_cost_record",
                        "args": {
                            "amount": 130,
                            "category": "种子",
                            "record_subtype": "赊账",
                            "counterparty": "张三",
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    assert get_pending(1) is None
    assert "谁欠谁" in result["messages"][0].content
    assert "你欠张三" in result["messages"][0].content
    assert "张三欠你" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_purchase_debt_direction_creates_pending_action():
    """买入赊账方向明确，应创建待确认记账。"""
    tool = SimpleNamespace(
        name="create_cost_record",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SimpleNamespace(permission_level="write_confirm"),
    )
    state = {
        "messages": [
            HumanMessage(content="今天买橘子种子130张三赊账"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_cost_record",
                        "args": {
                            "amount": 130,
                            "category": "种子",
                            "record_type": "cost",
                            "record_subtype": "赊账",
                            "counterparty": "张三",
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "create_cost_record"
    assert pending.params["counterparty"] == "张三"
    assert "[PENDING_ACTION]" in result["messages"][0].content
    assert "确认记账" in result["messages"][0].content


@pytest.mark.asyncio
async def test_unknown_permission_on_non_write_skill_fails_closed_without_execution():
    tool = SimpleNamespace(
        name="metadata_read_tool",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SimpleNamespace(permission_level="unknown_permission"),
    )
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "metadata_read_tool",
                        "args": {"keyword": "玉米"},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ):
        result = await _parallel_tool_node(state)

    assert get_pending(1) is None
    assert result["messages"][0].content == "工具调用失败：未知权限等级。"
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_permission_rejects_without_execution_and_records_trace():
    tool = SimpleNamespace(
        name="admin_tool",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.ADMIN),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "admin_tool",
                        "args": {"target": "quota"},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert result["messages"][0].content == "工具调用失败：需要管理员权限。"
    tool.ainvoke.assert_not_awaited()
    collector.record.assert_called_once()
    assert collector.record.call_args.kwargs["output_data"] == {
        "status": "rejected",
        "permission_level": "admin",
    }


@pytest.mark.asyncio
async def test_admin_permission_is_not_downgraded_by_registry_read_operation():
    tool = SimpleNamespace(
        name="get_farm_status",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.ADMIN),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "get_farm_status",
                        "args": {},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert result["messages"][0].content == "工具调用失败：需要管理员权限。"
    tool.ainvoke.assert_not_awaited()
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["status"] == "rejected"
    assert output_data["permission_level"] == "admin"
    assert output_data["legacy_tool_name"] == "get_farm_status"
    assert output_data["resolved_capability"] == "get_farm_status"
    assert output_data["resolved_operation"] == "query_status"
    assert output_data["operation_risk"] == "read"


@pytest.mark.asyncio
async def test_admin_permission_executes_for_admin_user_role_and_records_trace():
    tool = SimpleNamespace(
        name="admin_tool",
        args_schema=None,
        ainvoke=AsyncMock(return_value="管理员工具已执行"),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.ADMIN),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "admin_tool",
                        "args": {"target": "quota"},
                    }
                ],
            )
        ],
        "farm_id": 1,
        "user_role": "admin",
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert result["messages"][0].content == "管理员工具已执行"
    tool.ainvoke.assert_awaited_once_with({"target": "quota"})
    collector.record.assert_called_once()
    assert collector.record.call_args.kwargs["output_data"] == {
        "status": "success",
        "reply_preview": "管理员工具已执行",
        "permission_level": "admin",
    }


@pytest.mark.asyncio
async def test_validation_error_records_trace():
    class RequiredArgs(BaseModel):
        required_name: str

    tool = SimpleNamespace(
        name="metadata_read_tool",
        args_schema=RequiredArgs,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.READ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "metadata_read_tool",
                        "args": {},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert result["messages"][0].content.startswith("参数校验失败:")
    tool.ainvoke.assert_not_awaited()
    collector.record.assert_called_once()
    assert collector.record.call_args.kwargs["node_type"] == "skill_call"
    assert collector.record.call_args.kwargs["node_name"] == "metadata_read_tool"
    assert collector.record.call_args.kwargs["input_data"] == {}
    assert collector.record.call_args.kwargs["output_data"] == {
        "status": "validation_error",
        "permission_level": "read",
    }
    assert "Field required" in collector.record.call_args.kwargs["error_message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("permission_level", "tool_name", "reason"),
    [
        (SkillPermissionLevel.READ, "metadata_read_tool", None),
        (
            SkillPermissionLevel.EXTERNAL_NETWORK,
            "get_weather_forecast",
            "外部天气暂不可用",
        ),
    ],
)
async def test_disabled_read_or_external_tool_rejects_without_execution(
    permission_level, tool_name, reason
):
    tool = SimpleNamespace(
        name=tool_name,
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(
            permission_level=permission_level,
            enabled=False,
            disabled_reason=reason,
            operation_risk=(
                "external_network"
                if permission_level == SkillPermissionLevel.EXTERNAL_NETWORK
                else None
            ),
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": tool_name,
                        "args": {"query": "天气"},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert get_pending(1) is None
    assert "工具已禁用" in result["messages"][0].content
    if reason is not None:
        assert reason in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()
    expected_output = {
        "status": "disabled",
        "permission_level": permission_level.value,
    }
    if reason is not None:
        expected_output["disabled_reason"] = reason
    collector.record.assert_called_once()
    output_data = collector.record.call_args.kwargs["output_data"]
    for key, value in expected_output.items():
        assert output_data[key] == value
    if tool_name == "get_weather_forecast":
        assert output_data["legacy_tool_name"] == "get_weather_forecast"
        assert output_data["resolved_capability"] == "get_weather_forecast"
        assert output_data["resolved_operation"] == "query_forecast"
        assert output_data["operation_risk"] == "external_network"


@pytest.mark.asyncio
async def test_registry_hidden_web_search_rejects_even_when_metadata_enabled():
    tool = SimpleNamespace(
        name="web_search",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.EXTERNAL_NETWORK,
            enabled=True,
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "web_search",
                        "args": {"query": "最新农业政策"},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert get_pending(1) is None
    assert "工具已禁用" in result["messages"][0].content
    assert "SearXNG 引擎不稳定" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["status"] == "disabled"
    assert output_data["permission_level"] == "external_network"
    assert output_data["legacy_tool_name"] == "web_search"
    assert output_data["resolved_capability"] == "web_search"
    assert output_data["resolved_operation"] == "search"
    assert output_data["operation_risk"] == "external_network"
    assert "SearXNG 引擎不稳定" in output_data["disabled_reason"]


@pytest.mark.asyncio
async def test_disabled_write_confirm_tool_rejects_without_pending_action():
    tool = SimpleNamespace(
        name="metadata_write_tool",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            enabled=False,
            disabled_reason="写入功能维护中",
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            HumanMessage(content="创建一条需要确认的记录"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "metadata_write_tool",
                        "args": {"amount": 100},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert get_pending(1) is None
    assert "工具已禁用" in result["messages"][0].content
    assert "写入功能维护中" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()
    collector.record.assert_called_once()
    assert collector.record.call_args.kwargs["output_data"] == {
        "status": "disabled",
        "permission_level": "write_confirm",
        "disabled_reason": "写入功能维护中",
    }


@pytest.mark.asyncio
async def test_external_network_permission_executes_and_records_permission_level():
    tool = SimpleNamespace(
        name="get_weather_forecast",
        args_schema=None,
        ainvoke=AsyncMock(return_value="天气结果"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.EXTERNAL_NETWORK,
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "get_weather_forecast",
                        "args": {"location": "苏州"},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await _parallel_tool_node(state)

    assert result["messages"][0].content == "天气结果"
    tool.ainvoke.assert_awaited_once_with({"location": "苏州"})
    output_data = collector.record.call_args.kwargs["output_data"]
    for key, value in {
        "status": "success",
        "reply_preview": "天气结果",
        "permission_level": "external_network",
    }.items():
        assert output_data[key] == value
    assert output_data["legacy_tool_name"] == "get_weather_forecast"
    assert output_data["resolved_capability"] == "get_weather_forecast"
    assert output_data["resolved_operation"] == "query_forecast"
    assert output_data["operation_risk"] == "external_network"
