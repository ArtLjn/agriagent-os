"""短时记忆 in-memory 存储。"""

from collections import defaultdict, deque
from typing import Deque

from app.memory.models import (
    MemoryMessage,
    PendingActionSnapshot,
    TemporaryTaskState,
)

SessionKey = tuple[str, int, str | None]


class InMemoryShortTermMemory:
    """基于进程内字典的短时会话记忆。"""

    def __init__(self, recent_message_limit: int = 12) -> None:
        self.recent_message_limit = recent_message_limit
        self._messages: dict[SessionKey, Deque[MemoryMessage]] = defaultdict(
            lambda: deque(maxlen=recent_message_limit)
        )
        self._session_summaries: dict[SessionKey, str] = {}
        self._pending_actions: dict[SessionKey, PendingActionSnapshot] = {}
        self._temporary_task_states: dict[SessionKey, TemporaryTaskState] = {}

    async def add_message(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
        message: MemoryMessage,
    ) -> None:
        self._messages[self._key(user_id, farm_id, session_id)].append(message)

    async def get_recent_messages(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
    ) -> list[MemoryMessage]:
        return list(self._messages.get(self._key(user_id, farm_id, session_id), []))

    async def set_session_summary(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
        summary: str | None,
    ) -> None:
        key = self._key(user_id, farm_id, session_id)
        if summary is None:
            self._session_summaries.pop(key, None)
            return
        self._session_summaries[key] = summary

    async def get_session_summary(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
    ) -> str | None:
        return self._session_summaries.get(self._key(user_id, farm_id, session_id))

    async def set_pending_action(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
        pending_action: PendingActionSnapshot | None,
    ) -> None:
        key = self._key(user_id, farm_id, session_id)
        if pending_action is None:
            self._pending_actions.pop(key, None)
            return
        self._pending_actions[key] = pending_action

    async def get_pending_action(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
    ) -> PendingActionSnapshot | None:
        key = self._key(user_id, farm_id, session_id)
        pending_action = self._pending_actions.get(key)
        if pending_action is not None and pending_action.is_expired():
            self._pending_actions.pop(key, None)
            return None
        return pending_action

    async def set_temporary_task_state(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
        task_state: TemporaryTaskState | None,
    ) -> None:
        key = self._key(user_id, farm_id, session_id)
        if task_state is None:
            self._temporary_task_states.pop(key, None)
            return
        self._temporary_task_states[key] = task_state

    async def get_temporary_task_state(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
    ) -> TemporaryTaskState | None:
        return self._temporary_task_states.get(self._key(user_id, farm_id, session_id))

    @staticmethod
    def _key(user_id: str, farm_id: int, session_id: str | None) -> SessionKey:
        return (user_id, farm_id, session_id)
