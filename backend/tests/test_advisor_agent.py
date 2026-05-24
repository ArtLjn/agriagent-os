import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestBuildAdvisorAgent:
    """测试建议 Agent 构建。"""

    @patch("app.agents.graph.get_llm")
    def test_build_advisor_agent_returns_graph(self, mock_get_llm: MagicMock) -> None:
        """验证 build_advisor_agent 返回编译后的图。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        from app.agents.advisor import build_advisor_agent
        result = build_advisor_agent()

        assert result is not None


class TestAdvisorInvoke:
    """测试建议 Agent 调用。"""

    @patch("app.agents.advisor._get_advisor_graph")
    def test_invoke_advisor_returns_response(self, mock_get_graph: MagicMock) -> None:
        """验证 invoke_advisor 返回 LLM 响应文本。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "建议：今天适合浇水。"
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
        mock_get_graph.return_value = mock_graph

        from app.agents.advisor import invoke_advisor
        result = asyncio.run(invoke_advisor("今天该做什么？"))

        assert result == "建议：今天适合浇水。"
        mock_graph.ainvoke.assert_called_once()
        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["farm_id"] == 1

    @patch("app.agents.advisor._get_advisor_graph")
    def test_invoke_advisor_passes_farm_id(self, mock_get_graph: MagicMock) -> None:
        """验证 invoke_advisor 正确传递 farm_id。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "建议内容"
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
        mock_get_graph.return_value = mock_graph

        from app.agents.advisor import invoke_advisor
        result = asyncio.run(invoke_advisor("问题", farm_id=42))

        assert result == "建议内容"
        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["farm_id"] == 42
