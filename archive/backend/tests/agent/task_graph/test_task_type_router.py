"""Task Graph 任务类型路由测试。"""

import pytest

from app.agent.task_graph.router import route_task_type

pytestmark = pytest.mark.no_db


def test_route_task_type_recognizes_planting_plan() -> None:
    decision = route_task_type(
        "我在太仓新租了30亩地 每块地1.5亩 帮我规划下茬口，秋季草莓"
    )

    assert decision.task_type == "planting_plan"
    assert "task_word" in decision.matched_signals
    assert "crop" in decision.matched_signals
    assert "season_or_time" in decision.matched_signals
    assert "area_or_plot" in decision.matched_signals


def test_route_task_type_sends_incomplete_planting_plan_to_slot_questions() -> None:
    decision = route_task_type("帮我规划下茬口")

    assert decision.task_type == "planting_plan"
    assert decision.intent == "plan_crop_cycle"


def test_route_task_type_unknown_goes_to_legacy_fallback() -> None:
    decision = route_task_type("今天帮我随便聊聊农场运营")

    assert decision.task_type == "legacy_skill_fallback"
    assert decision.intent == "unknown"


def test_route_task_type_retry_intent_does_not_route_to_cost() -> None:
    decision = route_task_type("刚才失败了，重试一下")

    assert decision.task_type == "retry_or_resume"
    assert decision.intent == "retry_or_resume"
    assert decision.metadata["retry_or_resume"] is True
