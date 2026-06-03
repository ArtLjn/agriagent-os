"""检索结果 selector。"""

from app.context.models import ContextBlock


class RetrievalSelector:
    """选择语义检索结果。"""

    def select(self, results: list[str] | None = None, **_kwargs) -> list[ContextBlock]:
        if not results:
            return []
        return [
            ContextBlock(
                key="retrieval",
                source="retrieval",
                purpose="检索结果",
                content="\n".join(results[:5]),
                priority=25,
                compressible=True,
                min_tokens=24,
            )
        ]


__all__ = ["RetrievalSelector"]
