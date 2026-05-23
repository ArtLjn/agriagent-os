from unittest.mock import MagicMock, patch


class TestBuildAdvisorAgent:
    """测试建议 Agent 构建。"""

    @patch("app.agents.graph.create_react_agent")
    @patch("app.agents.graph.get_llm")
    def test_build_advisor_agent_returns_graph(self, mock_get_llm: MagicMock, mock_create_react: MagicMock) -> None:
        """验证 build_advisor_agent 返回编译后的图。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_graph = MagicMock()
        mock_create_react.return_value = mock_graph

        from app.agents.advisor import build_advisor_agent
        result = build_advisor_agent()

        assert result is mock_graph
        mock_get_llm.assert_called_once()
        mock_create_react.assert_called_once()


class TestAdvisorInvoke:
    """测试建议 Agent 调用。"""

    @patch("app.agents.advisor._get_advisor_graph")
    def test_invoke_advisor_returns_response(self, mock_get_graph: MagicMock) -> None:
        """验证 invoke_advisor 返回 LLM 响应文本。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "建议：今天适合浇水。"
        mock_graph.invoke.return_value = {"messages": [mock_msg]}
        mock_get_graph.return_value = mock_graph

        from app.agents.advisor import invoke_advisor
        result = invoke_advisor("今天该做什么？")

        assert result == "建议：今天适合浇水。"
