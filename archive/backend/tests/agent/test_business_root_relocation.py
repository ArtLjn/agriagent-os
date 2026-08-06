"""业务根文件归位后的真实路径测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.prompt.registry import get_registry
from app.domains.conversation.agent_schemas import ChatRequest

pytestmark = pytest.mark.no_db


@pytest.fixture(autouse=True)
def _register_report_prompt_template():
    """报告测试需要最小 prompt 模板。"""
    get_registry().register("report", "1.0", "测试报告模板 {{ current_date }}")
    yield


def test_new_business_modules_are_importable():
    """新业务落点应可直接导入。"""
    import app.application.advice.advisor as advisor
    import app.application.report as report
    import app.platforms.evaluation.skill_coverage as skill_coverage

    assert advisor.invoke_advisor is not None
    assert report.generate_cycle_report is not None
    assert skill_coverage.list_skill_coverage_entries is not None


@pytest.mark.asyncio
async def test_advisor_real_patch_target_drives_execution():
    """patch 真实 advisor loop 入口应影响真实函数执行路径。"""
    import app.application.advice.advisor as advisor

    mock_loop = AsyncMock(return_value={"messages": [MagicMock(content="迁移后回复")]})

    with (
        patch("app.application.advice.advisor.run_agent_loop", mock_loop),
        patch(
            "app.application.advice.advisor.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
    ):
        mock_pending.return_value = MagicMock(handled=False)
        result = await advisor.invoke_advisor("今天该做什么？", farm_id=1)

    assert result == "迁移后回复"
    mock_pending.assert_awaited_once()
    mock_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_report_real_patch_target_drives_execution():
    """patch 真实 report LLM 入口应影响真实函数执行路径。"""
    import app.application.report as report

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="报告内容"))

    with patch("app.application.report._get_report_llm", return_value=mock_llm):
        result = await report.generate_cycle_report(cycle_id=1, farm_id=1)

    assert result == "报告内容"
    mock_llm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_patch_target_drives_real_chat_execution():
    """patch 新非流式聊天 target 应影响新子包聊天入口。"""
    from app.agent.executor.models import PendingActionDecision
    from app.application.chat.use_case import chat

    db = MagicMock()
    farm = MagicMock(id=1, user_id="user-1")

    with (
        patch(
            "app.application.chat.use_case.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_advisor,
        patch(
            "app.application.chat.use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.application.chat.use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
        patch(
            "app.application.chat.use_case.build_pending_action_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.use_case.build_pending_plan_response",
            return_value=None,
        ),
    ):
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_advisor.return_value = "新 target patch 后的回复"

        result = await chat(
            db,
            ChatRequest(message="今天怎么安排", session_id=None),
            farm,
            request_id="req-compat-chat",
        )

    assert result.reply == "新 target patch 后的回复"
    mock_advisor.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_patch_target_drives_real_stream_execution():
    """patch 新流式聊天 target 应影响新子包流式入口。"""
    from app.agent.executor.models import PendingActionDecision
    from app.application.chat.stream_chat import stream_chat_events

    async def _patched_stream_advisor(*_args, **_kwargs):
        yield "流式"
        yield "回复"

    db = MagicMock()
    user = MagicMock(id="user-1")
    farm = MagicMock(id=1, user_id="user-1")

    with (
        patch(
            "app.application.chat.stream_chat.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.application.chat.stream_chat.resolve_query_menu_or_message",
            new_callable=AsyncMock,
            return_value=("请给建议", None),
        ),
        patch(
            "app.application.chat.stream_chat.stream_advisor",
            side_effect=_patched_stream_advisor,
        ) as mock_stream_advisor,
        patch(
            "app.application.chat.stream_chat._flush_trace_queue",
            new_callable=AsyncMock,
        ),
        patch(
            "app.application.chat.stream_chat._get_skill_names",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.application.chat.stream_chat._schedule_stream_background_finalization",
        ),
        patch(
            "app.application.chat.stream_chat.build_pending_action_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.stream_chat.build_pending_plan_response",
            return_value=None,
        ),
    ):
        mock_pending.return_value = PendingActionDecision.unhandled()
        events = [
            event
            async for event in stream_chat_events(
                db,
                ChatRequest(message="请给建议", session_id=None),
                user,
                farm,
                request_id="req-compat-stream",
            )
        ]

    assert events[:2] == [
        'data: {"content": "流式"}\n\n',
        'data: {"content": "回复"}\n\n',
    ]
    mock_stream_advisor.assert_called_once()
