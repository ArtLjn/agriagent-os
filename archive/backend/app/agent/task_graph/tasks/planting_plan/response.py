"""planting_plan 确定性布局和响应合成。"""

from __future__ import annotations

from decimal import Decimal

from app.agent.task_graph.models import PlanningSlotSet


def calculate_planting_layout(
    *, total_area_mu: int | float, unit_area_mu: int | float | None = None
) -> dict[str, int | float | None]:
    unit_count = None
    if unit_area_mu not in (None, 0):
        unit_count = _format_number(
            Decimal(str(total_area_mu)) / Decimal(str(unit_area_mu))
        )
    return {
        "total_area_mu": total_area_mu,
        "unit_area_mu": unit_area_mu,
        "unit_count": unit_count,
    }


def synthesize_planting_plan_response(
    *, slots: PlanningSlotSet, layout: dict[str, int | float | None]
) -> str:
    values = slots.slots
    crop = values.get("crop").value if "crop" in values else "待确认作物"
    location = values.get("location").value if "location" in values else "待确认地点"
    season = values.get("season").value if "season" in values else "待确认季节"
    total_area = layout.get("total_area_mu")
    unit_area = layout.get("unit_area_mu")
    unit_count = layout.get("unit_count")
    split_summary = _split_summary(total_area, unit_area, unit_count)
    uncertainties = []
    if "location" not in values:
        uncertainties.append("缺少地点，天气窗口暂不能精确判断")
    if unit_area is None:
        uncertainties.append("缺少单块地面积，暂不能拆分地块数量")
    if not uncertainties:
        uncertainties.append("缺少真实作物模板、天气和系统地块数据校验")

    return (
        f"种植对象：{crop}。\n"
        f"地点：{location}。\n"
        f"季节：{season}。\n"
        f"面积：{_mu(total_area)}。\n"
        f"面积拆分结果：{split_summary}。\n"
        f"播种窗口：围绕{season}前段启动育苗或播种准备。\n"
        f"定植窗口：围绕{season}中段按地块批次推进。\n"
        f"管理窗口：围绕{season}中后段重点跟踪水肥、病虫害和人工安排。\n"
        f"采收窗口：围绕{season}后段结合品种成熟期滚动校准。\n"
        "事实来源：面积、地点、作物和季节来自用户输入；地块数量来自 total_area_mu/unit_area_mu 派生计算。\n"
        f"不确定项：{'；'.join(uncertainties)}。\n"
        "下一步建议：确认地块清单、品种和预算后，再生成待确认的创建方案；当前不会直接写入系统。"
    )


def _split_summary(
    total_area: int | float | None,
    unit_area: int | float | None,
    unit_count: int | float | None,
) -> str:
    if unit_area is None or unit_count is None:
        return "缺少单块地面积，暂不能拆分地块数量"
    return f"{_mu(total_area)} / {_mu(unit_area)} = {unit_count}块"


def _mu(value: int | float | None) -> str:
    return "待确认" if value is None else f"{value}亩"


def _format_number(value: Decimal) -> int | float:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return int(normalized)
    return float(normalized)
