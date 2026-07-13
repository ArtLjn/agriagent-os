"""删除茬口 operation。"""

from skillify.models.schemas import ResultStatus, SkillResult

from app.agent.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.services import cycle_service


async def delete_cycle(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "删除茬口")
    if context_error:
        return context_error
    cycle_id = params.get("cycle_id")
    if not cycle_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="删除茬口需要 cycle_id。"
        )
    db = SessionLocal()
    try:
        cycle_service.delete_crop_cycle(db, int(cycle_id), farm_id)
        return SkillResult(
            status=ResultStatus.SUCCESS, reply=f"已删除茬口 #{cycle_id}。"
        )
    except Exception as exc:
        return SkillResult(status=ResultStatus.FAILED, reply=f"删除茬口失败：{exc}")
    finally:
        db.close()
