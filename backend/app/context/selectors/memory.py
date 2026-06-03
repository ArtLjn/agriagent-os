"""Memory selector 兼容骨架。"""

from app.context.models import ContextBlock


class MemorySelector:
    """选择短时或长期记忆摘要。"""

    def select(
        self,
        memory_summary: str | None = None,
        memory_hits: list[str] | None = None,
        **_kwargs,
    ) -> list[ContextBlock]:
        parts = []
        if memory_summary:
            parts.append(memory_summary)
        if memory_hits:
            parts.extend(memory_hits[:5])
        if not parts:
            return []
        return [
            ContextBlock(
                key="memory",
                source="memory",
                purpose="记忆摘要",
                content="\n".join(parts),
                priority=45,
                compressible=True,
                min_tokens=32,
            )
        ]


__all__ = ["MemorySelector"]
