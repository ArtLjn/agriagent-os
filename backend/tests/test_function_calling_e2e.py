"""端到端验证 function calling 链路。"""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import compile_advisor_graph


class TestFunctionCallingE2E:
    """端到端验证 function calling 链路。"""

    @patch("app.agents.graph.get_langchain_tools")
    @patch("app.agents.graph.get_llm")
    @patch("app.agents.graph.farm_context_service.build_summary")
    @patch("app.agents.graph.SessionLocal")
    def test_weather_query_triggers_tool_call(
        self, mock_session, mock_summary, mock_get_llm, mock_get_tools
    ):
        """天气查询应触发 get_weather_forecast tool call。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            display_name="老李"
        )
        mock_session.return_value = mock_db
        mock_summary.return_value = "当前无种植计划"

        mock_tool = MagicMock()
        mock_tool.name = "get_weather_forecast"
        mock_get_tools.return_value = [mock_tool]

        mock_llm = MagicMock()
        tool_call_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "get_weather_forecast", "args": {"city": "苏州"}, "id": "tc1"}
            ],
        )
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = [tool_call_msg, AIMessage(content="明天苏州晴")]
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        result = graph.invoke({"messages": [HumanMessage(content="明天苏州什么天气")]})

        last_msg = result["messages"][-1]
        assert "苏州" in last_msg.content
        mock_llm.invoke.assert_called()

    @patch("app.agents.graph.get_langchain_tools")
    @patch("app.agents.graph.get_llm")
    @patch("app.agents.graph.farm_context_service.build_summary")
    @patch("app.agents.graph.SessionLocal")
    def test_chat_query_does_not_trigger_tool_call(
        self, mock_session, mock_summary, mock_get_llm, mock_get_tools
    ):
        """闲聊不应触发 tool call，直接返回文本。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            display_name="老李"
        )
        mock_session.return_value = mock_db
        mock_summary.return_value = "当前无种植计划"

        mock_get_tools.return_value = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = AIMessage(content="你好老李，有啥事？")
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        result = graph.invoke({"messages": [HumanMessage(content="你好")]})

        last_msg = result["messages"][-1]
        assert last_msg.content == "你好老李，有啥事？"
