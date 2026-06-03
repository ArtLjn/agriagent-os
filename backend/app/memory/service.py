"""Memory Service in-memory 骨架。"""

from collections.abc import Callable
from typing import Any

from app.memory.consolidation import InMemoryObservationEventSink
from app.memory.long_term import EmptyLongTermMemoryStore
from app.memory.models import MemoryContext, MemoryHit, MemoryMessage
from app.memory.retrieval import EmptyMemoryRetrievalStore
from app.memory.schemas import MemoryObservationEvent, MemorySearchQuery
from app.memory.short_term import InMemoryShortTermMemory

TraceRecorder = Callable[..., None]


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


_memory_service = InMemoryMemoryService()


def get_memory_service() -> InMemoryMemoryService:
    """返回默认 Memory Service 实例。"""
    return _memory_service
