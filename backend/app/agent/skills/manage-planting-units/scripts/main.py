"""种植单元管理 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.schemas.planting import PlantingUnitCreate, PlantingUnitUpdate
from app.services import planting_service


class ManagePlantingUnitsSkill(Skill):
    """创建、更新或删除种植单元。"""

    def name(self) -> str:
        return "manage_planting_units"

    def description(self) -> str:
        return "创建、更新或删除棚、地块等种植单元。删除会移除该单元及其作业范围关联。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作：create/update/delete",
                },
                "unit_id": {"type": "integer", "description": "种植单元 ID"},
                "cycle_id": {"type": "integer", "description": "所属茬口 ID"},
                "name": {"type": "string", "description": "种植单元名称"},
                "area_mu": {"type": "number", "description": "面积，单位亩"},
                "planted_date": {
                    "type": "string",
                    "description": "定植日期，YYYY-MM-DD",
                },
                "status": {"type": "string", "description": "状态，如 active/inactive"},
                "note": {"type": "string", "description": "备注"},
            },
            "required": ["action"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["crop_cycles", "planting_units"],
            "cache_invalidation": ["get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["action", "unit_id", "cycle_id", "name"],
                "changed_fields": ["area_mu", "planted_date", "status", "note"],
                "editable_fields": [
                    "action",
                    "unit_id",
                    "cycle_id",
                    "name",
                    "area_mu",
                    "planted_date",
                    "status",
                    "note",
                ],
                "risk_notes": ["删除种植单元会移除其作业范围关联。"],
            },
            "evaluation_tags": ["write", "planting_unit"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理种植单元")
        if context_error:
            return context_error
        action = _clean(params.get("action")) or "create"
        db = SessionLocal()
        try:
            if action == "create":
                return _create_unit(db, farm_id, params)
            if action == "update":
                return _update_unit(db, farm_id, params)
            if action == "delete":
                return _delete_unit(db, farm_id, params)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="管理种植单元失败：action 必须是 create、update 或 delete。",
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"管理种植单元失败：{exc}"
            )
        finally:
            db.close()


def _create_unit(db, farm_id: int, params: dict) -> SkillResult:
    cycle_id = params.get("cycle_id")
    name = _clean(params.get("name"))
    if not cycle_id or not name:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="创建种植单元需要 cycle_id 和名称。"
        )
    unit = planting_service.create_unit(
        db,
        PlantingUnitCreate(
            cycle_id=int(cycle_id),
            name=name,
            area_mu=_to_decimal(params.get("area_mu")),
            planted_date=_to_date(params.get("planted_date")),
            status=_clean(params.get("status")) or "active",
            note=_clean(params.get("note")),
        ),
        farm_id,
    )
    return SkillResult(
        status=ResultStatus.SUCCESS, reply=f"已创建种植单元：#{unit.id} {unit.name}。"
    )


def _update_unit(db, farm_id: int, params: dict) -> SkillResult:
    unit_id = params.get("unit_id")
    if not unit_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="更新种植单元需要 unit_id。"
        )
    values = {}
    for key in ("name", "status", "note"):
        if key in params and params.get(key) is not None:
            values[key] = _clean(params.get(key))
    if "area_mu" in params and params.get("area_mu") is not None:
        values["area_mu"] = _to_decimal(params.get("area_mu"))
    if "planted_date" in params and params.get("planted_date") is not None:
        values["planted_date"] = _to_date(params.get("planted_date"))
    unit = planting_service.update_unit(
        db,
        int(unit_id),
        PlantingUnitUpdate(**values),
        farm_id,
    )
    return SkillResult(
        status=ResultStatus.SUCCESS, reply=f"已更新种植单元：#{unit.id} {unit.name}。"
    )


def _delete_unit(db, farm_id: int, params: dict) -> SkillResult:
    unit_id = params.get("unit_id")
    if not unit_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="删除种植单元需要 unit_id。"
        )
    planting_service.delete_unit(db, int(unit_id), farm_id)
    return SkillResult(
        status=ResultStatus.SUCCESS, reply=f"已删除种植单元 #{unit_id}。"
    )


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
