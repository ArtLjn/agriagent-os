"""作物模板管理 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.schemas.crop import CropTemplateCreate, GrowthStageCreate
from app.services import crop_service


class ManageCropTemplatesSkill(Skill):
    """更新或删除作物模板。"""

    def name(self) -> str:
        return "manage_crop_templates"

    def description(self) -> str:
        return "更新或删除作物模板。删除模板会级联删除相关茬口、阶段、农事日志和成本记录，属于高风险操作。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作：update/delete"},
                "template_id": {"type": "integer", "description": "作物模板 ID"},
                "name": {"type": "string", "description": "作物名称"},
                "variety": {"type": "string", "description": "品种"},
                "stages": {
                    "type": "string",
                    "description": "阶段 JSON 数组，含 name、duration_days、order_index、key_tasks。",
                },
            },
            "required": ["action"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.HIGH,
            "context_dependencies": ["crop_templates", "crop_cycles"],
            "cache_invalidation": [
                "crop_cycle",
                "farm_logs",
                "cost_summary",
                "get_farm_status",
            ],
            "confirmation_schema": {
                "target_fields": ["action", "template_id", "name"],
                "changed_fields": ["variety", "stages"],
                "editable_fields": [
                    "action",
                    "template_id",
                    "name",
                    "variety",
                    "stages",
                ],
                "risk_notes": [
                    "删除模板会级联删除相关茬口、阶段、农事日志和成本记录。"
                ],
            },
            "evaluation_tags": ["write", "crop_template"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理作物模板")
        if context_error:
            return context_error
        action = _clean(params.get("action")) or "update"
        db = SessionLocal()
        try:
            if action == "update":
                return _update_template(db, farm_id, params)
            if action == "delete":
                return _delete_template(db, farm_id, params)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="管理作物模板失败：action 必须是 update 或 delete。",
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"管理作物模板失败：{exc}"
            )
        finally:
            db.close()


def _update_template(db, farm_id: int, params: dict) -> SkillResult:
    template_id = params.get("template_id")
    if not template_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="更新作物模板需要 template_id。"
        )
    existing = crop_service.get_crop_template(db, int(template_id), farm_id)
    if existing is None:
        return SkillResult(
            status=ResultStatus.FAILED, reply=f"作物模板 {template_id} 不存在。"
        )
    stages = _parse_stages(params.get("stages"))
    if stages is None:
        stages = [
            GrowthStageCreate(
                name=stage.name,
                duration_days=stage.duration_days,
                order_index=stage.order_index,
                key_tasks=stage.key_tasks,
            )
            for stage in sorted(existing.stages, key=lambda item: item.order_index)
        ]
    data = CropTemplateCreate(
        name=_clean(params.get("name")) or existing.name,
        variety=_clean(params.get("variety")) or existing.variety,
        stages=stages,
    )
    template = crop_service.update_crop_template(db, int(template_id), data, farm_id)
    return SkillResult(
        status=ResultStatus.SUCCESS,
        reply=f"已更新作物模板：#{template.id} {template.name}。",
    )


def _delete_template(db, farm_id: int, params: dict) -> SkillResult:
    template_id = params.get("template_id")
    if not template_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="删除作物模板需要 template_id。"
        )
    crop_service.delete_crop_template(db, int(template_id), farm_id)
    return SkillResult(
        status=ResultStatus.SUCCESS, reply=f"已删除作物模板 #{template_id}。"
    )


def _parse_stages(value) -> list[GrowthStageCreate] | None:
    if value in (None, ""):
        return None
    if isinstance(value, list):
        raw_stages = value
    else:
        import json

        raw_stages = json.loads(str(value))
    return [GrowthStageCreate(**stage) for stage in raw_stages]


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None
