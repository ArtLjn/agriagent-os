"""更新茬口阶段 operation。"""

from __future__ import annotations

from skillify.models.schemas import ResultStatus, SkillResult

from app.agent.skills.context import require_farm_context
from app.context.invalidation import invalidate_farm_context
from app.core.database import SessionLocal
from app.models.cycle import CropCycle, CycleStage


async def update_stage(params: dict, context) -> SkillResult:
    """执行当前生长阶段更新。"""
    stage_name = _stage_name_from_params(params)
    if stage_name is None:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="更新阶段失败：请提供目标阶段名称。",
        )

    farm_id, context_error = require_farm_context(context, "更新阶段")
    if context_error:
        return context_error

    db = SessionLocal()
    try:
        cycle = _resolve_cycle(db, params=params, farm_id=farm_id)
        if isinstance(cycle, SkillResult):
            return cycle

        if not cycle.stages:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"茬口「{cycle.name}」还没有阶段数据。",
            )

        target = _find_stage(list(cycle.stages), stage_name)
        if target is None:
            available = "、".join(stage.name for stage in cycle.stages)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=(
                    f"茬口「{cycle.name}」中没有「{stage_name}」阶段。"
                    f"可用阶段：{available}"
                ),
            )

        for stage in cycle.stages:
            if stage.is_current:
                stage.is_current = 0
        target.is_current = 1
        db.commit()
        invalidate_farm_context(farm_id)

        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=f"已将茬口「{cycle.name}」的阶段更新为「{target.name}」。",
        )
    except Exception as exc:
        db.rollback()
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"更新阶段失败：{exc}",
        )
    finally:
        db.close()


def _stage_name_from_params(params: dict) -> str | None:
    for key in ("current_stage", "stage_name", "stage"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_cycle(db, *, params: dict, farm_id: int) -> CropCycle | SkillResult:
    cycle_id = params.get("cycle_id")
    if cycle_id is None:
        cycle_id = params.get("current_cycle_id") or params.get("context_cycle_id")
    if cycle_id is not None:
        cycle = _get_cycle_by_id(db, cycle_id, farm_id)
        if cycle is None:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"未找到 ID 为 {cycle_id} 的茬口。",
            )
        return cycle

    matches = _match_active_cycles(
        db,
        farm_id=farm_id,
        crop_name=_clean_text(params.get("crop_name")),
        cycle_name=_clean_text(params.get("cycle_name")),
    )
    if not matches:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="当前没有活跃的茬口，请先创建茬口。",
        )
    if len(matches) > 1:
        cycle_list = "\n".join(f"  - {cycle.name}（ID: {cycle.id}）" for cycle in matches)
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply=f"当前有多个活跃茬口，请指定要更新哪一个：\n{cycle_list}",
        )
    return matches[0]


def _get_cycle_by_id(db, cycle_id: int, farm_id: int) -> CropCycle | None:
    return (
        db.query(CropCycle)
        .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
        .first()
    )


def _match_active_cycles(
    db,
    *,
    farm_id: int,
    crop_name: str | None,
    cycle_name: str | None,
) -> list[CropCycle]:
    active_cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .all()
    )
    return [
        cycle
        for cycle in active_cycles
        if _cycle_matches(cycle, crop_name=crop_name, cycle_name=cycle_name)
    ]


def _cycle_matches(
    cycle: CropCycle,
    *,
    crop_name: str | None,
    cycle_name: str | None,
) -> bool:
    if crop_name is None and cycle_name is None:
        return True

    cycle_label = _normalize(cycle.name)
    template_label = _normalize(getattr(cycle.crop_template, "name", ""))
    if cycle_name:
        query = _normalize(cycle_name)
        if query in cycle_label or cycle_label in query:
            return True
    if crop_name:
        query = _normalize(crop_name)
        return (
            query in cycle_label
            or query in template_label
            or (template_label and template_label in query)
        )
    return False


def _find_stage(stages: list[CycleStage], name: str) -> CycleStage | None:
    for stage in stages:
        if stage.name == name:
            return stage
    for stage in stages:
        if name in stage.name or stage.name in name:
            return stage
    return None


def _clean_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()
