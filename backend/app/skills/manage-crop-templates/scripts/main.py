"""作物模板能力 Skill。"""

import json
import logging

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.skills.context import require_farm_context
from app.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.schemas.crop import CropTemplateCreate, GrowthStageCreate
from app.services import crop_service

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一位农业专家。根据给定的作物名称，生成该作物的标准生长阶段列表。\n"
    "必须以 JSON 数组格式回复，每个元素包含：\n"
    '- "name": 阶段名称（如"播种期"、"苗期"）\n'
    '- "duration_days": 该阶段天数（整数）\n'
    '- "order_index": 顺序（从 0 开始）\n'
    '- "key_tasks": 该阶段主要农事（一句话）\n\n'
    "只返回 JSON 数组，不要其他文字。\n"
    '示例：[{"name":"播种期","duration_days":7,"order_index":0,"key_tasks":"催芽播种"}]'
)


class ManageCropTemplatesSkill(Skill):
    """查询、创建、更新或删除作物模板。"""

    def name(self) -> str:
        return "manage_crop_templates"

    def description(self) -> str:
        return (
            "管理作物模板，支持查询已有模板、创建新模板、更新模板和删除模板。"
            "删除模板会级联删除相关茬口、阶段、农事日志和成本记录，属于高风险操作。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "操作：query_templates/create_template/manage_template",
                    "enum": [
                        "query_templates",
                        "create_template",
                        "manage_template",
                    ],
                },
                "action": {
                    "type": "string",
                    "description": "管理模板时的动作：update/delete。兼容历史参数。",
                    "enum": ["update", "delete"],
                },
                "template_id": {"type": "integer", "description": "作物模板 ID"},
                "crop_name": {
                    "type": "string",
                    "description": "创建模板时的作物名称，如西瓜、玉米、番茄。",
                },
                "name": {"type": "string", "description": "作物名称"},
                "variety": {"type": "string", "description": "品种"},
                "limit": {"type": "integer", "description": "查询返回数量，默认 100"},
                "stages": {
                    "type": "string",
                    "description": "阶段 JSON 数组，含 name、duration_days、order_index、key_tasks。",
                },
            },
            "required": ["operation"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["crop_templates", "crop_cycles"],
            "cache_invalidation": [
                "crop_cycle",
                "farm_logs",
                "cost_summary",
                "get_farm_status",
            ],
            "confirmation_schema": {
                "target_fields": ["operation", "action", "template_id", "name"],
                "changed_fields": ["crop_name", "variety", "stages"],
                "editable_fields": [
                    "operation",
                    "action",
                    "template_id",
                    "crop_name",
                    "name",
                    "variety",
                    "stages",
                ],
                "risk_notes": [
                    "删除模板会级联删除相关茬口、阶段、农事日志和成本记录。"
                ],
            },
            "evaluation_tags": ["read", "write", "crop_template"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理作物模板")
        if context_error:
            return context_error
        operation = _resolve_operation(params)
        db = SessionLocal()
        try:
            if operation == "query_templates":
                return _query_templates(db, farm_id, params)
            if operation == "create_template":
                return await self._create_template(db, farm_id, params, context)
            if operation == "manage_template":
                return _manage_template(db, farm_id, params)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=(
                    "管理作物模板失败：operation 必须是 "
                    "query_templates、create_template 或 manage_template。"
                ),
            )
        except Exception as exc:
            logger.error(
                "管理作物模板失败 | operation=%s | error=%s", operation, exc
            )
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"管理作物模板失败：{exc}"
            )
        finally:
            db.close()

    async def _create_template(
        self,
        db,
        farm_id: int,
        params: dict,
        context,
    ) -> SkillResult:
        crop_name = _clean(params.get("crop_name")) or _clean(params.get("name"))
        if not crop_name:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="请提供作物名称。",
            )

        variety = _clean(params.get("variety"))
        if result := _system_template_match_result(db, crop_name, variety):
            return result

        stages = await self._generate_stages(context, crop_name)
        if not stages:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"生成{crop_name}生长阶段失败，请稍后再试。",
            )

        if result := _duplicate_template_result(
            db, farm_id, crop_name, variety, stages
        ):
            return result

        template_create = CropTemplateCreate(
            name=crop_name,
            variety=variety,
            stages=stages,
        )
        created = crop_service.create_crop_template(
            db, template_create, farm_id=farm_id
        )
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=_created_template_reply(crop_name, created.stages),
        )

    async def _generate_stages(
        self, context, crop_name: str
    ) -> list[GrowthStageCreate]:
        client = getattr(context, "llm_client", None)
        model = getattr(context, "llm_model", "") or ""
        if not client or not model:
            return _fallback_stages()

        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"作物：{crop_name}"},
                ],
                max_tokens=500,
                temperature=0.3,
            )
            content = (resp.choices[0].message.content or "").strip()
            content = content.replace("```json", "").replace("```", "").strip()
            raw_stages = json.loads(content)

            stages = []
            for index, stage in enumerate(raw_stages):
                stages.append(
                    GrowthStageCreate(
                        name=str(stage.get("name", f"阶段{index + 1}")),
                        duration_days=int(stage.get("duration_days", 15)),
                        order_index=int(stage.get("order_index", index)),
                        key_tasks=str(stage.get("key_tasks", ""))
                        if stage.get("key_tasks")
                        else None,
                    )
                )
            return stages
        except Exception:
            logger.warning(
                "LLM 生成阶段失败，使用默认模板 | crop=%s", crop_name, exc_info=True
            )
            return _fallback_stages()


def _resolve_operation(params: dict) -> str:
    operation = _clean(params.get("operation"))
    if operation:
        return operation
    action = _clean(params.get("action"))
    if action in {"update", "delete"}:
        return "manage_template"
    if params.get("crop_name") or params.get("name"):
        return "create_template"
    return "query_templates"


def _query_templates(db, farm_id: int, params: dict) -> SkillResult:
    limit = int(params.get("limit") or 100)
    templates = crop_service.get_crop_templates(db, farm_id, limit=limit)
    if not templates:
        return SkillResult(status=ResultStatus.SUCCESS, reply="暂无作物模板。")
    lines = ["作物模板："]
    for template in templates:
        variety = f"（{template.variety}）" if template.variety else ""
        stages = sorted(template.stages, key=lambda stage: stage.order_index)
        stage_text = "、".join(stage.name for stage in stages) or "无阶段"
        lines.append(f"- #{template.id} {template.name}{variety}：{stage_text}")
    return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))


def _system_template_match_result(
    db, crop_name: str, variety: str | None
) -> SkillResult | None:
    system_template = crop_service.find_system_template_match(db, crop_name, variety)
    if not system_template:
        return None
    stage_names = _format_stage_chain(system_template.stages)
    return SkillResult(
        status=ResultStatus.NEED_CLARIFY,
        reply=(
            f"系统库已有 {crop_name} 的成熟模版"
            f"（阶段：{stage_names}），要导入吗？"
        ),
    )


def _duplicate_template_result(
    db,
    farm_id: int,
    crop_name: str,
    variety: str | None,
    stages: list[GrowthStageCreate],
) -> SkillResult | None:
    existing = crop_service.find_exact_duplicate(
        db,
        farm_id=farm_id,
        name=crop_name,
        variety=variety,
        stages=stages,
    )
    if not existing:
        return None
    stage_names = _format_stage_chain(existing.stages)
    return SkillResult(
        status=ResultStatus.SUCCESS,
        reply=(
            f"📋 已有完全相同的模版 #{existing.id}，"
            f"阶段：{stage_names}。可以直接建茬口了。"
        ),
    )


def _created_template_reply(crop_name: str, stages) -> str:
    stage_lines = [
        f"{index + 1}. {stage.name}（{stage.duration_days}天）"
        + (f"— {stage.key_tasks}" if stage.key_tasks else "")
        for index, stage in enumerate(
            sorted(stages, key=lambda item: item.order_index)
        )
    ]
    stages_text = "\n".join(stage_lines)
    return f"✅ {crop_name}模板已创建！\n\n📋 **生长阶段**\n{stages_text}"


def _manage_template(db, farm_id: int, params: dict) -> SkillResult:
    action = _clean(params.get("action")) or "update"
    if action == "update":
        return _update_template(db, farm_id, params)
    if action == "delete":
        return _delete_template(db, farm_id, params)
    return SkillResult(
        status=ResultStatus.FAILED,
        reply="管理作物模板失败：action 必须是 update 或 delete。",
    )


def _fallback_stages() -> list[GrowthStageCreate]:
    return [
        GrowthStageCreate(
            name="播种期", duration_days=10, order_index=0, key_tasks="播种"
        ),
        GrowthStageCreate(
            name="苗期", duration_days=20, order_index=1, key_tasks="育苗管理"
        ),
        GrowthStageCreate(
            name="生长期", duration_days=40, order_index=2, key_tasks="水肥管理"
        ),
        GrowthStageCreate(
            name="采收期", duration_days=20, order_index=3, key_tasks="采收"
        ),
    ]


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
        raw_stages = json.loads(str(value))
    return [GrowthStageCreate(**stage) for stage in raw_stages]


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _format_stage_chain(stages) -> str:
    return "→".join(
        stage.name for stage in sorted(stages, key=lambda stage: stage.order_index)
    )
