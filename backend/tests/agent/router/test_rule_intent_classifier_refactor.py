"""Router classifier 拆分边界回归测试。"""

import pytest

from app.agent.router.classifier import RuleIntentClassifier
from app.agent.router.classifier_frames import build_query_weather_frame
from app.agent.router.classifier_hints import OPERATION_HINTS, USER_SETTINGS_HINTS

pytestmark = pytest.mark.no_db


def _intents(message: str) -> list[str]:
    return [frame.intent for frame in RuleIntentClassifier().classify(message)]


def test_classifier_refactor_modules_expose_stable_hint_and_frame_boundaries() -> None:
    assert "压蔓" in OPERATION_HINTS
    assert "助手回复角色" in USER_SETTINGS_HINTS
    assert build_query_weather_frame().intent == "query_weather"


@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("当前助手回复角色是什么", "query_user_settings"),
        ("老王还欠多少人工钱", "query_labor_payables"),
        ("记录李海压蔓工资100一天", "manage_wage"),
        ("今天买了100元化肥", "create_cost_record"),
        ("还款100元", "settle_debt"),
        ("我的茬口有哪些", "query_crop_cycles"),
        ("帮我建个黑布林茬口30亩", "create_crop_cycle"),
        ("删除这个茬口", "delete_cycle"),
        ("有哪些作物模板", "query_crop_templates"),
        ("有哪些地块", "query_planting_units"),
        ("帮我创建作业单", "create_work_order"),
        ("搜索一下天气新闻", "query_web_search"),
        ("明天苏州什么天气", "query_weather"),
        ("帮我处理一下这个工人的事情", "ambiguous_write"),
        ("李海这个月干了15天", "clarify_farm_labor_work"),
    ],
)
def test_classifier_key_routes_stay_stable(message: str, expected_intent: str) -> None:
    assert expected_intent in _intents(message)
