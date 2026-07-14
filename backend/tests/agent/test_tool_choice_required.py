# backend/tests/agent/test_tool_choice_required.py
"""tool_choice=required 透传测试。"""


class TestToolChoiceRequired:
    def test_force_binding_sets_tool_choice_required(self):
        """select_tools 返回 force_binding 时，tool_choice 必须为 'required'。"""
        from app.agent.tool_selector import ToolSelectionResult
        from app.agent.runtime.llm_support import _resolve_tool_choice

        selection = ToolSelectionResult(
            tools=["weather"],
            force_binding=frozenset({"weather"}),
        )
        assert _resolve_tool_choice(selection) == "required"

    def test_no_force_binding_keeps_auto(self):
        from app.agent.tool_selector import ToolSelectionResult
        from app.agent.runtime.llm_support import _resolve_tool_choice

        selection = ToolSelectionResult(
            tools=["some_tool"],
            force_binding=frozenset(),
        )
        assert _resolve_tool_choice(selection) == "auto"

    def test_empty_tools_no_force_binding_keeps_auto(self):
        from app.agent.tool_selector import ToolSelectionResult
        from app.agent.runtime.llm_support import _resolve_tool_choice

        selection = ToolSelectionResult(
            tools=[],
            force_binding=frozenset(),
        )
        assert _resolve_tool_choice(selection) == "auto"
