"""planting_plan 确定性布局与响应草稿测试。"""

import pytest

from app.agent.task_graph.slot_extractor import extract_planting_plan_slots
from app.agent.task_graph.tasks.planting_plan.response import (
    calculate_planting_layout,
    synthesize_planting_plan_response,
)

pytestmark = pytest.mark.no_db


def test_calculate_planting_layout_divides_total_area_by_unit_area() -> None:
    layout = calculate_planting_layout(total_area_mu=30, unit_area_mu=1.5)

    assert layout["unit_count"] == 20
    assert layout["total_area_mu"] == 30
    assert layout["unit_area_mu"] == 1.5


def test_synthesize_planting_plan_response_contains_sources_and_uncertainties() -> None:
    slots = extract_planting_plan_slots(
        "我在太仓新租了30亩地 每块地1.5亩 帮我规划下茬口，秋季草莓"
    )
    layout = calculate_planting_layout(total_area_mu=30, unit_area_mu=1.5)

    response = synthesize_planting_plan_response(slots=slots, layout=layout)

    assert "草莓" in response
    assert "太仓" in response
    assert "秋季" in response
    assert "30亩" in response
    assert "1.5亩" in response
    assert "20块" in response
    assert "事实来源" in response
    assert "播种窗口" in response
    assert "定植窗口" in response
    assert "管理窗口" in response
    assert "采收窗口" in response
    assert "不确定项" in response
    assert "下一步建议" in response
    assert "已创建" not in response
    assert "已写入" not in response


def test_synthesize_planting_plan_response_handles_missing_unit_area() -> None:
    slots = extract_planting_plan_slots("太仓30亩地 帮我规划下茬口，秋季草莓")
    layout = calculate_planting_layout(total_area_mu=30)

    response = synthesize_planting_plan_response(slots=slots, layout=layout)

    assert "暂不能拆分地块数量" in response
    assert "None块" not in response
