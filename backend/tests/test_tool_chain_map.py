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
            "get_cost_analytics",
            "get_cost_summary",
            "create_cost_record",
            "create_crop_cycle",
            "create_crop_template",
            "create_operation_work_order",
            "get_crop_cycle_info",
            "get_recent_farm_logs",
            "get_farm_status",
            "get_labor_payables",
            "get_operation_work_orders",
            "log_farm_activity",
            "settle_debt",
            "settle_labor_payment",
            "update_crop_cycle",
            "update_crop_stage",
            "update_operation_work_order",
            "get_weather_forecast",
            "web_search",
        }
        assert set(TOOL_CHAIN_MAP.keys()) == expected_keys

    def test_query_tools_link_to_farm_status(self):
        """查询类工具应关联 get_farm_status。"""
        query_tools = [
            "get_weather_forecast",
            "get_cost_summary",
            "get_cost_analytics",
            "get_crop_cycle_info",
            "get_recent_farm_logs",
            "get_labor_payables",
            "get_operation_work_orders",
        ]
        for tool in query_tools:
            assert "get_farm_status" in TOOL_CHAIN_MAP[tool], (
                f"{tool} 应关联 get_farm_status"
            )

    def test_write_tools_have_no_chain(self):
        """写操作工具不应关联额外工具。"""
        write_tools = [
            "create_cost_record",
            "create_crop_cycle",
            "create_crop_template",
            "create_operation_work_order",
            "log_farm_activity",
            "settle_debt",
            "settle_labor_payment",
            "update_crop_cycle",
            "update_crop_stage",
            "update_operation_work_order",
            "get_farm_status",
        ]
        for tool in write_tools:
            assert TOOL_CHAIN_MAP[tool] == [], f"{tool} 不应有工具链关联"


class TestExpandByChain:
    """expand_by_chain 函数测试。"""

    def test_weather_chain(self):
        result = expand_by_chain({"get_weather_forecast"})
        assert "get_farm_status" in result

    def test_cost_chain(self):
        result = expand_by_chain({"get_cost_summary"})
        assert "get_farm_status" in result

    def test_crop_chain(self):
        result = expand_by_chain({"get_crop_cycle_info"})
        assert "get_farm_status" in result

    def test_labor_payables_chain(self):
        result = expand_by_chain({"get_labor_payables"})
        assert "get_farm_status" in result

    def test_operation_work_orders_chain(self):
        result = expand_by_chain({"get_operation_work_orders"})
        assert "get_farm_status" in result

    def test_write_skill_no_chain(self):
        result = expand_by_chain({"create_cost_record"})
        assert result == {"create_cost_record"}

    def test_empty_input(self):
        result = expand_by_chain(set())
        assert result == set()

    def test_multiple_inputs(self):
        result = expand_by_chain({"get_weather_forecast", "get_cost_summary"})
        assert "get_farm_status" in result
        assert "get_weather_forecast" in result
        assert "get_cost_summary" in result

    def test_max_tools_capped(self):
        result = expand_by_chain({"get_weather_forecast"}, max_tools=1)
        assert len(result) <= 1

    def test_original_tools_preserved(self):
        """扩展后的集合必须保留原始工具。"""
        original = {"get_cost_analytics", "get_crop_cycle_info"}
        result = expand_by_chain(original)
        for tool in original:
            assert tool in result

    def test_max_tools_zero(self):
        result = expand_by_chain({"get_weather_forecast"}, max_tools=0)
        assert result == set()
