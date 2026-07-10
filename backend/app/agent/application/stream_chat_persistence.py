"""流式聊天的 trace 查询和回复持久化适配。"""

from sqlalchemy.orm import Session

from app.agent.application import chat_use_case_helpers as _chat_helpers
from app.core.database import SessionLocal
from app.infra.repository_runtime import get_agent_record_repository
from app.models.farm import Farm
from app.models.user import User
from app.schemas.agent import ChatRequest, PendingActionResponse


def get_skill_names(db: Session, request_id: str) -> list[str]:
    return _chat_helpers.get_skill_names(
        db,
        request_id,
        session_factory=SessionLocal,
    )


async def save_stream_reply(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    full_reply: str,
    skill_names: list[str],
    pending_action: PendingActionResponse | None = None,
):
    return await _chat_helpers.save_stream_reply(
        db,
        chat_request,
        user,
        farm,
        full_reply,
        skill_names,
        pending_action,
        repository_factory=get_agent_record_repository,
    )
