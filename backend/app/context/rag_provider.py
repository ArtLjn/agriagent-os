"""外部 RAG 只读知识 Provider。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.context.models import ContextBlock
from app.infra.quillrag_client import QuillRAGClient, QuillRAGRetrieveResult
from app.shared.config import RAGServiceConfig, settings


class RAGRetrieveClient(Protocol):
    """RAG retrieve client 协议，便于单测注入。"""

    def retrieve(self, **kwargs) -> QuillRAGRetrieveResult: ...


@dataclass(frozen=True, slots=True)
class RAGKnowledgeSelection:
    """RAG selector 的 block 与 trace 元数据。"""

    blocks: list[ContextBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RAGKnowledgeProvider:
    """把 QuillRAG 检索结果转换为 ContextBlock。"""

    def __init__(
        self,
        *,
        client: RAGRetrieveClient | None = None,
        config: RAGServiceConfig | None = None,
    ) -> None:
        self.config = config or settings.rag_service
        self.client = client or self._client_from_config(self.config)

    @classmethod
    def from_settings(cls) -> "RAGKnowledgeProvider":
        return cls(config=settings.rag_service)

    def select(self, *, query: str) -> RAGKnowledgeSelection:
        """检索外部知识并返回可注入 Evidence 分区的 block。"""
        if not self.config.enabled:
            return RAGKnowledgeSelection(metadata={"rag_called": False})
        if not self.config.url or not query.strip():
            return RAGKnowledgeSelection(
                metadata={"rag_called": False, "rag_skipped": True}
            )

        result = self.client.retrieve(
            query=query,
            collection=self.config.default_collection,
            mode=self.config.default_mode,
            top_k=self.config.top_k,
            filters={},
            use_hyde=self.config.use_hyde,
        )
        metadata = self._metadata_from_result(result)
        if not result.ok:
            if self.config.fallback_enabled:
                return RAGKnowledgeSelection(metadata=metadata)
            raise RuntimeError(f"QuillRAG retrieve failed: {result.error_code}")
        if not result.results:
            metadata["rag_empty"] = True
            return RAGKnowledgeSelection(metadata=metadata)

        content = self._format_prompt_content(result)
        block = ContextBlock(
            key="rag_knowledge",
            source="external_rag",
            purpose="外部农技知识检索",
            content=content,
            priority=35,
            compressible=True,
            min_tokens=64,
            ttl_seconds=300,
            metadata=metadata,
        )
        return RAGKnowledgeSelection(blocks=[block], metadata=metadata)

    @staticmethod
    def _client_from_config(config: RAGServiceConfig) -> QuillRAGClient:
        return QuillRAGClient(
            base_url=config.url,
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
            retry=config.retry,
        )

    def _metadata_from_result(self, result: QuillRAGRetrieveResult) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "rag_called": True,
            "collection": self.config.default_collection,
            "requested_mode": self.config.default_mode,
            "actual_mode": result.actual_mode or "",
            "warning": result.warning or "",
            "result_count": len(result.results),
            "attempts": result.attempts,
        }
        if not result.ok:
            metadata.update(
                {
                    "rag_unavailable": True,
                    "rag_error_code": result.error_code or "unknown",
                    "rag_error_summary": result.error_message[:160],
                }
            )
        return metadata

    @staticmethod
    def _format_prompt_content(result: QuillRAGRetrieveResult) -> str:
        lines = ["外部知识检索结果："]
        if result.actual_mode:
            lines.append(f"实际检索模式：{result.actual_mode}")
        if result.warning:
            lines.append(f"检索提示：{result.warning}")
        for index, item in enumerate(result.results[:5], start=1):
            source = item.doc_id or "unknown"
            source_ref = f"{source}#{item.chunk_index}"
            snippet = _compact_text(item.content, limit=180)
            lines.append(
                f"{index}. 来源：{source_ref}；分数：{item.score:.3f}；摘要：{snippet}"
            )
        return "\n".join(lines)


def _compact_text(text: str, *, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


__all__ = [
    "RAGKnowledgeProvider",
    "RAGKnowledgeSelection",
    "RAGRetrieveClient",
]
