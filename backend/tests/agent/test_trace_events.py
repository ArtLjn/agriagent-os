"""trace 事件齐全性测试。"""

from unittest.mock import MagicMock


class TestTraceEvents:
    def test_context_bundle_built_event_emitted(self):
        """ContextBundle 构造完成后必须埋 context_bundle_built 事件。"""
        from app.context.builder import ContextBuilder

        collector = MagicMock()
        collector.record = MagicMock()
        builder = ContextBuilder(
            selectors=[],
            max_tokens=1000,
            trace_collector=collector,
        )
        builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
        assert collector.record.called
        call_kwargs = collector.record.call_args.kwargs
        assert call_kwargs.get("node_name") == "context_bundle"

    def test_force_binding_trace_payload_structure(self):
        """tool_call_forced 事件的 payload 必须含 skill 名和 tool_choice。"""
        from app.agent.tool_selector import ToolSelectionResult
        from app.agent.runtime.llm_support import _resolve_tool_choice

        selection = ToolSelectionResult(
            tools=["get_weather_forecast"],
            force_binding=frozenset({"get_weather_forecast"}),
        )
        payload = {
            "forced_skills": sorted(selection.force_binding),
            "tool_choice": _resolve_tool_choice(selection),
            "selected_tools": selection.tools,
        }
        assert payload["forced_skills"] == ["get_weather_forecast"]
        assert payload["tool_choice"] == "required"
        assert "get_weather_forecast" in payload["selected_tools"]

    def test_data_source_payload_from_tool(self):
        """当有 tool_messages 时，data_source 必须是 tool:<skill_name>。"""
        from app.agent.runtime.nodes import _build_data_source_payload

        tool_calls = [{"name": "get_weather_forecast"}]
        payload = _build_data_source_payload(tool_calls=tool_calls)
        assert payload["data_source"] == "tool:get_weather_forecast"
        assert payload["has_tool_results"] is True

    def test_data_source_payload_without_tools(self):
        """当无 tool_messages 时，data_source 必须是 context_bundle。"""
        from app.agent.runtime.nodes import _build_data_source_payload

        payload = _build_data_source_payload(tool_calls=None)
        assert payload["data_source"] == "context_bundle"
        assert payload["has_tool_results"] is False
