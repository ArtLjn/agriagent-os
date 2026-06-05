"""测试 _llm_node 双阶段模型选择 + 请求内重试循环。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def _make_state(messages, farm_id=1):
    """构造 AgentState。"""
    return {"messages": messages, "farm_id": farm_id}


def _make_llm_mock(response_content="OK", tool_calls=None):
    """构造 mock LLM 实例。"""
    llm = AsyncMock()
    resp = MagicMock()
    resp.content = response_content
    resp.tool_calls = tool_calls or []
    resp.response_metadata = {}
    llm.ainvoke = AsyncMock(return_value=resp)
    llm.bind_tools = MagicMock(return_value=llm)
    llm.model_name = "test-model"
    return llm, resp


def test_filter_tool_calls_by_selected_drops_unbound_tool():
    """手动 JSON 工具调用只能执行本轮绑定的候选工具。"""
    from app.agent.runtime.direct_routing import filter_tool_calls_by_selected

    selected_tool = MagicMock()
    selected_tool.name = "create_crop_cycle"
    tool_calls = [
        {"name": "create_crop_template", "args": {"crop_name": "小麦"}, "id": "tc1"},
        {"name": "create_crop_cycle", "args": {"crop_name": "小麦"}, "id": "tc2"},
    ]

    result = filter_tool_calls_by_selected(tool_calls, [selected_tool])

    assert result == [
        {"name": "create_crop_cycle", "args": {"crop_name": "小麦"}, "id": "tc2"}
    ]


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前后重置全局单例。"""
    import app.core.llm_client_manager as mgr_module

    mgr_module._manager = None
    yield
    mgr_module._manager = None


class TestDualPhaseModelSelection:
    """测试双阶段模型：无 tool 结果用 tool-selection，有 tool 结果用 generation。"""

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    def test_no_tool_results_uses_generation_role(
        self,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """默认 agent intent 无 ToolMessage 时使用 generation 角色。"""
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock()
        mock_get_llm.return_value = llm

        from app.agent.graph import _llm_node

        state = _make_state([HumanMessage(content="你好")])
        asyncio.get_event_loop().run_until_complete(_llm_node(state))

        mock_get_llm.assert_called_once_with(role="generation")

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="天气如何")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    def test_with_tool_results_uses_generation_role(
        self,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """有 ToolMessage 时，get_llm 应以 role='generation' 调用。"""
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock()
        mock_get_llm.return_value = llm

        from app.agent.graph import _llm_node

        tool_msg = ToolMessage(content="晴，25度", tool_call_id="tc1")
        state = _make_state(
            [
                HumanMessage(content="天气如何"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "get_weather", "id": "tc1", "args": {}}],
                ),
                tool_msg,
            ]
        )
        asyncio.get_event_loop().run_until_complete(_llm_node(state))

        mock_get_llm.assert_called_once_with(role="generation")


class TestRetryLoop:
    """测试请求内重试循环。"""

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_successful_llm_call_logs_completion(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
        caplog,
    ):
        """LLM 成功调用后应输出可见的完成日志。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock(response_content="你好")
        mock_get_llm.return_value = llm

        from app.agent.graph import _llm_node

        with caplog.at_level("INFO", logger="app.agent.runtime.nodes"):
            state = _make_state([HumanMessage(content="你好")])
            asyncio.get_event_loop().run_until_complete(_llm_node(state))

        assert "LLM 调用完成" in caplog.text
        assert "key=test/model" in caplog.text
        assert "model=test-model" in caplog.text

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_success_on_first_attempt_no_retry(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """第一次成功时不触发重试。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock()
        mock_get_llm.return_value = llm

        from app.agent.graph import _llm_node

        state = _make_state([HumanMessage(content="你好")])
        asyncio.get_event_loop().run_until_complete(_llm_node(state))

        assert mock_get_llm.call_count == 1
        mock_success.assert_called_once_with("test/model")
        mock_failure.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_provider_error_triggers_retry(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """PROVIDER 级错误（如 ConnectionError）应触发重试。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        call_count = 0

        def make_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            llm = AsyncMock()
            llm.model_name = f"model-{call_count}"
            llm.bind_tools = MagicMock(return_value=llm)

            if call_count == 1:
                # 第一次调用失败（PROVIDER 级错误）
                llm.ainvoke = AsyncMock(side_effect=ConnectionError("连接失败"))
            else:
                # 第二次调用成功
                resp = MagicMock()
                resp.content = "重试成功"
                resp.tool_calls = []
                resp.response_metadata = {}
                llm.ainvoke = AsyncMock(return_value=resp)

            return llm

        mock_get_llm.side_effect = make_llm

        # classify_error 对 ConnectionError 返回 PROVIDER
        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.graph import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # 第一次失败 + 第二次重试成功
        assert call_count == 2
        mock_failure.assert_called_once()
        mock_success.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_model_error_no_retry(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """MODEL 级错误（如 400 schema 错误）不重试，直接抛出。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm = AsyncMock()
        llm.model_name = "test-model"
        llm.bind_tools = MagicMock(return_value=llm)
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("400 schema error"))
        mock_get_llm.return_value = llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error", return_value=ErrorLevel.MODEL
        ):
            from app.agent.graph import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            with pytest.raises(RuntimeError, match="400 schema error"):
                asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # MODEL 级错误不重试，get_llm 只调用一次
        assert mock_get_llm.call_count == 1
        mock_failure.assert_called_once()
        mock_success.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_all_retries_exhausted_raises(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """所有重试用尽后，最后一次异常抛出。"""
        mock_settings.ai = MagicMock(failover_max_retries=2, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        call_count = 0

        def make_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            llm = AsyncMock()
            llm.model_name = f"model-{call_count}"
            llm.bind_tools = MagicMock(return_value=llm)
            llm.ainvoke = AsyncMock(side_effect=ConnectionError("持续连接失败"))
            return llm

        mock_get_llm.side_effect = make_llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.graph import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            with pytest.raises(ConnectionError, match="持续连接失败"):
                asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # failover_max_retries=2，调用 2 次
        assert call_count == 2
        assert mock_failure.call_count == 2
        mock_success.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_retry_rebinds_tools(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """重试时应重新调用 bind_tools 绑定选中的工具。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()

        tool_mock = MagicMock()
        tool_mock.name = "web_search"
        mock_tools.return_value = [tool_mock]

        call_count = 0

        def make_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            llm = AsyncMock()
            llm.model_name = f"model-{call_count}"
            llm.bind_tools = MagicMock(return_value=llm)

            if call_count == 1:
                llm.ainvoke = AsyncMock(side_effect=ConnectionError("连接失败"))
            else:
                resp = MagicMock()
                resp.content = "成功"
                resp.tool_calls = []
                resp.response_metadata = {}
                llm.ainvoke = AsyncMock(return_value=resp)

            return llm

        mock_get_llm.side_effect = make_llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.graph import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # 两次调用都应 bind_tools
        assert call_count == 2


class TestRetryWithSingleAttempt:
    """测试 failover_max_retries=1 时退化为无重试行为。"""

    @pytest.mark.asyncio
    @patch("app.agent.runtime.nodes._record_llm_success")
    @patch("app.agent.runtime.nodes._record_llm_failure")
    @patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model")
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.nodes._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.nodes.get_request_date")
    @patch("app.agent.runtime.nodes._get_season", return_value="春季")
    @patch("app.agent.runtime.nodes.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_single_attempt_no_retry_on_failure(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """failover_max_retries=1 时失败直接抛出，不重试。"""
        mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm = AsyncMock()
        llm.model_name = "test-model"
        llm.bind_tools = MagicMock(return_value=llm)
        llm.ainvoke = AsyncMock(side_effect=ConnectionError("连接失败"))
        mock_get_llm.return_value = llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.graph import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            with pytest.raises(ConnectionError):
                asyncio.get_event_loop().run_until_complete(_llm_node(state))

        assert mock_get_llm.call_count == 1
