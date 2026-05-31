"""并行 tool calling 配置与 bind_tools 行为测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import compile_advisor_graph
from app.agent.prompt_registry import get_registry
from app.core.config import AIConfig


@pytest.fixture(autouse=True)
def _register_prompt_templates():
    """为所有测试注册 system_base 模板，避免 KeyError。"""
    registry = get_registry()
    registry.register(
        "system_base",
        "1.0",
        "你是农业顾问。{{ display_name }} "
        "{{ farm_location }} {{ current_season }}",
    )
    yield


class TestAIConfigParallel:
    """AIConfig.parallel_tool_calls 默认值与配置。"""

    def test_default_is_true(self):
        config = AIConfig()
        assert config.parallel_tool_calls is True

    def test_can_set_false(self):
        config = AIConfig(parallel_tool_calls=False)
        assert config.parallel_tool_calls is False


class TestBindToolsParallel:
    """bind_tools 根据 parallel_tool_calls 配置传入参数。"""

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.SessionLocal")
    @pytest.mark.asyncio
    async def test_bind_tools_passes_parallel_true_by_default(
        self, mock_session, mock_get_llm, mock_get_tools
    ):
        """parallel_tool_calls=True 时 bind_tools 传入该参数。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_db

        mock_tool = MagicMock()
        mock_tool.name = "get_weather_forecast"
        mock_get_tools.return_value = [mock_tool]

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="明天晴"))
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        await graph.ainvoke(
            {"messages": [HumanMessage(content="明天天气")]}
        )

        mock_llm.bind_tools.assert_called_once()
        call_kwargs = mock_llm.bind_tools.call_args[1]
        assert call_kwargs.get("parallel_tool_calls") is True

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.SessionLocal")
    @pytest.mark.asyncio
    async def test_bind_tools_omits_parallel_when_disabled(
        self, mock_session, mock_get_llm, mock_get_tools
    ):
        """parallel_tool_calls=False 时不传入该参数。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_db

        mock_tool = MagicMock()
        mock_tool.name = "get_weather_forecast"
        mock_get_tools.return_value = [mock_tool]

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="明天晴"))
        mock_get_llm.return_value = mock_llm

        with patch("app.agent.graph.settings") as mock_settings:
            mock_settings.ai.parallel_tool_calls = False
            mock_settings.ai.enable_thinking = False
            mock_settings.token_quota.over_quota_action = "warn"
            graph = compile_advisor_graph()
            await graph.ainvoke(
                {"messages": [HumanMessage(content="明天天气")]}
            )

        mock_llm.bind_tools.assert_called_once()
        call_kwargs = mock_llm.bind_tools.call_args[1]
        assert "parallel_tool_calls" not in call_kwargs or call_kwargs.get("parallel_tool_calls") is False


class TestParallelToolSnippet:
    """并行调用引导 snippet 加载与渲染。"""

    def test_snippet_loaded(self):
        from app.agent.prompt_composer import get_composer

        composer = get_composer()
        assert "p1-parallel-tool" in composer.list_snippets()

    def test_system_base_contains_parallel_guidance(self):
        from app.agent.prompt_composer import get_composer

        composer = get_composer()
        rendered = composer.compose(
            "system_base",
            variables={
                "display_name": "农友",
                "farm_location": "徐州",
                "current_season": "夏季",
            },
        )
        assert "并行工具调用" in rendered
        assert "同时返回所有需要的工具调用" in rendered


class TestParallelBatchTrace:
    """并行执行聚合 trace 日志测试。"""

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_collector")
    @pytest.mark.asyncio
    async def test_parallel_batch_trace_recorded(
        self, mock_get_collector, mock_get_tools
    ):
        """并行执行 2 个 Skill 时记录 parallel_batch 聚合 trace。"""
        mock_collector = MagicMock()
        mock_get_collector.return_value = mock_collector

        weather_tool = MagicMock()
        weather_tool.name = "get_weather_forecast"
        weather_tool.ainvoke = AsyncMock(return_value="晴天 25度")

        cost_tool = MagicMock()
        cost_tool.name = "get_cost_summary"
        cost_tool.ainvoke = AsyncMock(return_value="本月花费 500 元")

        mock_get_tools.return_value = [weather_tool, cost_tool]

        from app.agent.graph import _parallel_tool_node, AgentState

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "get_weather_forecast", "args": {"city": "徐州"}, "id": "tc1"},
                        {"name": "get_cost_summary", "args": {}, "id": "tc2"},
                    ],
                )
            ],
            "farm_id": 1,
        }

        result = await _parallel_tool_node(state)
        assert len(result["messages"]) == 2

        # 验证 parallel_batch trace 被记录
        batch_calls = [
            c for c in mock_collector.record.call_args_list
            if c[1].get("node_type") == "parallel_batch"
        ]
        assert len(batch_calls) == 1
        batch_data = batch_calls[0][1]
        assert batch_data["output_data"]["parallel_count"] == 2
        assert len(batch_data["output_data"]["skills"]) == 2

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_collector")
    @pytest.mark.asyncio
    async def test_single_skill_no_batch_trace(
        self, mock_get_collector, mock_get_tools
    ):
        """单 Skill 执行时不记录 parallel_batch trace。"""
        mock_collector = MagicMock()
        mock_get_collector.return_value = mock_collector

        weather_tool = MagicMock()
        weather_tool.name = "get_weather_forecast"
        weather_tool.ainvoke = AsyncMock(return_value="晴天 25度")
        mock_get_tools.return_value = [weather_tool]

        from app.agent.graph import _parallel_tool_node, AgentState

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "get_weather_forecast", "args": {"city": "徐州"}, "id": "tc1"},
                    ],
                )
            ],
            "farm_id": 1,
        }

        result = await _parallel_tool_node(state)
        assert len(result["messages"]) == 1

        # 验证没有 parallel_batch trace
        batch_calls = [
            c for c in mock_collector.record.call_args_list
            if c[1].get("node_type") == "parallel_batch"
        ]
        assert len(batch_calls) == 0
