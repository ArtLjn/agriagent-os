"""农场状态查询 Skill — 封装 farm_context_service 供 Agent 按需调用。"""

import logging

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.services import farm_context_service

logger = logging.getLogger(__name__)


class FarmStatusSkill(Skill):
    def name(self) -> str:
        return "get_farm_status"

    def description(self) -> str:
        return (
            "获取当前农场综合状态（茬口、近期农事、花费、天气）。"
            "当用户问到种植情况、农事进展、花费账目、需要整体建议时，"
            "调用此工具获取真实农场数据。"
        )

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    @cached(ttl_seconds=300, key_fn=lambda p: "farm_status")
    async def execute(self, params: dict, context) -> SkillResult:
        farm_id = getattr(context, "farm_id", 1) or 1
        db = SessionLocal()
        try:
            summary = farm_context_service.build_summary(db, farm_id=farm_id)
            return SkillResult(status=ResultStatus.SUCCESS, reply=summary)
        except Exception as e:
            logger.error("get_farm_status 失败 | farm_id=%d | error=%s", farm_id, e)
            return SkillResult(
                status=ResultStatus.FAILED, reply="获取农场状态失败，请稍后再试。"
            )
        finally:
            db.close()
