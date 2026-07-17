"""业务根文件迁移兼容测试。"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.prompt.registry import get_registry
from app.schemas.agent import ChatRequest

pytestmark = pytest.mark.no_db


@pytest.fixture(autouse=True)
def _register_report_prompt_template():
    """报告兼容测试需要最小 prompt 模板。"""
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


def test_legacy_advisor_public_api_reexports_new_objects():
    """旧 advisor 入口公开对象应转发到新模块对象。"""
    import app.agent.advisor as legacy_advisor
    import app.application.advice.advisor as new_advisor

    assert legacy_advisor.build_advisor_agent is new_advisor.build_advisor_agent
    assert legacy_advisor.invoke_advisor is new_advisor.invoke_advisor
    assert legacy_advisor.stream_advisor is new_advisor.stream_advisor


def test_legacy_report_public_api_reexports_new_objects():
    """旧 report 入口公开对象应转发到新模块对象。"""
    import app.agent.report as legacy_report
    import app.application.report as new_report

    assert legacy_report.generate_cycle_report is new_report.generate_cycle_report


def test_legacy_skill_coverage_public_api_reexports_new_objects():
    """旧 skill_coverage 入口公开对象应转发到新模块对象。"""
    import app.agent.skill_coverage as legacy_coverage
    import app.platforms.evaluation.skill_coverage as new_coverage

    public_names = [
        "CoverageStatus",
        "SkillCoverageEntry",
        "list_skill_coverage_entries",
        "summarize_skill_coverage",
    ]
    for name in public_names:
        assert getattr(legacy_coverage, name) is getattr(new_coverage, name)


@pytest.mark.asyncio
async def test_legacy_advisor_patch_target_drives_new_execution():
    """patch 旧 advisor 图入口仍应影响新真实函数执行路径。"""
    import app.agent.advisor as legacy_advisor
    import app.application.advice.advisor as new_advisor

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"messages": [MagicMock(content="迁移后回复")]}
    )

    with (
        patch("app.agent.advisor._get_advisor_graph", return_value=mock_graph),
        patch(
            "app.agent.advisor.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
    ):
        mock_pending.return_value = MagicMock(handled=False)
        result = await new_advisor.invoke_advisor("今天该做什么？", farm_id=1)

    assert legacy_advisor.invoke_advisor is new_advisor.invoke_advisor
    assert result == "迁移后回复"
    mock_pending.assert_awaited_once()
    mock_graph.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_report_patch_target_drives_new_execution():
    """patch 旧 report LLM 入口仍应影响新真实函数执行路径。"""
    import app.agent.report as legacy_report
    import app.application.report as new_report

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="报告内容"))

    with patch("app.agent.report._get_report_llm", return_value=mock_llm):
        result = await new_report.generate_cycle_report(cycle_id=1, farm_id=1)

    assert legacy_report.generate_cycle_report is new_report.generate_cycle_report
    assert result == "报告内容"
    mock_llm.ainvoke.assert_awaited_once()


def test_legacy_agent_advisor_aliases_real_advice_module():
    """旧 agent advisor 入口不应双跳加载旧 application advisor。"""
    legacy_agent = importlib.import_module("app.agent.advisor")
    new_module = importlib.import_module("app.application.advice.advisor")

    assert legacy_agent is new_module


@pytest.mark.asyncio
async def test_legacy_chat_patch_target_drives_new_chat_execution():
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
async def test_legacy_stream_patch_target_drives_new_stream_execution():
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
