from unittest.mock import MagicMock, patch


class TestBuildReportAgent:
    """测试报告 Agent 构建。"""

    @patch("app.agents.report.create_react_agent")
    @patch("app.agents.report.get_llm")
    def test_build_report_agent_returns_graph(self, mock_get_llm: MagicMock, mock_create_react: MagicMock) -> None:
        """验证 build_report_agent 返回编译后的图。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_graph = MagicMock()
        mock_create_react.return_value = mock_graph

        from app.agents.report import build_report_agent
        result = build_report_agent()

        assert result is mock_graph
        mock_get_llm.assert_called_once()
        mock_create_react.assert_called_once()


class TestGenerateCycleReport:
    """测试周期报告生成。"""

    @patch("app.agents.report._get_report_graph")
    def test_generate_cycle_report_returns_text(self, mock_get_graph: MagicMock) -> None:
        """验证生成周期报告返回文本。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "周期报告：西瓜春茬总成本 2000 元..."
        mock_graph.invoke.return_value = {"messages": [mock_msg]}
        mock_get_graph.return_value = mock_graph

        from app.agents.report import generate_cycle_report
        result = generate_cycle_report(1)

        assert "周期报告" in result
