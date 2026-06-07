"""tool_selector 模块单元测试。"""

from unittest.mock import MagicMock

import pytest

from app.agent.tool_selector import select_tools

pytestmark = pytest.mark.no_db

ALL_TOOL_NAMES = [
    "get_cost_analytics",
    "get_cost_summary",
    "create_cost_record",
    "delete_cost_record",
    "create_crop_cycle",
    "delete_crop_cycle",
    "create_crop_template",
    "get_crop_templates",
    "manage_crop_templates",
    "create_operation_work_order",
    "get_crop_cycle_info",
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
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
    "manage_workers",
    "manage_wages",
    "get_weather_forecast",
    "web_search",
]

ENABLED_TOOL_NAMES = [name for name in ALL_TOOL_NAMES if name != "web_search"]


def _make_tools(names=None):
    names = names or ALL_TOOL_NAMES
    tools = []
    for n in names:
        m = MagicMock(spec=["name"])
        m.name = n
        tools.append(m)
    return tools


def _make_tools_with_enabled(overrides: dict[str, bool]):
    tools = []
    for n in ALL_TOOL_NAMES:
        m = MagicMock(spec=["name", "skill_metadata"])
        m.name = n
        if n in overrides:
            m.skill_metadata = type(
                "SkillMetadataStub", (), {"enabled": overrides[n]}
            )()
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
        assert result == ENABLED_TOOL_NAMES

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

    def test_update_crop_cycle_colloquial_date_change(self):
        result = select_tools("玉米修改下9月开始", _make_tools())
        assert result == ["update_crop_cycle"]

    def test_update_crop_cycle_named_cycle_date_change(self):
        result = select_tools("把玉米茬口改成9月1开始", _make_tools())
        assert result == ["update_crop_cycle"]

    def test_ambiguous_triggers_fallback(self):
        result = select_tools("买化肥", _make_tools())
        assert result == ENABLED_TOOL_NAMES

    def test_create_operation_work_order_with_labor_detail(self):
        result = select_tools(
            "今天东大棚4个工人给西瓜授粉，每人200，先付老王200", _make_tools()
        )
        assert result == ["create_operation_work_order"]

    def test_create_operation_work_order_wins_over_query_word(self):
        result = select_tools("新建今天授粉作业，3个工人，每人200", _make_tools())
        assert result == ["create_operation_work_order"]

    def test_settle_labor_payment_partial_payment(self):
        result = select_tools("给老王补付300人工", _make_tools())
        assert result == ["settle_labor_payment"]

    def test_update_operation_work_order_correction(self):
        result = select_tools("刚才那条授粉记录不是付老王，是付老李200", _make_tools())
        assert result == ["update_operation_work_order"]

    def test_save_wage_uses_manage_wages(self):
        result = select_tools("给老王记一笔采收工资，每天180", _make_tools())
        assert result == ["manage_wages"]

    def test_update_wage_uses_manage_wages(self):
        result = select_tools("把工资记录12的日薪改成200", _make_tools())
        assert result == ["manage_wages"]

    def test_update_worker_default_wage_uses_manage_workers(self):
        result = select_tools("猪八戒工资更新150一天", _make_tools())
        assert result == ["manage_workers"]

    def test_delete_cost_record_uses_delete_cost_record(self):
        result = select_tools("删除账务记录12", _make_tools())
        assert result == ["delete_cost_record"]

    def test_manage_cost_category_uses_category_skill(self):
        result = select_tools("新增成本分类农机", _make_tools())
        assert result == ["manage_cost_categories"]

    def test_manage_crop_template_uses_template_skill(self):
        result = select_tools("把作物模板5名字改成麒麟西瓜", _make_tools())
        assert result == ["manage_crop_templates"]

    def test_delete_crop_cycle_uses_delete_skill(self):
        result = select_tools("删除茬口12", _make_tools())
        assert result == ["delete_crop_cycle"]

    def test_manage_farm_log_uses_log_skill(self):
        result = select_tools("删除农事记录8", _make_tools())
        assert result == ["manage_farm_logs"]

    def test_manage_planting_unit_uses_unit_skill(self):
        result = select_tools("新增东大棚种植单元", _make_tools())
        assert result == ["manage_planting_units"]

    def test_manage_user_settings_uses_settings_skill(self):
        result = select_tools("默认城市改成杭州", _make_tools())
        assert result == ["manage_user_settings"]


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

    def test_labor_payable_query_prefers_labor_skill(self):
        result = select_tools("老王还欠多少人工钱", _make_tools())
        assert result[0] == "get_labor_payables"
        assert "get_cost_summary" not in result

    def test_operation_work_order_query(self):
        result = select_tools("最近玉米授粉作业有哪些", _make_tools())
        assert result == ["get_operation_work_orders"]

    def test_workers_query_defaults_to_worker_skill(self):
        result = select_tools("我的工人", _make_tools())
        assert result == ["get_workers"]

    def test_inactive_workers_query_uses_worker_skill(self):
        result = select_tools("看看离职工人", _make_tools())
        assert result == ["get_workers"]

    def test_cost_category_query_uses_category_skill(self):
        result = select_tools("有哪些成本分类", _make_tools())
        assert result == ["get_cost_categories"]

    def test_crop_template_query_uses_template_skill(self):
        result = select_tools("有哪些作物模板", _make_tools())
        assert result == ["get_crop_templates"]

    def test_planting_unit_query_uses_unit_skill(self):
        result = select_tools("有哪些大棚", _make_tools())
        assert result == ["get_planting_units"]

    def test_user_settings_query_uses_settings_skill(self):
        result = select_tools("我的默认城市是什么", _make_tools())
        assert result == ["get_user_settings"]

    def test_create_worker_uses_manage_workers(self):
        result = select_tools("我招了一个工人李四，日薪150", _make_tools())
        assert result == ["manage_workers"]

    def test_deactivate_worker_uses_manage_workers(self):
        result = select_tools("删除工人李四", _make_tools())
        assert result == ["manage_workers"]


class TestFallback:
    def test_greeting_returns_all(self):
        result = select_tools("你好", _make_tools())
        assert result == ENABLED_TOOL_NAMES

    def test_planting_advice_returns_all(self):
        result = select_tools("西瓜怎么种", _make_tools())
        assert result == ENABLED_TOOL_NAMES

    def test_how_to_plant_new_crop_returns_all(self):
        result = select_tools("怎么种小麦", _make_tools())
        assert result == ENABLED_TOOL_NAMES

    def test_planting_attention_returns_all(self):
        result = select_tools("种小麦要注意什么", _make_tools())
        assert result == ENABLED_TOOL_NAMES

    def test_all_tools_present(self):
        tools = _make_tools()
        result = select_tools("随便聊聊", tools)
        assert set(result) == set(ENABLED_TOOL_NAMES)
        assert len(result) == len(ENABLED_TOOL_NAMES)

    def test_metadata_enabled_false_excludes_tool(self):
        result = select_tools(
            "随便聊聊",
            _make_tools_with_enabled({"get_farm_status": False}),
        )
        assert "get_farm_status" not in result

    def test_metadata_enabled_true_overrides_legacy_disabled_set(self):
        result = select_tools(
            "随便聊聊",
            _make_tools_with_enabled({"web_search": True}),
        )
        assert "web_search" in result

    def test_empty_message_returns_all(self):
        result = select_tools("", _make_tools())
        assert result == ENABLED_TOOL_NAMES

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

        assert result == ENABLED_TOOL_NAMES
        assert "tool_select | layer=fallback_all" in caplog.text
        assert "returned=[" in caplog.text
