"""茬口创建任务的轻量计划构造器。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.context.models import ContextBundle

_CROP_VARIETY_RE = re.compile(
    r"(?<!\d)([A-Za-z]*\d+[A-Za-z0-9-]*)(?!\s*(?:亩|元|块|天|号|年|月|日))"
)
_AREA_MU_RE = re.compile(r"(\d+(?:\.\d+)?)\s*亩")


@dataclass(frozen=True)
class CropCycleSetupPlan:
    """由单个茬口创建意图扩展出的待确认计划。"""

    steps: list[dict[str, Any]]
    area_note: str = ""


def build_crop_cycle_setup_steps(
    *,
    tool_calls: list[dict],
    original_input: str,
    context_bundle: ContextBundle | None = None,
) -> CropCycleSetupPlan | None:
    """把创建茬口 tool call 扩展成模板、茬口、可选种植单元计划。"""
    cycle_params = _cycle_params_from_tool_call(tool_calls)
    if cycle_params is None:
        return None
    crop_name = str(cycle_params.get("crop_name") or "").strip()
    if not crop_name:
        return None

    cycle_params["operation"] = "create_cycle"
    _fill_area(cycle_params, original_input)

    template_params: dict[str, Any] = {
        "operation": "create_template",
        "crop_name": crop_name,
    }
    variety = _crop_variety_for_template(cycle_params, original_input, crop_name)
    if variety:
        template_params["variety"] = variety

    steps = [
        {
            "step_id": "ensure_crop_template",
            "tool_name": "manage_crop_templates",
            "params": template_params,
            "depends_on": [],
        },
        {
            "step_id": "create_crop_cycle",
            "tool_name": "manage_crop_cycle",
            "params": cycle_params,
            "depends_on": ["ensure_crop_template"],
        },
    ]
    unit_params = _planting_unit_params(
        context_bundle=context_bundle,
        fallback_area=cycle_params.get("area"),
    )
    if unit_params:
        steps.append(
            {
                "step_id": "create_planting_unit",
                "tool_name": "manage_planting_units",
                "params": unit_params,
                "depends_on": ["create_crop_cycle"],
            }
        )

    return CropCycleSetupPlan(
        steps=steps,
        area_note=_area_note(cycle_params, has_planting_unit=bool(unit_params)),
    )


def _cycle_params_from_tool_call(tool_calls: list[dict]) -> dict[str, Any] | None:
    if len(tool_calls) != 1:
        return None
    tool_call = tool_calls[0]
    if str(tool_call.get("name") or "") != "manage_crop_cycle":
        return None
    args = tool_call.get("args")
    if not isinstance(args, dict):
        return None
    if str(args.get("operation") or "") != "create_cycle":
        return None
    return dict(args)


def _fill_area(cycle_params: dict[str, Any], original_input: str) -> None:
    if cycle_params.get("area") not in (None, ""):
        return
    match = _AREA_MU_RE.search(original_input)
    if match:
        cycle_params["area"] = _number_text(match.group(1))


def _crop_variety_for_template(
    cycle_params: dict[str, Any],
    original_input: str,
    crop_name: str,
) -> str | None:
    variety = _clean_text(cycle_params.get("variety"))
    if variety:
        return variety
    for text in (cycle_params.get("cycle_name"), original_input):
        variety = _extract_crop_variety(str(text or ""), crop_name)
        if variety:
            return variety
    return None


def _extract_crop_variety(text: str, crop_name: str) -> str | None:
    if not text:
        return None
    normalized = (
        text.replace(crop_name, " ")
        .replace("茬口", " ")
        .replace("种植", " ")
        .replace("周期", " ")
    )
    match = _CROP_VARIETY_RE.search(normalized)
    if not match:
        return None
    return _clean_text(match.group(1))


def _planting_unit_params(
    *,
    context_bundle: ContextBundle | None,
    fallback_area: Any,
) -> dict[str, Any] | None:
    task = _active_crop_setup_task(context_bundle)
    if not task:
        return None
    planting_unit = task.get("planting_unit")
    if not isinstance(planting_unit, dict):
        return None
    name = _clean_text(planting_unit.get("name"))
    if not name:
        return None
    params: dict[str, Any] = {
        "operation": "manage_units",
        "action": "create",
        "cycle_id": {"$from_step": "create_crop_cycle", "path": "id"},
        "name": name,
    }
    area = planting_unit.get("area_mu", fallback_area)
    if area not in (None, ""):
        params["area_mu"] = area
    return params


def _active_crop_setup_task(context_bundle: ContextBundle | None) -> dict[str, Any]:
    if context_bundle is None:
        return {}
    for block in context_bundle.blocks:
        if block.key != "active_task_state":
            continue
        metadata = block.metadata or {}
        if metadata.get("task_type") != "crop_cycle_setup":
            continue
        entities = metadata.get("entities")
        if isinstance(entities, dict):
            return entities
    return {}


def _area_note(cycle_params: dict[str, Any], *, has_planting_unit: bool) -> str:
    area = cycle_params.get("area")
    if area in (None, "") or has_planting_unit:
        return ""
    return "我会先把面积作为茬口总面积记录；如需创建具体地块或大棚，请补充名称。"


def _number_text(value: str) -> int | float | str:
    if "." not in value:
        try:
            return int(value)
        except ValueError:
            return value
    try:
        return float(value)
    except ValueError:
        return value


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text


__all__ = ["CropCycleSetupPlan", "build_crop_cycle_setup_steps"]
