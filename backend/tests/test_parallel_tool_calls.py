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
