"""Skill 执行上下文安全工具。"""

from skillify.models.schemas import ResultStatus, SkillResult


def require_farm_context(context, action: str) -> tuple[int | None, SkillResult | None]:
    """读取可信 farm_id，缺失时返回失败结果。"""
    farm_id = getattr(context, "farm_id", None)
    if not isinstance(farm_id, int) or farm_id <= 0:
        return None, SkillResult(
            status=ResultStatus.FAILED,
            reply=f"{action}失败：缺少农场上下文，已拒绝执行。",
        )
    return farm_id, None
