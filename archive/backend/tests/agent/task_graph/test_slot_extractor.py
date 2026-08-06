"""种植规划槽位抽取测试。"""

import pytest

from app.agent.task_graph.slot_extractor import extract_planting_plan_slots

pytestmark = pytest.mark.no_db


def test_extract_planting_plan_slots_from_acceptance_sample() -> None:
    slots = extract_planting_plan_slots(
        "我在太仓新租了30亩地 每块地1.5亩 帮我规划下茬口，秋季草莓"
    )

    assert slots.slots["location"].value == "太仓"
    assert slots.slots["crop"].value == "草莓"
    assert slots.slots["season"].value == "秋季"
    assert slots.slots["total_area_mu"].value == 30
    assert slots.slots["unit_area_mu"].value == 1.5
    assert slots.slots["unit_count"].value == 20
    assert slots.slots["total_area_mu"].source.kind == "user_input"
    assert slots.slots["unit_area_mu"].source.kind == "user_input"
    assert slots.slots["unit_count"].source.kind == "derived"
    assert "total_area_mu/unit_area_mu" in (slots.slots["unit_count"].source.ref or "")


def test_extract_planting_plan_slots_parses_basic_chinese_numbers() -> None:
    slots = extract_planting_plan_slots("太仓三十亩地，秋季种草莓，每块三亩")

    assert slots.slots["total_area_mu"].value == 30
    assert slots.slots["unit_area_mu"].value == 3
    assert slots.slots["unit_count"].value == 10
