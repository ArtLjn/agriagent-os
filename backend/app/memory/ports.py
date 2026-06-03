"""Memory 模块端口定义。"""

from typing import Protocol

from app.memory.models import MemoryContext, MemoryHit
from app.memory.schemas import MemoryObservationEvent, MemorySearchQuery


class MemoryServicePort(Protocol):
    """Agent 与 Context Builder 依赖的 Memory 服务端口。"""

    async def build_context(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None = None,
    ) -> MemoryContext:
        """构建当前请求可用的记忆上下文。"""
        ...

    async def observe_interaction(
        self,
        event: MemoryObservationEvent,
    ) -> MemoryObservationEvent:
        """记录一次对话完成后的观察事件。"""
        ...

    async def search(self, query: MemorySearchQuery) -> list[MemoryHit]:
        """检索历史记忆。"""
        ...


class MemoryContextProviderPort(Protocol):
    """Context Builder 可选接入端口。"""

    async def build_context(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None = None,
    ) -> MemoryContext:
        """返回 MemoryContext，长期记忆未启用时也必须返回空上下文。"""
        ...
