"""创建作物模板 Skill — 根据作物名自动生成生长阶段并入库。"""

import json
import logging

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

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


class CreateCropTemplateSkill(Skill):
    def name(self) -> str:
        return "create_crop_template"

    def description(self) -> str:
        return (
            "创建作物模板（定义作物及其生长阶段）。当系统没有某作物模板、"
            "用户想种新作物时调用。只需提供作物名称，系统自动生成生长阶段。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "crop_name": {
                    "type": "string",
                    "description": "作物名称，如'西瓜'、'玉米'、'番茄'",
                },
                "variety": {
                    "type": "string",
                    "description": "品种（可选），如'8424'、'圣女果'",
                },
            },
            "required": ["crop_name"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        crop_name = params.get("crop_name", "").strip()
        if not crop_name:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="请提供作物名称。",
            )

        variety = params.get("variety", "").strip() or None
        farm_id = getattr(context, "farm_id", 1) or 1

        db = SessionLocal()
        try:
            existing = crop_service.find_template_by_name(db, crop_name, farm_id)
            if existing:
                stage_names = "→".join(
                    s.name for s in sorted(existing.stages, key=lambda s: s.order_index)
                )
                return SkillResult(
                    status=ResultStatus.SUCCESS,
                    reply=f"📋 {crop_name}模板已存在，阶段：{stage_names}。可以直接建茬口了。",
                )

            stages = await self._generate_stages(context, crop_name)
            if not stages:
                return SkillResult(
                    status=ResultStatus.FAILED,
                    reply=f"生成{crop_name}生长阶段失败，请稍后再试。",
                )

            template_create = CropTemplateCreate(
                name=crop_name,
                variety=variety,
                stages=stages,
            )
            created = crop_service.create_crop_template(
                db, template_create, farm_id=farm_id
            )

            stage_lines = [
                f"{i + 1}. {s.name}（{s.duration_days}天）"
                + (f"— {s.key_tasks}" if s.key_tasks else "")
                for i, s in enumerate(
                    sorted(created.stages, key=lambda s: s.order_index)
                )
            ]
            stages_text = "\n".join(stage_lines)
            reply = f"✅ {crop_name}模板已创建！\n\n📋 **生长阶段**\n{stages_text}"
            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
        except Exception as exc:
            logger.error("创建作物模板失败 | crop=%s | error=%s", crop_name, exc)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"创建模板失败：{exc}",
            )
        finally:
            db.close()

    async def _generate_stages(
        self, context, crop_name: str
    ) -> list[GrowthStageCreate]:
        client = getattr(context, "llm_client", None)
        model = getattr(context, "llm_model", "") or ""
        if not client or not model:
            return self._fallback_stages()

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
            for idx, s in enumerate(raw_stages):
                stages.append(
                    GrowthStageCreate(
                        name=str(s.get("name", f"阶段{idx + 1}")),
                        duration_days=int(s.get("duration_days", 15)),
                        order_index=int(s.get("order_index", idx)),
                        key_tasks=str(s.get("key_tasks", ""))
                        if s.get("key_tasks")
                        else None,
                    )
                )
            return stages
        except Exception:
            logger.warning(
                "LLM 生成阶段失败，使用默认模板 | crop=%s", crop_name, exc_info=True
            )
            return self._fallback_stages()

    @staticmethod
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
