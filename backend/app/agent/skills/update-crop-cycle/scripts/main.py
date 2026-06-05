"""更新茬口 Skill — 修改茬口开始日期并同步重算阶段。"""

from __future__ import annotations

import re
from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import (
    SkillPermissionLevel,
    SkillRiskLevel,
)
from app.context.invalidation import invalidate_farm_context
from app.core.database import SessionLocal
from app.models.cycle import CropCycle
from app.services import cycle_service

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class UpdateCropCycleSkill(Skill):
    """更新种植茬口开始日期的 Skill。"""

    def name(self) -> str:
        return "update_crop_cycle"

    def description(self) -> str:
        return (
            "修改、调整或更正已有茬口的开始日期、播种期或起始日期。"
            "当用户说修改玉米茬口9月1开始、把夏季玉米播种期改到9月1日、"
            "调整某茬口起始日期时调用此工具。需要 start_date，"
            "可用 cycle_id、crop_name 或 cycle_name 定位茬口。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口 ID，可选。传入时按当前农场限定查找。",
                },
                "crop_name": {
                    "type": "string",
                    "description": "作物名称，如玉米、辣椒，用于自动匹配活跃茬口。",
                },
                "cycle_name": {
                    "type": "string",
                    "description": "茬口名称，如夏季玉米，用于自动匹配活跃茬口。",
                },
                "start_date": {
                    "type": "string",
                    "description": "新的开始日期 YYYY-MM-DD，上游应补全年份。",
                },
            },
            "required": ["start_date"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["farm", "active_cycles"],
            "cache_invalidation": ["crop_cycle", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["cycle_id", "cycle_name", "crop_name"],
                "changed_fields": ["start_date"],
                "inferred_fields": ["crop_name", "cycle_name"],
                "editable_fields": [
                    "cycle_id",
                    "cycle_name",
                    "crop_name",
                    "start_date",
                ],
                "risk_notes": ["修改开始日期会同步重算该茬口所有阶段起止日期。"],
            },
            "evaluation_tags": ["write", "crop_cycle", "date_update"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        """执行茬口开始日期更新。"""
        new_start_date, date_error = _parse_required_start_date(
            params.get("start_date")
        )
        if date_error:
            return date_error

        farm_id, context_error = require_farm_context(context, "修改茬口")
        if context_error:
            return context_error

        db = SessionLocal()
        try:
            cycle = _resolve_cycle(db, params=params, farm_id=farm_id)
            if isinstance(cycle, SkillResult):
                return cycle

            old_start_date = cycle.start_date
            cycle.start_date = new_start_date
            cycle_service._recalculate_stages(db, cycle.id)

            db.commit()
            invalidate_farm_context(farm_id)
            db.refresh(cycle)

            reply = (
                f"已将茬口「{cycle.name}」开始日期从 "
                f"{old_start_date.isoformat()} 修改为 {new_start_date.isoformat()}，"
                "阶段日期已同步重算。"
            )
            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
        except Exception as exc:
            db.rollback()
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"修改茬口失败：{exc}",
            )
        finally:
            db.close()


def _parse_required_start_date(value) -> tuple[date | None, SkillResult | None]:
    """校验并解析必填 YYYY-MM-DD 日期。"""
    if not isinstance(value, str) or not value.strip():
        return None, SkillResult(
            status=ResultStatus.FAILED,
            reply="修改茬口失败：请提供 start_date，格式为 YYYY-MM-DD。",
        )

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
