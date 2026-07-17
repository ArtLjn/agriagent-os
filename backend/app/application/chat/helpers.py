"""Agent chat use case 的持久化与观测辅助函数。"""

import inspect
import logging

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.context.invalidation import invalidate_farm_context
from app.core.database import SessionLocal
from app.infra.repository_runtime import (
    get_agent_record_repository,
    resolve_maybe_awaitable,
)
from app.infra.trace_collector import get_collector
from app.memory.models import MemoryContext
from app.memory.service import get_memory_service
from app.models.agent_record import AgentRecord
from app.models.conversation import Conversation
from app.models.farm import Farm
from app.models.trace import TraceRecord
from app.models.user import User
from app.modules.farm.service import get_farm_by_user_id
from app.schemas.agent import ChatRequest, PendingActionResponse, PendingPlanResponse

logger = logging.getLogger(__name__)


async def stream_start_turn(recorder, db: Session, **kwargs):
    if hasattr(type(recorder), "async_start_turn"):
        return await recorder.async_start_turn(db, **kwargs)
    value = recorder.start_turn(db, **kwargs)
    if inspect.isawaitable(value):
        return await value
    return value


async def stream_finish_turn(recorder, db: Session, started_turn, **kwargs):
    if hasattr(type(recorder), "async_finish_turn"):
        return await recorder.async_finish_turn(db, started_turn, **kwargs)
    value = recorder.finish_turn(db, started_turn, **kwargs)
    if inspect.isawaitable(value):
        return await value
    return value


async def observe_chat_completion(
    *,
    user_id: str,
    farm_id: int,
    session_id: str | None,
    user_input: str,
    assistant_reply: str,
    skills_called: list[str],
    request_id: str,
) -> None:
    """提交 Memory observation，失败不影响聊天主流程。"""
    if not user_id:
        return
    try:
        await get_memory_service().observe_chat_completion(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
            user_input=user_input,
            assistant_reply=assistant_reply,
            skills_called=skills_called,
            metadata={"request_id": request_id},
        )
    except Exception:
        logger.exception("[%s] Memory observation 提交失败", request_id)


def invalidate_user_farm_context(
    db: Session, user_id: str
) -> dict[str, int | bool] | None:
    """清理当前用户关联农场的上下文缓存。"""
    farm = get_farm_by_user_id(db, user_id)
    if farm is None:
        return None
    return invalidate_farm_context(farm.id)


async def load_memory_context(
    *,
    user_id: str,
    farm_id: int,
    session_id: str | None,
) -> MemoryContext:
    """通过 application 层获取 Runtime 所需的 MemoryContext。"""
    return await get_memory_service().build_context(
        user_id=user_id,
        farm_id=farm_id,
        session_id=session_id,
    )


def record_agent_response(
    *,
    node_name: str,
    user_input: str,
    reply: str,
    reason: str,
) -> None:
    """记录不一定经过工具节点的最终回复。"""
    get_collector().record(
        node_type="agent_response",
        node_name=node_name,
        input_data={"message": user_input},
        output_data={"reply": reply, "reason": reason},
    )


async def flush_trace_queue() -> None:
    """刷新 trace 队列，确保 skill_call 已落盘。"""
    from app.infra.trace_collector import get_trace_dao

    dao = get_trace_dao()
    if dao and dao.queue_size > 0:
        await dao.flush_now()


def get_skill_names(
    db: Session, request_id: str, session_factory=SessionLocal
) -> list[str]:
    """查询当前请求调用的 skill 名称。"""
    skills = _query_skill_names(db, request_id)
    if skills:
        return skills
    fresh_db = session_factory()
    try:
        return _query_skill_names(fresh_db, request_id)
    finally:
        fresh_db.close()


def skill_names_from_trace_records(records) -> list[str]:
    """从 trace records 中按出现顺序提取 skill_call 名称。"""
    skill_names: list[str] = []
    for record in records:
        if getattr(record, "node_type", None) != "skill_call":
            continue
        name = getattr(record, "node_name", None)
        if name and name not in skill_names:
            skill_names.append(name)
    return skill_names


def _query_skill_names(db: Session, request_id: str) -> list[str]:
    """从指定 DB session 查询 skill_call 名称。"""
    if not _trace_table_exists(db):
        return []
    try:
        skills = (
            db.query(TraceRecord.node_name)
            .filter(TraceRecord.request_id == request_id)
            .filter(TraceRecord.node_type == "skill_call")
            .distinct()
            .all()
        )
    except SQLAlchemyError:
        db.rollback()
        return []
    return [s[0] for s in skills if s[0]]


def _trace_table_exists(db: Session) -> bool:
    try:
        bind = db.get_bind()
    except Exception:
        bind = getattr(db, "bind", None)
    if bind is None:
        return True
    try:
        return bool(sa_inspect(bind).has_table("trace_records"))
    except Exception:
        return True


def merge_skill_names(*groups: list[str]) -> list[str]:
    """按出现顺序合并技能名并去重。"""
    merged: list[str] = []
    for group in groups:
        for name in group:
            if name and name not in merged:
                merged.append(name)
    return merged


def skill_names_from_pending_decision(decision) -> list[str]:
    """从 pending plan 确认执行结果中提取已执行工具。"""
    steps = decision.metadata.get("steps") if decision and decision.metadata else None
    if not isinstance(steps, list):
        return []
    return [
        str(step.get("tool_name"))
        for step in steps
        if isinstance(step, dict) and step.get("tool_name")
    ]


def skill_names_from_pending_plan(
    pending_plan: PendingPlanResponse | None,
) -> list[str]:
    """从待确认计划结构中提取工具名。"""
    if pending_plan is None:
        return []
    return [
        str(step.get("skill_name"))
        for step in pending_plan.steps
        if isinstance(step, dict) and step.get("skill_name")
    ]


async def save_stream_reply(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    full_reply: str,
    skill_names: list[str],
    pending_action: PendingActionResponse | None = None,
    repository_factory=get_agent_record_repository,
) -> Conversation | None:
    """保存流式回复和 AgentRecord。"""
    return await save_stream_reply_by_ids(
        db,
        cycle_id=chat_request.cycle_id,
        session_id=chat_request.session_id,
        user_id=user.id,
        farm_id=farm.id,
        full_reply=full_reply,
        skill_names=skill_names,
        pending_action=pending_action,
        repository_factory=repository_factory,
    )


async def save_stream_reply_by_ids(
    db: Session,
    *,
    cycle_id: int | None,
    session_id: str | None,
    user_id: str,
    farm_id: int,
    full_reply: str,
    skill_names: list[str],
    pending_action: PendingActionResponse | None = None,
    repository_factory=get_agent_record_repository,
) -> Conversation | None:
    """按轻量 ID 保存流式回复和 AgentRecord，便于后台独立 DB 使用。"""
    conversation = None
    if session_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.session_id == session_id,
                Conversation.farm_id == farm_id,
            )
            .first()
        )

    record = AgentRecord(
        cycle_id=cycle_id,
        record_type="chat",
        content=full_reply,
        farm_id=farm_id,
        user_id=user_id,
        conversation_id=conversation.id if conversation else None,
    )
    await resolve_maybe_awaitable(repository_factory(db).create(record))
    return conversation
