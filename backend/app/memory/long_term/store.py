"""长期记忆空存储。"""

from app.memory.models import LongTermMemoryContext


class EmptyLongTermMemoryStore:
    """长期记忆尚未启用时的空实现。"""

    async def build_context(
        self,
        user_id: str,
        farm_id: int,
    ) -> LongTermMemoryContext:
        return LongTermMemoryContext()
