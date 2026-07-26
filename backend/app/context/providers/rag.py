"""QuillRAG provider 兼容入口。"""

from app.context.rag_provider import RAGKnowledgeProvider, RAGUnavailableError

__all__ = ["RAGKnowledgeProvider", "RAGUnavailableError"]
