"""外部知识 selector。"""

from app.context.models import ContextBlock
from app.context.rag_provider import RAGKnowledgeProvider


class KnowledgeSelector:
    """选择外部 QuillRAG 只读知识。"""

    def __init__(self, provider: RAGKnowledgeProvider | None = None) -> None:
        self.provider = provider or RAGKnowledgeProvider.from_settings()
        self.last_metadata: dict = {}

    def select(self, query: str | None = None, **_kwargs) -> list[ContextBlock]:
        if not query:
            self.last_metadata = {"rag_called": False, "rag_skipped": True}
            return []
        selection = self.provider.select(query=query)
        self.last_metadata = dict(selection.metadata)
        return selection.blocks


__all__ = ["KnowledgeSelector"]
