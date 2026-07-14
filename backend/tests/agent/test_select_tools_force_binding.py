# backend/tests/agent/test_select_tools_force_binding.py
"""select_tools 查询不强制绑定契约。"""

from unittest.mock import MagicMock

from app.agent.tool_selector import select_tools


def _fake_tool(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


class TestSelectToolsForceBinding:
    def test_weather_input_selects_without_force_binding(self):
        all_tools = [_fake_tool("weather")]
        result = select_tools("今天天气怎么样", all_tools)
        assert "weather" in result.tools
        assert not result.force_binding

    def test_query_selection_does_not_force_bind(self):
        """普通读查询不再通过规则强制绑定工具。"""
        all_tools = [_fake_tool("manage_crop_cycle"), _fake_tool("get_farm_status")]
        result = select_tools("我的茬口有哪些", all_tools)
        assert "manage_crop_cycle" in result.tools
        assert not result.force_binding

    def test_no_force_binding_for_chitchat(self):
        all_tools = [_fake_tool("weather")]
        result = select_tools("你好", all_tools)
        assert "weather" not in result.force_binding
        assert "weather" not in result.tools

    def test_force_binding_field_stays_empty_for_query(self):
        all_tools = [_fake_tool("weather")]
        result = select_tools("天气预报", all_tools)
        assert result.force_binding == frozenset()
