"""TOOL_CHAIN_MAP + expand_by_chain 单元测试。"""

import pytest

from app.agent.tool_selector import TOOL_CHAIN_MAP, expand_by_chain

pytestmark = pytest.mark.no_db


class TestToolChainMap:
    """工具链关联映射测试。"""

    def test_map_is_dict(self):
        assert isinstance(TOOL_CHAIN_MAP, dict)

    def test_map_contains_all_known_tools(self):
        expected_keys = {
            "manage_cost",
            "manage_crop_cycle",
            "manage_crop_templates",
            "create_operation_work_order",
            "get_recent_farm_logs",
            "manage_farm_logs",
            "get_farm_status",
            "get_labor_payables",
            "get_workers",
            "get_operation_work_orders",
            "get_cost_categories",
            "manage_cost_categories",
            "get_planting_units",
            "manage_planting_units",
            "get_user_settings",
            "manage_user_settings",
            "log_farm_activity",
            "settle_labor_payment",
            "update_operation_work_order",
            "manage_workers",
            "manage_wages",
            "get_weather_forecast",
            "web_search",
        }
        assert set(TOOL_CHAIN_MAP.keys()) == expected_keys

    def test_only_daily_advice_support_tools_link_to_farm_status(self):
        """普通查询工具不应隐式关联 get_farm_status。"""
        query_tools_without_farm_status = [
            "manage_cost",
            "manage_crop_cycle",
            "get_recent_farm_logs",
            "get_labor_payables",
            "get_workers",
            "get_operation_work_orders",
            "get_cost_categories",
            "get_planting_units",
            "manage_crop_templates",
            "get_user_settings",
        ]
        for tool in query_tools_without_farm_status:
            assert TOOL_CHAIN_MAP[tool] == [], f"{tool} 不应关联 get_farm_status"

        assert TOOL_CHAIN_MAP["get_weather_forecast"] == []

    def test_write_tools_have_no_chain(self):
        """写操作工具不应关联额外工具。"""
        write_tools = [
            "manage_cost",
            "manage_crop_cycle",
            "manage_crop_templates",
            "create_operation_work_order",
            "log_farm_activity",
            "manage_farm_logs",
            "settle_labor_payment",
            "update_operation_work_order",
            "manage_workers",
            "manage_wages",
            "manage_cost_categories",
            "manage_planting_units",
            "manage_user_settings",
            "get_farm_status",
        ]
        for tool in write_tools:
            assert TOOL_CHAIN_MAP[tool] == [], f"{tool} 不应有工具链关联"


class TestExpandByChain:
    """expand_by_chain 函数测试。"""

    def test_cost_chain(self):
        result = expand_by_chain({"manage_cost"})
        assert result == {"manage_cost"}

    def test_crop_chain(self):
        result = expand_by_chain({"manage_crop_cycle"})
        assert result == {"manage_crop_cycle"}

    def test_labor_payables_chain(self):
        result = expand_by_chain({"get_labor_payables"})
        assert result == {"get_labor_payables"}

    def test_operation_work_orders_chain(self):
        result = expand_by_chain({"get_operation_work_orders"})
        assert result == {"get_operation_work_orders"}

    def test_workers_chain(self):
        result = expand_by_chain({"get_workers"})
        assert result == {"get_workers"}

    def test_write_skill_no_chain(self):
        result = expand_by_chain({"manage_cost"})
        assert result == {"manage_cost"}

    def test_empty_input(self):
        result = expand_by_chain(set())
        assert result == set()

    def test_multiple_inputs(self):
        result = expand_by_chain({"get_weather_forecast", "manage_cost"})
        assert result == {"get_weather_forecast", "manage_cost"}

    def test_max_tools_capped(self):
        result = expand_by_chain({"get_weather_forecast"}, max_tools=1)
        assert len(result) <= 1

    def test_original_tools_preserved(self):
        """扩展后的集合必须保留原始工具。"""
        original = {"manage_cost", "manage_crop_cycle"}
        result = expand_by_chain(original)
        for tool in original:
            assert tool in result

    def test_max_tools_zero(self):
        result = expand_by_chain({"get_weather_forecast"}, max_tools=0)
        assert result == set()
