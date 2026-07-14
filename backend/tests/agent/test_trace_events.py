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
            tools=["weather"],
            force_binding=frozenset({"weather"}),
        )
        payload = {
            "forced_skills": sorted(selection.force_binding),
            "tool_choice": _resolve_tool_choice(selection),
            "selected_tools": selection.tools,
        }
        assert payload["forced_skills"] == ["weather"]
        assert payload["tool_choice"] == "required"
        assert "weather" in payload["selected_tools"]

    def test_force_binding_trace_records_actual_skills(self):
        """regression: 调用实际 trace 函数，传入真实 force_binding，断言 forced_skills 非空。

        历史 bug：原实现 _record_tool_call_forced_trace 内部调用 _select_tools(user_msg, [])
        传入空工具列表，导致 select_tools 内部 force_binding 推断永远为空（因为
        `enabled_tool_names` 为空），最终 trace 中 forced_skills 始终为空列表，
        违反 §5.9.5 设计意图。

        修复后：force_binding 由 _route_tools 基于真实工具列表派生并透传至本函数。
        """
        from app.agent.runtime import nodes as nodes_mod

        collector = MagicMock()
        nodes_mod._record_tool_call_forced_trace(
            collector=collector,
            user_msg="今天天气如何",
            selected_names=["weather"],
            tool_choice="required",
            force_binding=("weather",),
        )
        assert collector.record.called, "trace 函数必须调用 collector.record"
        call_kwargs = collector.record.call_args.kwargs
        assert call_kwargs.get("node_name") == "tool_call_forced"
        output_data = call_kwargs.get("output_data", {})
        assert output_data.get("forced_skills") == ["weather"], (
            "forced_skills 必须包含真实 skill 名，不能为空列表"
        )
        assert output_data.get("tool_choice") == "required"
        assert "weather" in output_data.get("selected_tools", [])

    def test_data_source_payload_from_tool(self):
        """当有 tool_messages 时，data_source 必须是 tool:<skill_name>。"""
        from app.agent.runtime.nodes import _build_data_source_payload

        tool_calls = [{"name": "weather"}]
        payload = _build_data_source_payload(tool_calls=tool_calls)
        assert payload["data_source"] == "tool:weather"
        assert payload["has_tool_results"] is True

    def test_data_source_payload_without_tools(self):
        """当无 tool_messages 时，data_source 必须是 context_bundle。"""
        from app.agent.runtime.nodes import _build_data_source_payload

        payload = _build_data_source_payload(tool_calls=None)
        assert payload["data_source"] == "context_bundle"
        assert payload["has_tool_results"] is False

    def test_final_reply_data_source_uses_tool_call_id_when_tool_message_has_no_name(
        self,
    ):
        """ToolMessage 无 name 时，应从上一条 AIMessage.tool_calls 反查 skill 名。"""
        from langchain_core.messages import AIMessage, ToolMessage

        from app.agent.runtime.nodes import _tool_messages_for_data_source

        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-cycles",
                        "name": "manage_crop_cycle",
                        "args": {},
                    }
                ],
            ),
            ToolMessage(content="茬口列表", tool_call_id="call-cycles"),
        ]

        tool_calls = _tool_messages_for_data_source(messages)

        assert tool_calls == [{"name": "manage_crop_cycle"}]
