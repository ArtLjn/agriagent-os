"""记忆检索空实现。"""

from app.memory.models import MemoryHit
from app.memory.schemas import MemorySearchQuery


class EmptyMemoryRetrievalStore:
    """检索后端未接入时返回空结果。"""

    async def search(self, query: MemorySearchQuery) -> list[MemoryHit]:
        return []
