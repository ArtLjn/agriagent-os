import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import AIMessage, HumanMessage


class TestBuildAdvisorAgent:
    """测试建议 Agent 构建。"""

    @patch("app.agent.graph.get_llm")
    def test_build_advisor_agent_returns_graph(self, mock_get_llm: MagicMock) -> None:
        """验证 build_advisor_agent 返回编译后的图。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        from app.agent.advisor import build_advisor_agent

        result = build_advisor_agent()

        assert result is not None


class TestBuildHistoryMessages:
    """测试 _build_history_messages 辅助函数。"""

    def test_returns_empty_when_no_conversation_id(self) -> None:
        """conversation_id 为 None 时返回空列表。"""
        from app.agent.advisor import _build_history_messages

        result = _build_history_messages(MagicMock(), None)

        assert result == []

    def test_returns_empty_when_db_is_none(self) -> None:
        """db 为 None 时返回空列表。"""
        from app.agent.advisor import _build_history_messages

        result = _build_history_messages(None, 1)

        assert result == []

    @patch("app.agent.advisor.get_recent_messages")
    def test_builds_history_from_db_records(self, mock_get_recent: MagicMock) -> None:
        """验证从数据库记录构建 LangChain 消息列表。"""
        from app.agent.advisor import _build_history_messages

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

    @patch("app.agent.advisor.get_recent_messages")
    def test_ignores_system_role_records(self, mock_get_recent: MagicMock) -> None:
        """验证 system 角色的记录被忽略。"""
        from app.agent.advisor import _build_history_messages

        rec_sys = MagicMock(role="system", content="系统消息")
        mock_get_recent.return_value = [rec_sys]

        mock_db = MagicMock()
        result = _build_history_messages(mock_db, 1)

        assert result == []

    @patch("app.agent.advisor.get_recent_messages")
    def test_custom_limit(self, mock_get_recent: MagicMock) -> None:
        """验证自定义 limit 参数传递。"""
        from app.agent.advisor import _build_history_messages

        mock_get_recent.return_value = []
        mock_db = MagicMock()

        _build_history_messages(mock_db, 5, limit=50)

        mock_get_recent.assert_called_once_with(mock_db, 5, limit=50)


class TestAdvisorInvoke:
    """测试建议 Agent 调用。"""

    @patch("app.agent.advisor._get_advisor_graph")
    def test_invoke_advisor_returns_response(self, mock_get_graph: MagicMock) -> None:
        """验证 invoke_advisor 返回 LLM 响应文本。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "建议：今天适合浇水。"
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
        mock_get_graph.return_value = mock_graph

        from app.agent.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("今天该做什么？"))

        assert result == "建议：今天适合浇水。"
        mock_graph.ainvoke.assert_called_once()
        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["farm_id"] == 1

    @patch("app.agent.advisor._get_advisor_graph")
    def test_invoke_advisor_passes_farm_id(self, mock_get_graph: MagicMock) -> None:
        """验证 invoke_advisor 正确传递 farm_id。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "建议内容"
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
        mock_get_graph.return_value = mock_graph

        from app.agent.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("问题", farm_id=42))

        assert result == "建议内容"
        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["farm_id"] == 42

    @patch("app.agent.advisor._build_history_messages")
    @patch("app.agent.advisor._get_advisor_graph")
    def test_invoke_advisor_with_history(
        self, mock_get_graph: MagicMock, mock_build_history: MagicMock
    ) -> None:
        """验证 invoke_advisor 注入历史消息。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "回复内容"
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
        mock_get_graph.return_value = mock_graph
        mock_build_history.return_value = [
            HumanMessage(content="之前的问题"),
            AIMessage(content="之前的回复"),
        ]

        mock_db = MagicMock()
        from app.agent.advisor import invoke_advisor

        result = asyncio.run(
            invoke_advisor("新问题", farm_id=1, db=mock_db, conversation_id=10)
        )

        assert result == "回复内容"
        call_args = mock_graph.ainvoke.call_args[0][0]
        messages = call_args["messages"]
        # 历史 2 条 + 当前 1 条
        assert len(messages) == 3
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "之前的问题"
        assert isinstance(messages[1], AIMessage)
        assert messages[1].content == "之前的回复"
        assert isinstance(messages[2], HumanMessage)
        assert messages[2].content == "新问题"

    @patch("app.agent.advisor._get_advisor_graph")
    def test_invoke_advisor_no_history_when_no_db(
        self, mock_get_graph: MagicMock
    ) -> None:
        """验证 db 为 None 时只有当前消息（无历史注入）。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "回复"
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
        mock_get_graph.return_value = mock_graph

        from app.agent.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("问题"))

        assert result == "回复"
        call_args = mock_graph.ainvoke.call_args[0][0]
        messages = call_args["messages"]
        # 无历史时只有当前消息 1 条
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "问题"


class TestAdvisorStream:
    """测试流式 Agent 调用。"""

    @patch("app.agent.advisor._build_history_messages")
    @patch("app.agent.advisor._get_advisor_graph")
    @pytest.mark.asyncio
    async def test_stream_advisor_with_history(
        self, mock_get_graph: MagicMock, mock_build_history: MagicMock
    ) -> None:
        """验证 stream_advisor 注入历史消息。"""
        from app.agent.advisor import stream_advisor

        mock_graph = MagicMock()

        async def _fake_astream(*args, **kwargs):
            yield {"agent": {"messages": [AIMessage(content="流式回复")]}}

        mock_graph.astream = _fake_astream
        mock_get_graph.return_value = mock_graph
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
        mock_build_history.assert_called_once_with(mock_db, 5)
