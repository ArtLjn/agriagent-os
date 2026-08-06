"""Skill Router QuillRAG 向量检索适配测试。"""

import logging

from app.agent.router.models import ToolCandidate
from app.agent.router.skill_vector_store import (
    QuillRAGSkillVectorStore,
    build_skill_vector_search_fn,
)
from app.infra.quillrag_client import QuillRAGDocument, QuillRAGRetrieveResult
from app.shared.config import RAGServiceConfig, SkillVectorStoreConfig


def _candidate(name: str, operation: str) -> ToolCandidate:
    return ToolCandidate(
        name=name,
        domain="finance",
        intents=[],
        risk="read",
        capability=name,
        operation=operation,
    )


class _FakeClient:
    def __init__(self) -> None:
        self.retrieve_payload: dict | None = None

    def retrieve(self, **kwargs) -> QuillRAGRetrieveResult:
        self.retrieve_payload = kwargs
        return QuillRAGRetrieveResult(
            ok=True,
            actual_mode="hybrid",
            results=[
                QuillRAGDocument(
                    content="doc",
                    score=0.91,
                    doc_id="skill:manage_cost.query_summary",
                    metadata={"route_key": "manage_cost.query_summary"},
                ),
                QuillRAGDocument(
                    content="doc",
                    score=0.88,
                    doc_id="skill:other.query",
                    metadata={"route_key": "other.query"},
                ),
            ],
        )


def test_skill_vector_store_maps_only_known_route_scores() -> None:
    client = _FakeClient()
    store = QuillRAGSkillVectorStore(
        config=SkillVectorStoreConfig(
            enabled=True,
            url="http://rag.local",
            collection="farm_manager_skill_routes_v1",
        ),
        rag_config=RAGServiceConfig(),
        client=client,  # type: ignore[arg-type]
    )

    scores = store.search(
        "这个月花了多少",
        [_candidate("manage_cost", "query_summary")],
    )

    assert scores == {"manage_cost.query_summary": 0.91}
    assert client.retrieve_payload == {
        "query": "这个月花了多少",
        "collection": "farm_manager_skill_routes_v1",
        "mode": "hybrid",
        "top_k": 8,
        "filters": {
            "project": "farm-manager",
            "category": "skill_route",
            "enabled": True,
            "status": "active",
        },
        "use_hyde": False,
    }


def test_skill_vector_store_logs_quillrag_host(caplog) -> None:
    client = _FakeClient()
    store = QuillRAGSkillVectorStore(
        config=SkillVectorStoreConfig(
            enabled=True,
            url="https://rag.local",
            collection="farm_manager_skill_routes_v1",
        ),
        rag_config=RAGServiceConfig(),
        client=client,  # type: ignore[arg-type]
    )

    with caplog.at_level(logging.INFO, logger="app.agent.router.skill_vector_store"):
        store.search("这个月花了多少", [_candidate("manage_cost", "query_summary")])

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event=skill_router_quillrag_retrieve_started" in message
        and "rag_service_host=rag.local" in message
        for message in messages
    )
    assert any(
        "event=skill_router_quillrag_retrieve_completed" in message
        and "rag_service_host=rag.local" in message
        and "external_embedding_requested=True" in message
        for message in messages
    )


def test_build_skill_vector_search_fn_uses_rag_service_fallback_url() -> None:
    search = build_skill_vector_search_fn(
        config=SkillVectorStoreConfig(enabled=True, url=""),
        rag_config=RAGServiceConfig(url="http://rag.local", api_key="key"),
    )

    assert search is not None


def test_build_skill_vector_search_fn_returns_none_without_url() -> None:
    search = build_skill_vector_search_fn(
        config=SkillVectorStoreConfig(enabled=True, url=""),
        rag_config=RAGServiceConfig(url=""),
    )

    assert search is None
