"""Agent runtime shared support primitives."""

from app.core.database import SessionLocal
from app.services.quota_service import QuotaCheckResult, check_user_quota


class AgentRuntimeError(RuntimeError):
    """Agent Runtime 基础错误。"""


class AgentLoopMaxStepsExceeded(AgentRuntimeError):
    """Agent loop 超过最大步数。"""


QUOTA_REJECT_MESSAGES = {
    "month": "本月用量已达上限，配额将在下月重置。",
    "week": "本周用量已达上限，配额将在下周一重置。",
    "identity": "缺少可信用户上下文，无法继续处理。",
}


def check_quota(user_id: str | None) -> QuotaCheckResult:
    db = SessionLocal()
    try:
        return check_user_quota(user_id, db)
    finally:
        db.close()


__all__ = [
    "AgentLoopMaxStepsExceeded",
    "AgentRuntimeError",
    "QUOTA_REJECT_MESSAGES",
    "check_quota",
]
