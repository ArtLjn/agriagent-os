from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.agent.executor import PendingActionDecision
from app.agent.executor.pending_actions import handle_pending_action
from app.infra.pending_actions import get_pending, remove_pending, store_pending


@pytest.fixture(autouse=True)
def clean_pending_action():
    remove_pending(1)
    yield
    remove_pending(1)


def test_pending_action_decision_factories():
    unhandled = PendingActionDecision.unhandled()
    confirmed = PendingActionDecision.confirmed("已执行：已记账")
    canceled = PendingActionDecision.canceled("已取消操作。")
    modified = PendingActionDecision.modified()
    failed = PendingActionDecision.failed("执行失败：数据库错误")

    assert unhandled.handled is False
    assert unhandled.status == "unhandled"
    assert confirmed.handled is True
    assert confirmed.status == "confirmed"
    assert confirmed.reply == "已执行：已记账"
    assert canceled.status == "canceled"
    assert modified.handled is False
    assert modified.status == "modified"
    assert failed.status == "failed"


@pytest.mark.asyncio
async def test_handle_pending_confirm_executes_skill_and_removes_pending():
    store_pending(
        1,
        "create_cost_record",
        {"amount": 100, "category": "化肥", "record_type": "cost"},
        original_input="买了100块化肥",
    )

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.return_value = "已记账：化肥 100元"
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
        )

    assert decision.handled is True
    assert decision.status == "confirmed"
    assert decision.reply == "已执行：已记账：化肥 100元"
    assert get_pending(1) is None
    assert decision.metadata["legacy_tool_name"] == "create_cost_record"
    assert decision.metadata["resolved_capability"] == "manage_cost"
    assert decision.metadata["resolved_operation"] == "create_record"
    assert decision.metadata["operation_risk"] == "write_confirm"
    mock_execute.assert_awaited_once_with(
        farm_id=1,
        skill_name="create_cost_record",
        params={"amount": 100, "category": "化肥", "record_type": "cost"},
        farm_uid="farm-uid-1",
    )


@pytest.mark.asyncio
async def test_handle_pending_legacy_replay_records_resolved_alias_trace():
    store_pending(
        1,
        "create_cost_record",
        {"amount": 100, "category": "化肥", "record_type": "cost"},
        original_input="买了100块化肥",
    )
    tool = SimpleNamespace(
        name="create_cost_record",
        ainvoke=AsyncMock(return_value="已记账：化肥 100元"),
        skill_metadata=SimpleNamespace(cache_invalidation=[]),
    )
    collector = MagicMock()

    with (
        patch(
            "app.agent.executor.pending_actions.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.executor.pending_actions.get_collector",
            return_value=collector,
        ),
    ):
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
        )

    assert decision.status == "confirmed"
    tool.ainvoke.assert_awaited_once_with(
        {"amount": 100, "category": "化肥", "record_type": "cost"}
    )
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["legacy_tool_name"] == "create_cost_record"
    assert output_data["resolved_capability"] == "manage_cost"
    assert output_data["resolved_operation"] == "create_record"
    assert output_data["operation_risk"] == "write_confirm"


@pytest.mark.asyncio
async def test_handle_pending_unknown_legacy_alias_fails_closed_with_trace():
    store_pending(
        1,
        "removed_legacy_tool",
        {"amount": 100},
        original_input="旧工具确认",
    )
    collector = MagicMock()

    with patch(
        "app.agent.executor.pending_aliases.get_collector",
        return_value=collector,
    ):
        decision = await handle_pending_action(farm_id=1, message="确认")

    assert decision.status == "failed"
    assert "未知 legacy alias" in decision.reply
    assert get_pending(1) is None
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data == {
        "status": "failed",
        "legacy_tool_name": "removed_legacy_tool",
        "alias_resolution": "missing",
    }


@pytest.mark.asyncio
async def test_handle_pending_failure_during_intent_detection_removes_pending():
    store_pending(
        1,
        "create_cost_record",
        {"amount": 100, "category": "化肥", "record_type": "cost"},
        original_input="买了100块化肥",
    )

    with patch(
        "app.agent.executor.pending_actions.detect_user_intent",
        side_effect=RuntimeError("意图检测失败"),
    ):
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
        )

    assert decision.handled is True
    assert decision.status == "failed"
    assert decision.reply == "执行失败：意图检测失败"
    assert get_pending(1) is None


@pytest.mark.asyncio
async def test_handle_pending_cancel_removes_pending():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    decision = await handle_pending_action(farm_id=1, message="取消")

    assert decision.handled is True
    assert decision.status == "canceled"
    assert decision.reply == "已取消操作。"
    assert get_pending(1) is None


@pytest.mark.asyncio
async def test_handle_pending_modify_repeats_confirmation_without_replanning():
    store_pending(
        1,
        "create_cost_record",
        {
            "amount": 130,
            "category": "种子",
            "record_type": "cost",
            "record_subtype": "赊账",
            "counterparty": "张三",
        },
        original_input="今天买橘子种子130张三赊账",
    )

    decision = await handle_pending_action(farm_id=1, message="我赊账的")

    assert decision.handled is True
    assert decision.status == "modified"
    assert "当前有一条待确认操作" in decision.reply
    assert "确认记账" in decision.reply
    assert "赊账" in decision.reply
    assert "张三" in decision.reply
    assert get_pending(1) is not None


@pytest.mark.asyncio
async def test_handle_pending_modify_with_clear_correction_keeps_replanning():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    decision = await handle_pending_action(farm_id=1, message="改成200块")

    assert decision.handled is False
    assert decision.status == "modified"
    assert get_pending(1) is not None


@pytest.mark.asyncio
async def test_handle_pending_missing_template_creates_template_pending():
    store_pending(
        1,
        "create_crop_cycle",
        {"crop_name": "小麦"},
        original_input="我想种小麦",
    )

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.return_value = "系统还没有小麦模板，要帮你创建一个吗？"
        decision = await handle_pending_action(farm_id=1, message="确认")

    pending = get_pending(1)
    assert decision.status == "confirmed"
    assert pending is not None
    assert pending.skill_name == "create_crop_template"
    assert pending.follow_up_skill_name == "create_crop_cycle"
    assert "确认创建作物模板" in decision.reply


@pytest.mark.asyncio
async def test_handle_pending_clears_cache_groups_from_tool_metadata():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})
    tool = type(
        "Tool",
        (),
        {
            "name": "create_cost_record",
            "skill_metadata": type(
                "Metadata",
                (),
                {"cache_invalidation": ["metadata_cost_group"]},
            )(),
        },
    )()

    with (
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
        patch(
            "app.agent.executor.pending_actions.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.executor.pending_actions.clear_skill_cache",
            return_value=2,
        ) as mock_clear,
    ):
        mock_execute.return_value = "已记账"
        decision = await handle_pending_action(farm_id=1, message="确认")

    assert decision.status == "confirmed"
    assert get_pending(1) is None
    assert decision.metadata["cache_groups_cleared"] == ["metadata_cost_group"]
    mock_clear.assert_called_once_with("metadata_cost_group")


@pytest.mark.asyncio
async def test_handle_pending_clears_fallback_cache_groups_when_metadata_empty():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})
    tool = type(
        "Tool",
        (),
        {
            "name": "create_cost_record",
            "skill_metadata": type("Metadata", (), {"cache_invalidation": []})(),
        },
    )()

    with (
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
        patch(
            "app.agent.executor.pending_actions.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.executor.pending_actions.clear_skill_cache",
            return_value=2,
        ) as mock_clear,
    ):
        mock_execute.return_value = "已记账"
        decision = await handle_pending_action(farm_id=1, message="确认")

    assert decision.status == "confirmed"
    assert get_pending(1) is None
    assert decision.metadata["cache_groups_cleared"] == [
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ]
    assert mock_clear.call_count == 3
    mock_clear.assert_has_calls(
        [
            call("cost_analytics"),
            call("cost_summary"),
            call("get_farm_status"),
        ]
    )
