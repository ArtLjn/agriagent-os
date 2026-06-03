"""Agent Context 记忆上下文适配。"""

from app.memory.models import MemoryContext
from app.memory.service import get_memory_service


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


__all__ = ["load_memory_context"]
