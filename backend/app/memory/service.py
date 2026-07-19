"""Memory Service in-memory 骨架。"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import update

from app.shared.llm import get_llm
from app.shared.compatibility import UTC
from app.shared.config import settings
from app.infra.repository_runtime import (
    get_conversation_message_repository,
    resolve_maybe_awaitable,
)
from app.infra.trace_collector import get_collector
from app.memory.consolidation import InMemoryObservationEventSink
from app.memory.models import (
    LongTermMemoryContext,
    MemoryContext,
    MemoryHit,
    MemoryMessage,
)
from app.memory.schemas import MemoryObservationEvent, MemorySearchQuery
from app.memory.short_term import InMemoryShortTermMemory
from app.models.conversation import Conversation
from app.observability import increment_counter

TraceRecorder = Callable[..., None]
logger = logging.getLogger(__name__)


class EmptyLongTermMemoryStore:
    """长期记忆尚未启用时的空实现。"""

    async def build_context(
        self,
        user_id: str,
        farm_id: int,
    ) -> LongTermMemoryContext:
        return LongTermMemoryContext()


class EmptyMemoryRetrievalStore:
    """检索后端未接入时返回空结果。"""

    async def search(self, query: MemorySearchQuery) -> list[MemoryHit]:
        return []


class InMemoryMemoryService:
    """Memory Service 的进程内实现。"""

    def __init__(self, recent_message_limit: int = 12) -> None:
        self.short_term = InMemoryShortTermMemory(
            recent_message_limit=recent_message_limit
        )
        self.long_term = EmptyLongTermMemoryStore()
        self.retrieval = EmptyMemoryRetrievalStore()
        self.observation_sink = InMemoryObservationEventSink()

    @property
    def observation_events(self) -> list[MemoryObservationEvent]:
        """返回已提交的观察事件，供测试和后续调试使用。"""
        return self.observation_sink.events

    async def build_context(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None = None,
    ) -> MemoryContext:
        """构建短时和长期记忆上下文。"""
        recent_messages = await self.short_term.get_recent_messages(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
        )
        session_summary = await self.short_term.get_session_summary(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
        )
        pending_action = await self.short_term.get_pending_action(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
        )
        temporary_task_state = await self.short_term.get_temporary_task_state(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
        )
        long_term = await self.long_term.build_context(
            user_id=user_id,
            farm_id=farm_id,
        )
        return MemoryContext(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
            recent_messages=recent_messages,
            session_summary=session_summary,
            pending_action=pending_action,
            temporary_task_state=temporary_task_state,
            long_term=long_term,
        )

    async def observe_interaction(
        self,
        event: MemoryObservationEvent,
        trace_collector: TraceRecorder | None = None,
    ) -> MemoryObservationEvent:
        """提交对话观察事件，并同步写入短时消息窗口。"""
        stored_event = await self.observation_sink.submit(event)
        await self.short_term.add_message(
            user_id=event.user_id,
            farm_id=event.farm_id,
            session_id=event.session_id,
            message=MemoryMessage(
                role="user",
                content=event.user_input,
                metadata={"event_id": event.event_id},
            ),
        )
        await self.short_term.add_message(
            user_id=event.user_id,
            farm_id=event.farm_id,
            session_id=event.session_id,
            message=MemoryMessage(
                role="assistant",
                content=event.assistant_reply,
                metadata={
                    "event_id": event.event_id,
                    "skills_called": event.skills_called,
                },
            ),
        )
        self._record_observation_trace(
            event=stored_event,
            trace_collector=trace_collector,
        )
        return stored_event

    async def search(self, query: MemorySearchQuery) -> list[MemoryHit]:
        """执行记忆检索。当前未接入检索后端，返回空列表。"""
        return await self.retrieval.search(query)

    async def maybe_summarize(
        self,
        db,
        conversation_id: int,
        farm_id: int,
        session_id: str | None,
        messages: list[Any] | None,
    ) -> None:
        """在达到阈值时生成 running summary，失败时静默降级。"""
        try:
            if not settings.ai.enable_session_summary:
                self._record_summary_skipped_trace(
                    farm_id=farm_id,
                    session_id=session_id,
                    reason="feature_disabled",
                )
                return

            if _is_summary_circuit_open():
                self._record_summary_skipped_trace(
                    farm_id=farm_id,
                    session_id=session_id,
                    reason="circuit_open",
                )
                return

            conversation = db.get(Conversation, conversation_id)
            if conversation is None:
                self._record_summary_skipped_trace(
                    farm_id=farm_id,
                    session_id=session_id,
                    reason="conversation_not_found",
                )
                return

            summary_messages = await _load_summary_messages(
                db=db,
                farm_id=farm_id,
                session_id=conversation.session_id,
                fallback_messages=messages,
            )
            message_count = len(summary_messages)
            if message_count < settings.ai.session_summary_message_threshold:
                self._record_summary_skipped_trace(
                    farm_id=farm_id,
                    session_id=session_id,
                    reason="below_threshold",
                    conversation_id=conversation_id,
                    message_count=message_count,
                )
                return

            original_summary_updated_at = conversation.summary_updated_at
            user_id = conversation.user_id or ""
            current_summary = conversation.summary
            if _is_within_debounce_window(original_summary_updated_at):
                self._record_summary_skipped_trace(
                    farm_id=farm_id,
                    session_id=session_id,
                    reason="within_debounce_window",
                    conversation_id=conversation_id,
                    message_count=message_count,
                )
                return

            _log_summary_event(
                "会话摘要开始生成",
                code="MEMORY_SUMMARY_STARTED",
                farm_id=farm_id,
                session_id=session_id,
                conversation_id=conversation_id,
                message_count=message_count,
                summary_message_count=len(summary_messages),
                threshold=settings.ai.session_summary_message_threshold,
            )
            llm = get_llm(role="generation")
            summary = await generate_summary(
                llm,
                current_summary=current_summary,
                old_messages=summary_messages,
                persona=None,
            )
            if summary is None:
                _log_summary_event(
                    "会话摘要未产生新增内容",
                    code="MEMORY_SUMMARY_EMPTY",
                    farm_id=farm_id,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    message_count=message_count,
                    summary_message_count=len(summary_messages),
                )
                return

            if not _update_summary_if_version_matches(
                db=db,
                conversation_id=conversation_id,
                previous_updated_at=original_summary_updated_at,
                summary=summary,
            ):
                _log_summary_event(
                    "会话摘要写入跳过",
                    code="MEMORY_SUMMARY_VERSION_CONFLICT",
                    farm_id=farm_id,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    message_count=message_count,
                    summary_length=len(summary),
                )
                return

            await self.short_term.set_session_summary(
                user_id=user_id,
                farm_id=farm_id,
                session_id=session_id,
                summary=summary,
            )
            _log_summary_event(
                "会话摘要写入成功",
                code="MEMORY_SUMMARY_UPDATED",
                farm_id=farm_id,
                session_id=session_id,
                conversation_id=conversation_id,
                message_count=message_count,
                summary_length=len(summary),
            )
        except Exception:
            increment_counter("session_summary_failed_total")
            logger.exception(
                "会话摘要触发失败",
                extra={
                    "code": "MEMORY_SUMMARY_FAILED",
                    "farm_id": farm_id,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                },
            )
            try:
                db.rollback()
            except Exception:
                return

    async def observe_chat_completion(
        self,
        *,
        user_id: str,
        farm_id: int,
        session_id: str | None,
        user_input: str,
        assistant_reply: str,
        skills_called: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        trace_collector: TraceRecorder | None = None,
    ) -> MemoryObservationEvent:
        """记录一次聊天完成事件。"""
        return await self.observe_interaction(
            MemoryObservationEvent(
                user_id=user_id,
                farm_id=farm_id,
                session_id=session_id,
                user_input=user_input,
                assistant_reply=assistant_reply,
                skills_called=skills_called or [],
                metadata=metadata or {},
            ),
            trace_collector=trace_collector,
        )

    def _record_observation_trace(
        self,
        *,
        event: MemoryObservationEvent,
        trace_collector: TraceRecorder | None,
    ) -> None:
        recorder = trace_collector
        if recorder is None:
            try:
                from app.infra.trace_collector import get_collector

                recorder = get_collector().record
            except Exception:
                return
        try:
            recorder(
                node_type="memory_observe",
                node_name="interaction_observation",
                input_data={
                    "event_id": event.event_id,
                    "farm_id": event.farm_id,
                    "session_id": event.session_id,
                    "skills_called": event.skills_called,
                },
                output_data={
                    "stored": True,
                    "recent_message_count": 2,
                },
            )
        except Exception:
            return

    def _record_summary_skipped_trace(
        self,
        *,
        farm_id: int,
        session_id: str | None,
        reason: str,
        conversation_id: int | None = None,
        message_count: int | None = None,
    ) -> None:
        increment_counter("session_summary_skipped_total", {"reason": reason})
        _log_summary_event(
            "会话摘要跳过",
            code="MEMORY_SUMMARY_SKIPPED",
            farm_id=farm_id,
            session_id=session_id,
            conversation_id=conversation_id,
            reason=reason,
            message_count=message_count,
            threshold=settings.ai.session_summary_message_threshold,
        )
        try:
            get_collector().record(
                node_type="memory_summary",
                node_name="summary_skipped",
                input_data={
                    "farm_id": farm_id,
                    "session_id": session_id,
                    "message_count": message_count,
                },
                output_data={"reason": reason},
            )
        except Exception:
            return


def _log_summary_event(message: str, **fields: Any) -> None:
    logger.info(message, extra=fields)


def _is_summary_circuit_open() -> bool:
    """LLM Manager 暂无公开查询熔断状态 API，默认保守不短路。"""
    return False


async def generate_summary(*args: Any, **kwargs: Any) -> str | None:
    """懒加载 summarizer，避免 app 启动阶段出现循环导入。"""
    from app.memory.summarizer import generate_summary as _generate_summary

    return await _generate_summary(*args, **kwargs)


def _is_within_debounce_window(summary_updated_at: datetime | None) -> bool:
    if summary_updated_at is None:
        return False
    updated_at = _as_aware_utc(summary_updated_at)
    debounce = timedelta(minutes=settings.ai.session_summary_debounce_minutes)
    return datetime.now(UTC) - updated_at < debounce


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _load_summary_messages(
    *,
    db,
    farm_id: int,
    session_id: str,
    fallback_messages: list[Any] | None,
) -> list[Any]:
    stored_messages = await resolve_maybe_awaitable(
        get_conversation_message_repository(db).list_by_session(
            farm_id=farm_id,
            session_id=session_id,
        )
    )
    return stored_messages or list(fallback_messages or [])


def _update_summary_if_version_matches(
    *,
    db,
    conversation_id: int,
    previous_updated_at: datetime | None,
    summary: str,
) -> bool:
    now = datetime.now(UTC)
    stmt = update(Conversation).where(Conversation.id == conversation_id)
    if previous_updated_at is None:
        stmt = stmt.where(Conversation.summary_updated_at.is_(None))
    else:
        stmt = stmt.where(Conversation.summary_updated_at == previous_updated_at)
    result = db.execute(
        stmt.values(summary=summary, summary_updated_at=now),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


_memory_service = InMemoryMemoryService()


def get_memory_service() -> InMemoryMemoryService:
    """返回默认 Memory Service 实例。"""
    return _memory_service
