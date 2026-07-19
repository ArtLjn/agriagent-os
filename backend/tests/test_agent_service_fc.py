"""FC 迁移验证测试。

验证 agent_service.py 已完成从 skillify 预路由到 ReAct Function Calling 的迁移：
1. _try_skillify_route / _execute_skill 函数已移除
2. build_skill_context / get_skill_manager 引用已清除
3. chat_with_agent / stream_chat_with_agent 全部走 ReAct loop 路径
4. pending action confirm/cancel 流程保留完整
"""

import inspect

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.commit.return_value = None
    db.rollback.return_value = None
    db.add.return_value = None
    farm = MagicMock()
    farm.id = 1
    farm.user_id = "test-user-001"
    db.query.return_value.filter.return_value.first.return_value = farm
    return db


async def _call_chat(db, message, **kwargs):
    from app.domains.conversation.agent_service import chat_with_agent

    return await chat_with_agent(db, message, **kwargs)


async def _stream_chat(message, **kwargs):
    from app.domains.conversation.agent_service import stream_chat_with_agent

    return stream_chat_with_agent(message, **kwargs)


class TestSkillifyRouteRemoved:
    """验证 skillify 预路由相关函数和导入已移除。"""

    def test_try_skillify_route_does_not_exist(self):
        import app.domains.conversation.agent_service as mod

        assert not hasattr(mod, "_try_skillify_route"), (
            "_try_skillify_route 仍然存在，需要移除"
        )

    def test_execute_skill_does_not_exist(self):
        import app.domains.conversation.agent_service as mod

        assert not hasattr(mod, "_execute_skill"), "_execute_skill 仍然存在，需要移除"

    def test_build_skill_context_not_in_source(self):
        import app.domains.conversation.agent_service as mod

        source = inspect.getsource(mod)
        assert "build_skill_context" not in source, (
            "build_skill_context 引用仍然存在于源码中"
        )

    def test_get_skill_manager_not_in_source(self):
        import app.domains.conversation.agent_service as mod

        source = inspect.getsource(mod)
        assert "get_skill_manager" not in source, (
            "get_skill_manager 引用仍然存在于源码中"
        )


class TestChatWithAgentRouting:
    """验证 chat_with_agent 所有请求走 invoke_advisor，无预路由。"""

    @pytest.mark.asyncio
    @patch("app.application.chat.use_case.invoke_advisor", new_callable=AsyncMock)
    @patch("app.domains.conversation.agent_service.get_pending", return_value=None)
    async def test_routes_through_invoke_advisor(
        self,
        mock_get_pending: MagicMock,
        mock_invoke: AsyncMock,
        mock_db: MagicMock,
    ):
        mock_invoke.return_value = "LLM 回复"
        result = await _call_chat(mock_db, "今天天气怎样", farm_id=1)
        assert result.reply == "LLM 回复"
        mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.application.chat.use_case.invoke_advisor", new_callable=AsyncMock)
    @patch("app.domains.conversation.agent_service.get_pending", return_value=None)
    async def test_no_skillify_pre_route(
        self,
        mock_get_pending: MagicMock,
        mock_invoke: AsyncMock,
        mock_db: MagicMock,
    ):
        mock_invoke.return_value = "回复"
        await _call_chat(mock_db, "查询成本记录", farm_id=1)
        mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.application.chat.use_case.invoke_advisor", new_callable=AsyncMock)
    @patch("app.domains.conversation.service.save_message")
    @patch("app.application.chat.use_case.get_or_create_conversation")
    @patch("app.domains.conversation.agent_service.get_pending", return_value=None)
    async def test_routes_with_session_id(
        self,
        mock_get_pending: MagicMock,
        mock_get_conv: MagicMock,
        mock_save_msg: MagicMock,
        mock_invoke: AsyncMock,
        mock_db: MagicMock,
    ):
        mock_invoke.return_value = "回复"
        mock_conv = MagicMock()
        mock_conv.id = 1
        mock_get_conv.return_value = mock_conv

        result = await _call_chat(mock_db, "问题", farm_id=1, session_id="s1")
        assert result.reply == "回复"
        mock_invoke.assert_called_once()


class TestPendingActionPreserved:
    """验证 pending action confirm/cancel 流程保留完整。"""

    @pytest.mark.asyncio
    @patch("app.application.chat.use_case.invoke_advisor", new_callable=AsyncMock)
    @patch(
        "app.application.chat.use_case.handle_pending_action",
        new_callable=AsyncMock,
    )
    async def test_confirm_executes_pending_action(
        self,
        mock_handle: AsyncMock,
        mock_invoke: AsyncMock,
        mock_db: MagicMock,
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_handle.return_value = PendingActionDecision.confirmed("已创建成本记录")

        result = await _call_chat(mock_db, "确认", farm_id=1)

        assert "已创建成本记录" in result.reply
        mock_handle.assert_awaited_once()
        mock_invoke.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.application.chat.use_case.invoke_advisor", new_callable=AsyncMock)
    @patch(
        "app.application.chat.use_case.handle_pending_action",
        new_callable=AsyncMock,
    )
    async def test_cancel_removes_pending(
        self,
        mock_handle: AsyncMock,
        mock_invoke: AsyncMock,
        mock_db: MagicMock,
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_handle.return_value = PendingActionDecision.canceled()

        result = await _call_chat(mock_db, "取消", farm_id=1)

        assert "取消" in result.reply
        mock_handle.assert_awaited_once()
        mock_invoke.assert_not_awaited()


class TestStreamChatWithAgentRouting:
    """验证 stream_chat_with_agent 所有请求走 stream_advisor。"""

    @pytest.mark.asyncio
    @patch("app.domains.conversation.agent_service.stream_advisor")
    @patch("app.domains.conversation.agent_service.get_pending", return_value=None)
    async def test_routes_through_stream_advisor(
        self,
        mock_get_pending: MagicMock,
        mock_stream: MagicMock,
    ):
        async def _fake_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        mock_stream.side_effect = _fake_stream

        gen = await _stream_chat("问题", farm_id=1)
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]
        mock_stream.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.domains.conversation.agent_service.stream_advisor")
    @patch("app.domains.conversation.agent_service.get_pending", return_value=None)
    async def test_no_skillify_pre_route_in_stream(
        self,
        mock_get_pending: MagicMock,
        mock_stream: MagicMock,
    ):
        async def _fake_stream(*args, **kwargs):
            yield "result"

        mock_stream.side_effect = _fake_stream

        gen = await _stream_chat("查询成本记录", farm_id=1)
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        mock_stream.assert_called_once()
