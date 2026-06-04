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

    def test_create_crop_cycle_intent_with_new_crop_name(self):
        result = select_tools("我想种小麦", _make_tools())
        assert result == ["create_crop_cycle"]

    def test_planting_advice_with_intent_phrase_does_not_write(self):
        result = select_tools("我想种小麦要注意什么", _make_tools())
        assert result == ALL_TOOL_NAMES

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

    def test_weekly_bill_query(self):
        result = select_tools("查一下本周账单", _make_tools())
        assert "get_cost_summary" in result

    def test_yearly_bill_query(self):
        result = select_tools("今年账单汇总", _make_tools())
        assert "get_cost_summary" in result

    def test_detail_ledger_query(self):
        result = select_tools("看一下这个月流水明细", _make_tools())
        assert "get_cost_summary" in result

    def test_debt_bill_query(self):
        result = select_tools("老王那边赊账还欠多少", _make_tools())
        assert "get_cost_summary" in result

    def test_trend_analytics(self):
        result = select_tools("比去年赚得多吗", _make_tools())
        assert "get_cost_analytics" in result

    def test_multi_intent(self):
        result = select_tools("看看天气和成本", _make_tools())
        assert "get_weather_forecast" in result
        assert "get_cost_summary" in result

    def test_keyword_match_logs_tool_select_layer(self, caplog):
        with caplog.at_level("INFO", logger="app.agent.tool_selector"):
            result = select_tools("今天天气", _make_tools())

        assert result == ["get_weather_forecast"]
        assert "tool_select | layer=rule" in caplog.text
        assert "candidates=['get_weather_forecast']" in caplog.text
        assert "returned=['get_weather_forecast']" in caplog.text


class TestFallback:
    def test_greeting_returns_all(self):
        result = select_tools("你好", _make_tools())
        assert result == ALL_TOOL_NAMES

    def test_planting_advice_returns_all(self):
        result = select_tools("西瓜怎么种", _make_tools())
        assert result == ALL_TOOL_NAMES

    def test_how_to_plant_new_crop_returns_all(self):
        result = select_tools("怎么种小麦", _make_tools())
        assert result == ALL_TOOL_NAMES

    def test_planting_attention_returns_all(self):
        result = select_tools("种小麦要注意什么", _make_tools())
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

    def test_llm_intent_logs_returned_tools(self, caplog):
        classifier = MagicMock()
        classifier.classify.return_value = ["get_cost_summary"]

        with caplog.at_level("INFO", logger="app.agent.tool_selector"):
            result = select_tools(
                "帮我看看最近账怎么样",
                _make_tools(),
                intent_classifier=classifier,
            )

        assert result == ["get_cost_summary"]
        assert "tool_select | layer=llm_intent" in caplog.text
        assert "returned=['get_cost_summary']" in caplog.text

    def test_fallback_all_logs_returned_tools(self, caplog):
        with caplog.at_level("INFO", logger="app.agent.tool_selector"):
            result = select_tools("你好", _make_tools())

        assert result == ALL_TOOL_NAMES
        assert "tool_select | layer=fallback_all" in caplog.text
        assert "returned=[" in caplog.text
