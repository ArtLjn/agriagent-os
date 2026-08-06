"""流式聊天的 trace 查询和回复持久化适配。"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.application.chat import helpers as _chat_helpers
from app.infra.repository_runtime import (
    get_agent_record_repository,
    get_trace_repository,
    resolve_maybe_awaitable,
)
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.conversation.agent_schemas import (
    ChatRequest,
    PendingActionResponse,
    PendingPlanResponse,
)


@dataclass(frozen=True)
class StreamReplyPersistencePayload:
    """后台持久化流式回复所需的轻量字段。"""

    cycle_id: int | None
    session_id: str | None
    user_id: str
    farm_id: int
    user_input: str
    full_reply: str
    skill_names: list[str]
    pending_action: PendingActionResponse | None = None
    pending_plan: PendingPlanResponse | None = None
    pending_decision_handled: bool = False


async def get_skill_names(db: Session, farm_id: int, request_id: str) -> list[str]:
    """从统一 trace repository 查询当前请求调用的 skill 名称。"""
    repo = get_trace_repository(db)
    records = await resolve_maybe_awaitable(
        repo.get_by_request_id(farm_id=farm_id, request_id=request_id)
    )
    return _chat_helpers.skill_names_from_trace_records(records)


async def save_stream_reply(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    full_reply: str,
    skill_names: list[str],
    pending_action: PendingActionResponse | None = None,
):
    return await save_stream_reply_payload(
        db,
        StreamReplyPersistencePayload(
            cycle_id=chat_request.cycle_id,
            session_id=chat_request.session_id,
            user_id=user.id,
            farm_id=farm.id,
            user_input=chat_request.message,
            full_reply=full_reply,
            skill_names=skill_names,
            pending_action=pending_action,
        ),
    )


async def save_stream_reply_payload(
    db: Session,
    payload: StreamReplyPersistencePayload,
):
    return await _chat_helpers.save_stream_reply_by_ids(
        db,
        cycle_id=payload.cycle_id,
        session_id=payload.session_id,
        user_id=payload.user_id,
        farm_id=payload.farm_id,
        full_reply=payload.full_reply,
        skill_names=payload.skill_names,
        pending_action=payload.pending_action,
        repository_factory=get_agent_record_repository,
    )
