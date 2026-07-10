"""端到端验证 function calling 链路。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import compile_advisor_graph
from app.prompt.registry import get_registry


@pytest.fixture(autouse=True)
def _register_prompt_templates():
    """为所有测试注册 system_base 模板，避免 KeyError。"""
    registry = get_registry()
    registry.register(
        "system_base",
        "1.0",
        "你是农业顾问。{{ display_name }} {{ farm_location }} {{ current_season }}",
    )
    yield


class TestFunctionCallingE2E:
    """端到端验证 function calling 链路。"""

    @patch("app.agent.runtime.tool_executor.get_langchain_tools")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.llm_support.SessionLocal")
    @pytest.mark.asyncio
    async def test_weather_query_triggers_tool_call(
        self,
        mock_session,
        mock_get_llm,
        _mock_quota,
        mock_get_tools,
        mock_executor_tools,
    ):
        """天气查询应触发 get_weather_forecast tool call。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            display_name="老李"
        )
        mock_session.return_value = mock_db

        mock_tool = MagicMock()
        mock_tool.name = "get_weather_forecast"
        mock_get_tools.return_value = [mock_tool]
        mock_executor_tools.return_value = [mock_tool]

        mock_llm = MagicMock()
        tool_call_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "get_weather_forecast", "args": {"city": "苏州"}, "id": "tc1"}
            ],
        )
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(
            side_effect=[tool_call_msg, AIMessage(content="明天苏州晴")]
        )
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="明天苏州什么天气")]}
        )

        last_msg = result["messages"][-1]
        assert "苏州" in last_msg.content
        mock_llm.ainvoke.assert_called()

    @patch("app.agent.runtime.tool_executor.get_langchain_tools")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.llm_support.SessionLocal")
    @pytest.mark.asyncio
    async def test_chat_query_does_not_trigger_tool_call(
        self,
        mock_session,
        mock_get_llm,
        _mock_quota,
        mock_get_tools,
        mock_executor_tools,
    ):
        """闲聊不应触发 tool call，直接返回文本。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            display_name="老李"
        )
        mock_session.return_value = mock_db

        mock_get_tools.return_value = []
        mock_executor_tools.return_value = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="你好老李，有啥事？")
        )
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        result = await graph.ainvoke({"messages": [HumanMessage(content="你好")]})

        last_msg = result["messages"][-1]
        assert last_msg.content == "你好老李，有啥事？"

    @patch("app.agent.runtime.tool_executor.get_langchain_tools")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.llm_support.SessionLocal")
    @pytest.mark.asyncio
    async def test_pre_filter_reduces_tools_before_binding(
        self,
        mock_session,
        mock_get_llm,
        _mock_quota,
        mock_get_tools,
        mock_executor_tools,
    ):
        """天气查询可绑定只读工具池，但不应绑定写工具。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            display_name="老李"
        )
        mock_session.return_value = mock_db

        weather_tool = MagicMock()
        weather_tool.name = "get_weather_forecast"
        cost_tool = MagicMock()
        cost_tool.name = "get_cost_summary"
        record_tool = MagicMock()
        record_tool.name = "create_cost_record"
        mock_get_tools.return_value = [weather_tool, cost_tool, record_tool]
        mock_executor_tools.return_value = [weather_tool, cost_tool, record_tool]

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="明天苏州晴"))
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        await graph.ainvoke({"messages": [HumanMessage(content="明天苏州什么天气")]})

        mock_llm.bind_tools.assert_called_once()
        bound_tools = mock_llm.bind_tools.call_args[0][0]
        bound_names = [t.name for t in bound_tools]
        assert "get_weather_forecast" in bound_names
        assert "create_cost_record" not in bound_names
        assert "get_cost_summary" in bound_names

    @patch("app.agent.runtime.tool_executor.get_langchain_tools")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.llm_support.SessionLocal")
    @pytest.mark.asyncio
    async def test_multi_turn_final_answer_binds_no_tools(
        self,
        mock_session,
        mock_get_llm,
        _mock_quota,
        mock_get_tools,
        mock_executor_tools,
    ):
        """多轮 tool call 场景下，final answer 轮不再绑定工具。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            display_name="老李"
        )
        mock_session.return_value = mock_db

        status_tool = MagicMock()
        status_tool.name = "get_farm_status"
        cost_tool = MagicMock()
        cost_tool.name = "get_cost_summary"
        mock_get_tools.return_value = [status_tool, cost_tool]
        mock_executor_tools.return_value = [status_tool, cost_tool]

        tool_call_msg = AIMessage(
            content="",
            tool_calls=[{"name": "get_farm_status", "args": {}, "id": "tc1"}],
        )
        final_msg = AIMessage(content="农场状态正常")

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_call_msg, final_msg])
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        await graph.ainvoke({"messages": [HumanMessage(content="农场最近怎么样")]})

        bind_calls = mock_llm.bind_tools.call_args_list
        assert len(bind_calls) == 1
        first_bound = [t.name for t in bind_calls[0][0][0]]
        assert "get_farm_status" in first_bound
        assert mock_llm.ainvoke.await_count == 2
