"""tool_selector 模块单元测试。"""

from unittest.mock import MagicMock

from app.agent.tool_selector import select_tools

ALL_TOOL_NAMES = [
    "create_cost_record",
    "settle_debt",
    "create_crop_cycle",
    "log_farm_activity",
    "update_crop_stage",
    "get_weather_forecast",
    "get_cost_summary",
    "get_cost_analytics",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
]


def _make_tools(names=None):
    names = names or ALL_TOOL_NAMES
    tools = []
    for n in names:
        m = MagicMock(spec=["name"])
        m.name = n
        tools.append(m)
    return tools


class TestWritePatternMatching:
    def test_cost_record_with_amount(self):
        result = select_tools("卖了西瓜5000块", _make_tools())
        assert "create_cost_record" in result

    def test_cost_record_explicit_trigger(self):
        result = select_tools("记一笔，买了化肥", _make_tools())
        assert "create_cost_record" in result

    def test_cost_record_colloquial_5w(self):
        result = select_tools("卖西瓜收入5w", _make_tools())
        assert "create_cost_record" in result

    def test_cost_record_no_amount(self):
        result = select_tools("买了化肥", _make_tools())
        assert "create_cost_record" in result

    def test_settle_debt_standard(self):
        result = select_tools("还了老王200", _make_tools())
        assert "settle_debt" in result

    def test_settle_debt_variant(self):
        result = select_tools("把欠老王的账结了", _make_tools())
        assert "settle_debt" in result

    def test_create_crop_cycle_with_crop(self):
        result = select_tools("创建春茬种植西瓜", _make_tools())
        assert "create_crop_cycle" in result

    def test_create_crop_cycle_season(self):
        result = select_tools("秋茬种番茄", _make_tools())
        assert "create_crop_cycle" in result

    def test_log_farm_activity_watering(self):
        result = select_tools("今天浇了水", _make_tools())
        assert "log_farm_activity" in result

    def test_log_farm_activity_fertilizing(self):
        result = select_tools("刚施了肥", _make_tools())
        assert "log_farm_activity" in result

    def test_log_farm_activity_spraying(self):
        result = select_tools("打药了", _make_tools())
        assert "log_farm_activity" in result

    def test_update_crop_stage_seedling(self):
        result = select_tools("西瓜进苗期了", _make_tools())
        assert "update_crop_stage" in result

    def test_update_crop_stage_flowering(self):
        result = select_tools("到开花期了", _make_tools())
        assert "update_crop_stage" in result

    def test_ambiguous_triggers_fallback(self):
        result = select_tools("买化肥", _make_tools())
        assert result == ALL_TOOL_NAMES


class TestQueryKeywordMatching:
    def test_weather_query(self):
        result = select_tools("今天天气", _make_tools())
        assert "get_weather_forecast" in result

    def test_balance_query(self):
        result = select_tools("我的余额", _make_tools())
        assert "get_cost_summary" in result

    def test_monthly_quota_query(self):
        result = select_tools("我的月额", _make_tools())
        assert "get_cost_summary" in result

    def test_trend_analytics(self):
        result = select_tools("比去年赚得多吗", _make_tools())
        assert "get_cost_analytics" in result

    def test_multi_intent(self):
        result = select_tools("看看天气和成本", _make_tools())
        assert "get_weather_forecast" in result
        assert "get_cost_summary" in result


class TestFallback:
    def test_greeting_returns_all(self):
        result = select_tools("你好", _make_tools())
        assert result == ALL_TOOL_NAMES

    def test_planting_advice_returns_all(self):
        result = select_tools("西瓜怎么种", _make_tools())
        assert result == ALL_TOOL_NAMES

    def test_all_tools_present(self):
        tools = _make_tools()
        result = select_tools("随便聊聊", tools)
        assert set(result) == set(ALL_TOOL_NAMES)
        assert len(result) == len(ALL_TOOL_NAMES)

    def test_empty_message_returns_all(self):
        result = select_tools("", _make_tools())
        assert result == ALL_TOOL_NAMES

    def test_empty_tools_returns_empty(self):
        result = select_tools("今天天气", [])
        assert result == []

    def test_top_k_limits_results(self):
        result = select_tools("看看天气和成本和余额和趋势", _make_tools(), top_k=2)
        assert len(result) <= 2
