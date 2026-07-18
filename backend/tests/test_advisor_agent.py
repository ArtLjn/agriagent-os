import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.executor.models import PendingActionDecision


class TestBuildAdvisorAgent:
    """测试建议 Agent 构建。"""

    @patch("app.agent.runtime.nodes.get_llm")
    def test_build_advisor_agent_returns_graph(self, mock_get_llm: MagicMock) -> None:
        """验证 build_advisor_agent 返回编译后的图。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        from app.application.advice.advisor import build_advisor_agent

        result = build_advisor_agent()

        assert result is not None


class TestBuildHistoryMessages:
    """测试 _build_history_messages 辅助函数。"""

    def test_returns_empty_when_no_conversation_id(self) -> None:
        """conversation_id 为 None 时返回空列表。"""
        from app.application.advice.advisor import _build_history_messages

        result = _build_history_messages(MagicMock(), None)

        assert result == []

    def test_returns_empty_when_db_is_none(self) -> None:
        """db 为 None 时返回空列表。"""
        from app.application.advice.advisor import _build_history_messages

        result = _build_history_messages(None, 1)

        assert result == []

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_builds_history_from_db_records(self, mock_get_recent: MagicMock) -> None:
        """验证从数据库记录构建 LangChain 消息列表。"""
        from app.application.advice.advisor import _build_history_messages

        rec_user = MagicMock(role="user", content="你好")
        rec_asst = MagicMock(role="assistant", content="你好！")
        mock_get_recent.return_value = [rec_user, rec_asst]

        mock_db = MagicMock()
        result = _build_history_messages(mock_db, 42)

        assert len(result) == 2
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "你好"
        assert isinstance(result[1], AIMessage)
        assert result[1].content == "你好！"
        mock_get_recent.assert_called_once_with(mock_db, 42, limit=20)

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_ignores_system_role_records(self, mock_get_recent: MagicMock) -> None:
        """验证 system 角色的记录被忽略。"""
        from app.application.advice.advisor import _build_history_messages

        rec_sys = MagicMock(role="system", content="系统消息")
        mock_get_recent.return_value = [rec_sys]

        mock_db = MagicMock()
        result = _build_history_messages(mock_db, 1)

        assert result == []

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_custom_limit(self, mock_get_recent: MagicMock) -> None:
        """验证自定义 limit 参数传递。"""
        from app.application.advice.advisor import _build_history_messages

        mock_get_recent.return_value = []
        mock_db = MagicMock()

        _build_history_messages(mock_db, 5, limit=50)

        mock_get_recent.assert_called_once_with(mock_db, 5, limit=50)

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_long_history_keeps_summary_and_recent_messages(
        self, mock_get_recent: MagicMock
    ) -> None:
        """长会话历史应摘要早期内容，并完整保留最近消息。"""
        from app.application.advice.advisor import _build_history_messages

        mock_get_recent.return_value = [
            MagicMock(role="user", content="你的功能"),
            MagicMock(
                role="assistant", content="我是芽芽，可以查数据、记账、管理种植。"
            ),
            MagicMock(role="user", content="我的茬口"),
            MagicMock(
                role="assistant", content="活跃茬口有夏季水稻、夏季苹果、夏季玉米。"
            ),
            MagicMock(role="user", content="水稻今天打药了"),
            MagicMock(role="assistant", content="已记录水稻打药。"),
            MagicMock(role="user", content="我想种橘子"),
            MagicMock(role="assistant", content="需要我帮你创建橘子茬口吗？"),
        ]

        result = _build_history_messages(
            MagicMock(),
            42,
            recent_message_limit=2,
        )

        assert len(result) == 3
        assert isinstance(result[0], AIMessage)
        assert "早期对话摘要" in result[0].content
        assert "你的功能" in result[0].content
        assert "夏季水稻" in result[0].content
        assert isinstance(result[1], HumanMessage)
        assert result[1].content == "我想种橘子"

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_current_user_input_removed_before_history_summary(
        self, mock_get_recent: MagicMock
    ) -> None:
        """当前用户输入如果已写入数据库，应先去重再做历史摘要。"""
        from app.application.advice.advisor import _build_history_messages

        mock_get_recent.return_value = [
            MagicMock(role="user", content="你的功能"),
            MagicMock(role="assistant", content="我是芽芽。"),
            MagicMock(role="user", content="第一个问题是"),
        ]

        result = _build_history_messages(
            MagicMock(),
            42,
            current_user_input="第一个问题是",
            recent_message_limit=1,
        )

        assert all(message.content != "第一个问题是" for message in result)


class TestAdvisorInvoke:
    """测试建议 Agent 调用。"""

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_returns_response(
        self, mock_loop: AsyncMock, mock_pending: AsyncMock
    ) -> None:
        """验证 invoke_advisor 返回 LLM 响应文本。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "建议：今天适合浇水。"
        mock_loop.return_value = {"messages": [mock_msg]}

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("今天该做什么？", farm_id=1))

        assert result == "建议：今天适合浇水。"
        mock_loop.assert_awaited_once()
        call_args = mock_loop.await_args.args[0]
        assert call_args["farm_id"] == 1

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_passes_farm_id(
        self, mock_loop: AsyncMock, mock_pending: AsyncMock
    ) -> None:
        """验证 invoke_advisor 正确传递 farm_id。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "建议内容"
        mock_loop.return_value = {"messages": [mock_msg]}

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("问题", farm_id=42))

        assert result == "建议内容"
        call_args = mock_loop.await_args.args[0]
        assert call_args["farm_id"] == 42

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor._async_build_history_messages")
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_with_history(
        self,
        mock_loop: AsyncMock,
        mock_build_history: MagicMock,
        mock_pending: AsyncMock,
    ) -> None:
        """验证 invoke_advisor 注入历史消息。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "回复内容"
        mock_loop.return_value = {"messages": [mock_msg]}
        mock_build_history.return_value = [
            HumanMessage(content="之前的问题"),
            AIMessage(content="之前的回复"),
        ]

        mock_db = MagicMock()
        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(
            invoke_advisor("新问题", farm_id=1, db=mock_db, conversation_id=10)
        )

        assert result == "回复内容"
        call_args = mock_loop.await_args.args[0]
        messages = call_args["messages"]
        # 历史 2 条 + 当前 1 条
        assert len(messages) == 3
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "之前的问题"
        assert isinstance(messages[1], AIMessage)
        assert messages[1].content == "之前的回复"
        assert isinstance(messages[2], HumanMessage)
        assert messages[2].content == "新问题"

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_no_history_when_no_db(
        self, mock_loop: AsyncMock, mock_pending: AsyncMock
    ) -> None:
        """验证 db 为 None 时只有当前消息（无历史注入）。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "回复"
        mock_loop.return_value = {"messages": [mock_msg]}

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("问题", farm_id=1))

        assert result == "回复"
        call_args = mock_loop.await_args.args[0]
        messages = call_args["messages"]
        # 无历史时只有当前消息 1 条
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "问题"


class TestAdvisorStream:
    """测试流式 Agent 调用。"""

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor._async_build_history_messages")
    @patch("app.application.advice.advisor.stream_agent_loop")
    @pytest.mark.asyncio
    async def test_stream_advisor_with_history(
        self,
        mock_stream_loop: MagicMock,
        mock_build_history: MagicMock,
        mock_pending: AsyncMock,
    ) -> None:
        """验证 stream_advisor 注入历史消息。"""
        from app.application.advice.advisor import stream_advisor

        mock_pending.return_value = PendingActionDecision.unhandled()

        async def _fake_astream(*args, **kwargs):
            yield {"llm": {"messages": [AIMessage(content="流式回复")]}}

        mock_stream_loop.side_effect = _fake_astream
        mock_build_history.return_value = [
            HumanMessage(content="历史问题"),
        ]

        mock_db = MagicMock()
        chunks = []
        async for chunk in stream_advisor(
            "新问题", farm_id=1, db=mock_db, conversation_id=5
        ):
            chunks.append(chunk)

        assert len(chunks) >= 1
        mock_build_history.assert_awaited_once_with(
            mock_db,
            5,
            current_user_input="新问题",
        )
