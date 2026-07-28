"""Skill Router 专用 QuillRAG 向量检索适配器。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import urlparse

from app.agent.router.models import ToolCandidate
from app.infra.trace_context import get_trace
from app.infra.quillrag_client import QuillRAGClient
from app.shared.config import RAGServiceConfig, SkillVectorStoreConfig, settings
from app.shared.logging import log_event

logger = logging.getLogger(__name__)

SkillVectorSearchFn = Callable[[str, list[ToolCandidate]], dict[str, float]]


class QuillRAGSkillVectorStore:
    """把 Skill Router query 转为 QuillRAG /retrieve 调用。"""

    def __init__(
        self,
        *,
        config: SkillVectorStoreConfig,
        rag_config: RAGServiceConfig,
        client: QuillRAGClient | None = None,
    ) -> None:
        self.config = config
        self.rag_config = rag_config
        self.base_url = _effective_url(config, rag_config)
        self.rag_service_host = _service_host(self.base_url)
        self.client = client or QuillRAGClient(
            base_url=self.base_url,
            api_key=_effective_api_key(config, rag_config),
            timeout_seconds=config.timeout_seconds,
            retry=config.retry,
        )

    def search(
        self,
        query: str,
        candidates: list[ToolCandidate],
    ) -> dict[str, float]:
        started_at = time.perf_counter()
        candidate_keys = {_route_key(candidate) for candidate in candidates}
        top_k = max(self.config.top_k, len(candidates))
        filters = {
            "project": "farm-manager",
            "category": "skill_route",
            "enabled": True,
            "status": "active",
        }
        _log_quillrag_retrieve_started(
            collection=self.config.collection,
            rag_service_host=self.rag_service_host,
            mode=self.config.mode,
            top_k=top_k,
            candidate_count=len(candidates),
        )
        result = self.client.retrieve(
            query=query,
            collection=self.config.collection,
            mode=self.config.mode,
            top_k=top_k,
            filters=filters,
            use_hyde=self.config.use_hyde,
        )
        if not result.ok:
            _log_quillrag_retrieve_completed(
                status="failed",
                started_at=started_at,
                collection=self.config.collection,
                rag_service_host=self.rag_service_host,
                mode=self.config.mode,
                top_k=top_k,
                candidate_count=len(candidates),
                result_count=0,
                scored_count=0,
                actual_mode=result.actual_mode,
                warning=result.warning,
                error_code=result.error_code,
            )
            raise RuntimeError(result.error_code or "SKILL_VECTOR_SEARCH_FAILED")
        scores: dict[str, float] = {}
        for document in result.results:
            route_key = _route_key_from_metadata(document.metadata, document.doc_id)
            if route_key and route_key in candidate_keys:
                scores[route_key] = max(scores.get(route_key, 0.0), document.score)
        _log_quillrag_retrieve_completed(
            status="success" if scores else "empty",
            started_at=started_at,
            collection=self.config.collection,
            rag_service_host=self.rag_service_host,
            mode=self.config.mode,
            top_k=top_k,
            candidate_count=len(candidates),
            result_count=len(result.results),
            scored_count=len(scores),
            actual_mode=result.actual_mode,
            warning=result.warning,
            error_code=None,
        )
        return scores


def build_skill_vector_search_fn(
    *,
    config: SkillVectorStoreConfig | None = None,
    rag_config: RAGServiceConfig | None = None,
    client: QuillRAGClient | None = None,
) -> SkillVectorSearchFn | None:
    """按配置构建 Router 向量检索函数。"""
    vector_config = config or settings.skill_vector_store
    base_rag_config = rag_config or settings.rag_service
    if not vector_config.enabled:
        return None
    if not _effective_url(vector_config, base_rag_config):
        logger.warning("Skill 向量检索未配置 RAG URL，已禁用")
        return None
    store = QuillRAGSkillVectorStore(
        config=vector_config,
        rag_config=base_rag_config,
        client=client,
    )
    return store.search


def _effective_url(
    config: SkillVectorStoreConfig,
    rag_config: RAGServiceConfig,
) -> str:
    return (config.url or rag_config.url).rstrip("/")


def _effective_api_key(
    config: SkillVectorStoreConfig,
    rag_config: RAGServiceConfig,
) -> str:
    return config.api_key or rag_config.api_key


def _service_host(base_url: str) -> str:
    parsed = urlparse(base_url)
    return parsed.netloc or base_url


def _route_key(candidate: ToolCandidate) -> str:
    if candidate.operation:
        return f"{candidate.name}.{candidate.operation}"
    return candidate.name


def _route_key_from_metadata(metadata: dict, doc_id: str | None) -> str | None:
    route_key = metadata.get("route_key") or metadata.get("source")
    if route_key:
        return str(route_key)
    if doc_id and doc_id.startswith("skill:"):
        return doc_id.removeprefix("skill:")
    return None


def _log_quillrag_retrieve_started(
    *,
    collection: str,
    rag_service_host: str,
    mode: str,
    top_k: int,
    candidate_count: int,
) -> None:
    trace = get_trace()
    log_event(
        logger,
        logging.INFO,
        "skill_router_quillrag_retrieve_started",
        request_id=trace.request_id if trace else None,
        session_id=trace.session_id if trace else None,
        status="started",
        data={
            "collection": collection,
            "rag_service_host": rag_service_host,
            "mode": mode,
            "top_k": top_k,
            "candidate_count": candidate_count,
            "quillrag_retrieve_used": True,
            "external_embedding_requested": True,
            "embedding_location": "quillrag_service",
            "local_embedding_used": False,
            "local_query_embedding_calls": 0,
            "local_doc_embedding_calls": 0,
        },
    )


def _log_quillrag_retrieve_completed(
    *,
    status: str,
    started_at: float,
    collection: str,
    rag_service_host: str,
    mode: str,
    top_k: int,
    candidate_count: int,
    result_count: int,
    scored_count: int,
    actual_mode: str | None,
    warning: str | None,
    error_code: str | None,
) -> None:
    trace = get_trace()
    log_event(
        logger,
        logging.INFO if status in {"success", "empty"} else logging.WARNING,
        "skill_router_quillrag_retrieve_completed",
        code=error_code,
        request_id=trace.request_id if trace else None,
        session_id=trace.session_id if trace else None,
        status=status,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        data={
            "collection": collection,
            "rag_service_host": rag_service_host,
            "mode": mode,
            "actual_mode": actual_mode,
            "top_k": top_k,
            "candidate_count": candidate_count,
            "result_count": result_count,
            "scored_count": scored_count,
            "warning": warning,
            "quillrag_retrieve_used": True,
            "external_embedding_requested": True,
            "embedding_location": "quillrag_service",
            "local_embedding_used": False,
            "local_query_embedding_calls": 0,
            "local_doc_embedding_calls": 0,
        },
    )


__all__ = [
    "QuillRAGSkillVectorStore",
    "SkillVectorSearchFn",
    "build_skill_vector_search_fn",
]
