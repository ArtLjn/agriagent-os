# backend/tests/agent/test_force_binding_rules.py
"""查询型意图强制绑定规则单测。"""
from app.agent.tool_selection_rules import QUERY_INTENT_FORCE_BINDING


class TestForceBindingRules:
    def test_weather_intent_binds_get_weather_forecast(self):
        assert "get_weather_forecast" in QUERY_INTENT_FORCE_BINDING["天气"]

    def test_crop_cycle_intent_binds_get_crop_cycles(self):
        assert "get_crop_cycles" in QUERY_INTENT_FORCE_BINDING["我的茬口"]

    def test_workers_intent_binds_get_workers(self):
        assert "get_workers" in QUERY_INTENT_FORCE_BINDING["我的工人"]

    def test_labor_payables_intent_binds_get_labor_payables(self):
        assert "get_labor_payables" in QUERY_INTENT_FORCE_BINDING["未付人工"]

    def test_each_intent_maps_to_at_least_one_skill(self):
        for intent, skills in QUERY_INTENT_FORCE_BINDING.items():
            assert len(skills) >= 1, f"intent {intent} has no skill"

    def test_intent_keys_are_distinct_keywords(self):
        """每个意图 key 是用于匹配的关键词。"""
        for intent in QUERY_INTENT_FORCE_BINDING:
            assert isinstance(intent, str)
            assert len(intent) >= 2
