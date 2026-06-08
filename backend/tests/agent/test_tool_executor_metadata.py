"""Tool executor metadata 权限测试。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_actions import get_pending, remove_pending
from app.models.planting import LaborEntry, OperationWorkOrder, Worker


@pytest.fixture(autouse=True)
def clean_pending_action():
    remove_pending(1)
    yield
    remove_pending(1)


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
async def test_read_metadata_executes_immediately_even_when_name_matches_write_fallback():
    tool = SimpleNamespace(
        name="create_cost_record",
        args_schema=None,
        ainvoke=AsyncMock(return_value="已读取"),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.READ),
    )
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_cost_record",
                        "args": {"amount": 100},
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
    tool.ainvoke.assert_awaited_once_with({"amount": 100})
    assert result["messages"][0].content == "已读取"


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
            "web_search",
            "外部搜索暂不可用",
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
    assert collector.record.call_args.kwargs["output_data"] == expected_output


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
        name="web_search",
        args_schema=None,
        ainvoke=AsyncMock(return_value="搜索结果"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.EXTERNAL_NETWORK
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

    assert result["messages"][0].content == "搜索结果"
    tool.ainvoke.assert_awaited_once_with({"query": "天气"})
    assert collector.record.call_args.kwargs["output_data"] == {
        "status": "success",
        "reply_preview": "搜索结果",
        "permission_level": "external_network",
    }
