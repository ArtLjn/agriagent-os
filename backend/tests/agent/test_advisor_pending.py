from unittest.mock import AsyncMock, patch

import pytest

from app.application.advice.advisor import invoke_advisor, stream_advisor
from app.agent.executor.models import PendingActionDecision
from app.infra.pending_actions import remove_pending, store_pending


@pytest.fixture(autouse=True)
def clean_pending_action():
    with (
        patch("app.infra.pending_actions._cancel_pending_plan_in_db"),
        patch("app.infra.pending_actions._load_pending_plan_from_db", return_value=None),
    ):
        remove_pending(1)
        yield
        remove_pending(1)


@pytest.mark.asyncio
async def test_advisor_delegates_pending_confirm_to_executor():
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    with patch(
        "app.application.advice.advisor.handle_pending_action",
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
            "app.application.advice.advisor.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch("app.application.advice.advisor.clear_trace") as mock_clear_trace,
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
            "app.application.advice.advisor.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch("app.application.advice.advisor.clear_trace") as mock_clear_trace,
    ):
        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")
        chunks = [chunk async for chunk in stream_advisor("确认", farm_id=1)]

    assert chunks == ["已执行：已记账"]
    mock_clear_trace.assert_called_once_with()


@pytest.mark.asyncio
async def test_stream_advisor_refuses_unsupported_delete_cost_request():
    """没有删除账单 Skill 时，不应让模型承诺清理所有账单。"""
    with patch("app.application.advice.advisor._get_advisor_graph") as mock_graph:
        chunks = [
            chunk
            async for chunk in stream_advisor(
                "清理所有账单", farm_id=1, user_id="user-1"
            )
        ]

    assert "暂不支持" in "".join(chunks)
    assert "删除账单" in "".join(chunks)
    mock_graph.assert_not_called()


@pytest.mark.asyncio
async def test_stream_advisor_records_trace_for_greeting_reply():
    with (
        patch("app.application.advice.advisor.record_agent_response") as mock_record_response,
        patch("app.application.advice.advisor.clear_trace") as mock_clear_trace,
    ):
        chunks = [
            chunk
            async for chunk in stream_advisor(
                "你好",
                farm_id=1,
                session_id="sess-greeting",
                request_id="req-greeting",
                user_id="user-1",
            )
        ]

    assert "".join(chunks)
    mock_record_response.assert_called_once()
    assert mock_record_response.call_args.kwargs["node_name"] == "greeting_reply"
    mock_clear_trace.assert_called_once_with()


@pytest.mark.asyncio
async def test_advisor_records_trace_for_unsupported_capability_reply():
    with (
        patch("app.application.advice.advisor.record_agent_response") as mock_record_response,
        patch("app.application.advice.advisor.clear_trace") as mock_clear_trace,
    ):
        reply = await invoke_advisor(
            "清理所有账单",
            farm_id=1,
            session_id="sess-unsupported",
            request_id="req-unsupported",
            user_id="user-1",
        )

    assert "暂不支持" in reply
    mock_record_response.assert_called_once()
    assert (
        mock_record_response.call_args.kwargs["node_name"]
        == "unsupported_capability_reply"
    )
    mock_clear_trace.assert_called_once_with()
