from unittest.mock import AsyncMock, patch

import pytest

from app.agent.advisor import invoke_advisor, stream_advisor
from app.agent.executor.models import PendingActionDecision
from app.infra.pending_actions import remove_pending, store_pending


@pytest.fixture(autouse=True)
def clean_pending_action():
    remove_pending(1)
    yield
    remove_pending(1)


@pytest.mark.asyncio
async def test_advisor_delegates_pending_confirm_to_executor():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    with patch(
        "app.agent.advisor.handle_pending_action",
        new_callable=AsyncMock,
    ) as mock_pending:
        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")
        reply = await invoke_advisor("确认", farm_id=1)

    assert reply == "已执行：已记账"
    mock_pending.assert_awaited_once_with(
        farm_id=1,
        message="确认",
        farm_uid=None,
        session_id="",
    )


@pytest.mark.asyncio
async def test_advisor_clears_trace_for_pending_handled_reply():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    with (
        patch(
            "app.agent.advisor.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch("app.agent.advisor.clear_trace") as mock_clear_trace,
    ):
        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")
        reply = await invoke_advisor("确认", farm_id=1)

    assert reply == "已执行：已记账"
    mock_clear_trace.assert_called_once_with()


@pytest.mark.asyncio
async def test_stream_advisor_clears_trace_for_pending_handled_reply():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    with (
        patch(
            "app.agent.advisor.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch("app.agent.advisor.clear_trace") as mock_clear_trace,
    ):
        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")
        chunks = [chunk async for chunk in stream_advisor("确认", farm_id=1)]

    assert chunks == ["已执行：已记账"]
    mock_clear_trace.assert_called_once_with()


@pytest.mark.asyncio
async def test_stream_advisor_refuses_unsupported_delete_cost_request():
    """没有删除账单 Skill 时，不应让模型承诺清理所有账单。"""
    with patch("app.agent.advisor._get_advisor_graph") as mock_graph:
        chunks = [
            chunk
            async for chunk in stream_advisor(
                "清理所有账单", farm_id=1, user_id="user-1"
            )
        ]

    assert "暂不支持" in "".join(chunks)
    assert "删除账单" in "".join(chunks)
    mock_graph.assert_not_called()
