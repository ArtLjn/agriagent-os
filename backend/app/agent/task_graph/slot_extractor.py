"""Task Graph 槽位抽取。"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.agent.task_graph.models import FactSource, PlanningSlot, PlanningSlotSet

_CROPS = (
    "番茄",
    "黄瓜",
    "西瓜",
    "水稻",
    "玉米",
    "辣椒",
    "茄子",
    "草莓",
    "小麦",
    "大豆",
)
_SEASONS = ("春季", "夏季", "秋季", "冬季", "春天", "夏天", "秋天", "冬天")
_KNOWN_LOCATIONS = ("太仓", "苏州", "徐州", "睢宁", "上海")
_AREA_RE = re.compile(r"([零一二两三四五六七八九十百\d]+(?:\.\d+)?)\s*亩")


def extract_planting_plan_slots(user_input: str) -> PlanningSlotSet:
    slots: dict[str, PlanningSlot] = {}
    _put(slots, "location", _extract_location(user_input), "user_input")
    _put(slots, "crop", _extract_first(user_input, _CROPS), "user_input")
    _put(
        slots,
        "season",
        _normalize_season(_extract_first(user_input, _SEASONS)),
        "user_input",
    )

    total_area, unit_area = _extract_area_slots(user_input)
    _put(slots, "total_area_mu", total_area, "user_input", normalized_unit="mu")
    _put(slots, "unit_area_mu", unit_area, "user_input", normalized_unit="mu")
    if total_area is not None and unit_area not in (None, 0):
        unit_count = _format_number(Decimal(str(total_area)) / Decimal(str(unit_area)))
        slots["unit_count"] = PlanningSlot(
            name="unit_count",
            value=unit_count,
            source=FactSource(
                kind="derived",
                ref="formula: total_area_mu/unit_area_mu",
            ),
        )

    missing = [
        name
        for name in ("crop", "season", "total_area_mu")
        if name not in slots or slots[name].value in (None, "")
    ]
    return PlanningSlotSet(
        task_type="planting_plan",
        slots=slots,
        missing_required_slots=missing,
    )


def _put(
    slots: dict[str, PlanningSlot],
    name: str,
    value: Any,
    source_kind: str,
    *,
    normalized_unit: str | None = None,
) -> None:
    if value in (None, ""):
        return
    slots[name] = PlanningSlot(
        name=name,
        value=value,
        source=FactSource(kind=source_kind),
        normalized_unit=normalized_unit,
    )


def _extract_location(text: str) -> str:
    for location in _KNOWN_LOCATIONS:
        if location in text:
            return location
    match = re.search(r"在([\u4e00-\u9fff]{2,6})(?:新租|租了|有|种|规划)", text)
    return match.group(1) if match else ""


def _extract_first(text: str, candidates: tuple[str, ...]) -> str:
    return next((candidate for candidate in candidates if candidate in text), "")


def _normalize_season(season: str) -> str:
    return {
        "春天": "春季",
        "夏天": "夏季",
        "秋天": "秋季",
        "冬天": "冬季",
    }.get(season, season)


def _extract_area_slots(text: str) -> tuple[int | float | None, int | float | None]:
    total_area: int | float | None = None
    unit_area: int | float | None = None
    for match in _AREA_RE.finditer(text):
        value = _parse_number(match.group(1))
        if value is None:
            continue
        prefix = text[max(0, match.start() - 6) : match.start()]
        if any(marker in prefix for marker in ("每块", "每个", "每片", "一块")):
            unit_area = value
        elif total_area is None:
            total_area = value
    return total_area, unit_area


def _parse_number(raw: str) -> int | float | None:
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return _format_number(Decimal(raw))
    chinese = _parse_chinese_integer(raw)
    return chinese


def _parse_chinese_integer(raw: str) -> int | None:
    digits = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if raw in digits:
        return digits[raw]
    if raw == "十":
        return 10
    if "百" in raw:
        left, _, right = raw.partition("百")
        hundred = digits.get(left, 1 if left == "" else 0)
        tail = _parse_chinese_integer(right) if right else 0
        return hundred * 100 + (tail or 0)
    if "十" in raw:
        left, _, right = raw.partition("十")
        ten = digits.get(left, 1 if left == "" else 0)
        tail = digits.get(right, 0) if right else 0
        return ten * 10 + tail
    return None


def _format_number(value: Decimal) -> int | float:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return int(normalized)
    return float(normalized)
