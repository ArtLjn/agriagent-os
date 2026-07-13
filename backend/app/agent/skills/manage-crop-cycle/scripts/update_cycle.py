"""更新茬口 operation。"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult

from app.agent.skills.context import require_farm_context
from app.context.invalidation import invalidate_farm_context
from app.core.database import SessionLocal
from app.models.cycle import CropCycle
from app.services import cycle_service

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_STATUSES = {"active", "planned", "finished"}


async def update_cycle(params: dict, context) -> SkillResult:
    """执行茬口更新。"""
    farm_id, context_error = require_farm_context(context, "修改茬口")
    if context_error:
        return context_error

    changes, change_error = _parse_changes(params)
    if change_error:
        return change_error

    db = SessionLocal()
    try:
        cycle = _resolve_cycle(db, params=params, farm_id=farm_id)
        if isinstance(cycle, SkillResult):
            return cycle

        old_values = _snapshot_cycle(cycle)
        _apply_changes(db, cycle, changes)

        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(cycle)

        reply = _format_success_reply(cycle, old_values, changes)
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
    except Exception as exc:
        db.rollback()
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"修改茬口失败：{exc}",
        )
    finally:
        db.close()


def _parse_changes(params: dict) -> tuple[dict, SkillResult | None]:
    changes = {}
    if "start_date" in params and params.get("start_date") not in (None, ""):
        new_start_date, date_error = _parse_start_date(params.get("start_date"))
        if date_error:
            return {}, date_error
        changes["start_date"] = new_start_date
    for source, target in (
        ("season", "season"),
        ("name", "name"),
        ("note", "batch_note"),
        ("batch_note", "batch_note"),
    ):
        if source in params and params.get(source) is not None:
            changes[target] = str(params.get(source)).strip()
    if "status" in params and params.get("status") is not None:
        status = str(params.get("status")).strip()
        if status not in _VALID_STATUSES:
            return {}, SkillResult(
                status=ResultStatus.FAILED,
                reply="修改茬口失败：status 必须是 active、planned 或 finished。",
            )
        changes["status"] = status
    if "area" in params and params.get("area") not in (None, ""):
        area = _to_decimal(params.get("area"))
        if area is None:
            return {}, SkillResult(
                status=ResultStatus.FAILED,
                reply="修改茬口失败：area 必须是有效数字。",
            )
        changes["total_area_mu"] = area
    stage_name = params.get("current_stage") or params.get("stage")
    if stage_name not in (None, ""):
        changes["current_stage"] = str(stage_name).strip()
    if not changes:
        return {}, SkillResult(
            status=ResultStatus.FAILED,
            reply=(
                "修改茬口失败：请提供要修改的字段，如 start_date、season、"
                "name、area、status、current_stage 或 note。"
            ),
        )
    return changes, None


def _parse_start_date(value) -> tuple[date | None, SkillResult | None]:
    """校验并解析 YYYY-MM-DD 日期。"""
    if not isinstance(value, str) or not value.strip():
        return None, _invalid_date_result()

    raw = value.strip()
    if not _ISO_DATE_PATTERN.fullmatch(raw):
        return None, _invalid_date_result()

    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, _invalid_date_result()


def _invalid_date_result() -> SkillResult:
    return SkillResult(
        status=ResultStatus.FAILED,
        reply="修改茬口失败：start_date 必须是有效日期，格式为 YYYY-MM-DD。",
    )


def _resolve_cycle(db, *, params: dict, farm_id: int) -> CropCycle | SkillResult:
    cycle_id = params.get("cycle_id")
    if cycle_id is None:
        cycle_id = params.get("current_cycle_id") or params.get("context_cycle_id")
    if cycle_id is not None:
        cycle = _get_cycle_by_id(db, cycle_id, farm_id)
        if cycle is None:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"未找到当前农场 ID 为 {cycle_id} 的茬口。",
            )
        return cycle

    crop_name = _clean_text(params.get("crop_name"))
    cycle_name = _clean_text(params.get("cycle_name"))
    if not crop_name and not cycle_name:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="请提供要修改的茬口 ID、作物名称或茬口名称。",
        )

    matches = _match_active_cycles(
        db,
        farm_id=farm_id,
        crop_name=crop_name,
        cycle_name=cycle_name,
    )
    if not matches:
        matches = _match_recent_planned_cycles(
            db,
            farm_id=farm_id,
            crop_name=crop_name,
            cycle_name=cycle_name,
        )
    if not matches:
        target = cycle_name or crop_name or "目标茬口"
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply=f"未在当前农场找到匹配「{target}」的活跃茬口，请指定茬口 ID。",
        )
    if len(matches) > 1:
        candidate_lines = "\n".join(
            f"  - {cycle.name}（ID: {cycle.id}）" for cycle in matches
        )
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply=f"找到多个匹配的活跃茬口，请指定要修改哪一个：\n{candidate_lines}",
        )
    return matches[0]


def _get_cycle_by_id(db, cycle_id, farm_id: int) -> CropCycle | None:
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
        .filter(
            CropCycle.farm_id == farm_id, CropCycle.status.in_(("active", "planned"))
        )
        .order_by(CropCycle.status, CropCycle.start_date.desc(), CropCycle.id.desc())
        .all()
    )

    return [
        cycle
        for cycle in active_cycles
        if _cycle_matches(cycle, crop_name=crop_name, cycle_name=cycle_name)
    ]


def _match_recent_planned_cycles(
    db,
    *,
    farm_id: int,
    crop_name: str | None,
    cycle_name: str | None,
) -> list[CropCycle]:
    cutoff = date.today() - timedelta(days=90)
    cycles = (
        db.query(CropCycle)
        .filter(
            CropCycle.farm_id == farm_id,
            CropCycle.status == "planned",
            CropCycle.start_date >= cutoff,
        )
        .order_by(CropCycle.start_date.desc(), CropCycle.id.desc())
        .all()
    )
    return [
        cycle
        for cycle in cycles
        if _cycle_matches(cycle, crop_name=crop_name, cycle_name=cycle_name)
    ]


def _cycle_matches(
    cycle: CropCycle,
    *,
    crop_name: str | None,
    cycle_name: str | None,
) -> bool:
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


def _clean_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _snapshot_cycle(cycle: CropCycle) -> dict:
    current = next((stage for stage in cycle.stages if stage.is_current), None)
    return {
        "name": cycle.name,
        "start_date": cycle.start_date,
        "season": cycle.season,
        "total_area_mu": cycle.total_area_mu,
        "status": cycle.status,
        "batch_note": cycle.batch_note,
        "current_stage": current.name if current else None,
    }


def _apply_changes(db, cycle: CropCycle, changes: dict) -> None:
    if "name" in changes:
        cycle.name = changes["name"]
    if "season" in changes:
        cycle.season = changes["season"]
    if "total_area_mu" in changes:
        cycle.total_area_mu = changes["total_area_mu"]
    if "status" in changes:
        cycle.status = changes["status"]
    if "batch_note" in changes:
        cycle.batch_note = changes["batch_note"]
    if "start_date" in changes:
        cycle.start_date = changes["start_date"]
        cycle_service._recalculate_stages(db, cycle.id)
    if "current_stage" in changes:
        _set_current_stage(cycle, changes["current_stage"])


def _set_current_stage(cycle: CropCycle, stage_name: str) -> None:
    target = None
    normalized = _normalize(stage_name)
    for stage in cycle.stages:
        if _normalize(stage.name) == normalized:
            target = stage
            break
    if target is None:
        raise ValueError(f"未找到阶段「{stage_name}」")
    for stage in cycle.stages:
        stage.is_current = stage.id == target.id


def _format_success_reply(cycle: CropCycle, old_values: dict, changes: dict) -> str:
    labels = {
        "name": "名称",
        "start_date": "开始日期",
        "season": "季节",
        "total_area_mu": "面积",
        "status": "状态",
        "batch_note": "备注",
        "current_stage": "当前阶段",
    }
    new_values = _snapshot_cycle(cycle)
    lines = [f"已更新茬口「{cycle.name}」："]
    for field in changes:
        if field == "current_stage":
            old_value = old_values.get("current_stage")
            new_value = changes[field]
        else:
            old_value = old_values.get(field)
            new_value = new_values.get(field)
        lines.append(f"- {labels.get(field, field)}：{old_value} → {new_value}")
    if "start_date" in changes:
        lines.append("阶段日期已同步重算。")
    return "\n".join(lines)
