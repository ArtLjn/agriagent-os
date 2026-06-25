# backend/tests/agent/test_select_tools_force_binding.py
"""select_tools 强制绑定信号单测。"""
from unittest.mock import MagicMock

from app.agent.tool_selector import select_tools


def _fake_tool(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


class TestSelectToolsForceBinding:
    def test_weather_input_forces_get_weather_forecast(self):
        all_tools = [_fake_tool("get_weather_forecast")]
        result = select_tools("今天天气怎么样", all_tools)
        assert "get_weather_forecast" in result.tools
        assert "get_weather_forecast" in result.force_binding

    def test_force_binding_survives_difference_update(self):
        """强制绑定不被 select_tools 内部裁剪吃掉。"""
        all_tools = [_fake_tool("get_crop_cycles"), _fake_tool("get_farm_status")]
        # "我的茬口" 命中 get_crop_cycles，正常情况下会被 difference_update 互斥逻辑影响
        # 但 force binding 应当穿透
        result = select_tools("我的茬口有哪些", all_tools)
        assert "get_crop_cycles" in result.tools
        assert "get_crop_cycles" in result.force_binding

    def test_no_force_binding_for_chitchat(self):
        all_tools = [_fake_tool("get_weather_forecast")]
        result = select_tools("你好", all_tools)
        assert "get_weather_forecast" not in result.force_binding
        assert "get_weather_forecast" not in result.tools

    def test_force_binding_tools_are_subset_of_tools(self):
        all_tools = [_fake_tool("get_weather_forecast")]
        result = select_tools("天气预报", all_tools)
        assert result.force_binding.issubset(set(result.tools))
