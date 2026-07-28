"""Skill 向量集合自动同步测试。"""

from app.infra.quillrag_client import (
    QuillRAGListedDocument,
    QuillRAGListDocumentsResult,
    QuillRAGWriteResult,
)
from app.ops.skill_vector_sync import (
    SkillVectorSyncer,
    build_skill_registry_hash,
    build_skill_route_documents,
)
from app.shared.config import RAGServiceConfig, SkillVectorStoreConfig


class _FakeClient:
    def __init__(self) -> None:
        self.collections: list[str] = []
        self.ingested: list[dict] = []
        self.documents: list[QuillRAGListedDocument] = []
        self.fail_doc_ids: set[str] = set()

    def ensure_collection(self, *, collection: str) -> QuillRAGWriteResult:
        self.collections.append(collection)
        return QuillRAGWriteResult(ok=True, data={"action": "created"})

    def list_documents(
        self,
        *,
        collection: str,
        page: int,
        page_size: int,
    ) -> QuillRAGListDocumentsResult:
        return QuillRAGListDocumentsResult(
            ok=True,
            total=len(self.documents),
            page=page,
            page_size=page_size,
            documents=self.documents,
        )

    def ingest_text(self, **kwargs) -> QuillRAGWriteResult:
        self.ingested.append(kwargs)
        if kwargs["doc_id"] in self.fail_doc_ids:
            return QuillRAGWriteResult(ok=False, error_code="timeout")
        return QuillRAGWriteResult(ok=True, data={"action": "created"})


def test_build_skill_route_documents_contains_operation_metadata() -> None:
    documents = build_skill_route_documents()
    target = next(
        document
        for document in documents
        if document.route_key == "manage_cost.query_summary"
    )

    assert target.doc_id == "skill:manage_cost.query_summary"
    assert "Operation: query_summary" in target.text
    assert target.metadata["route_key"] == "manage_cost.query_summary"
    assert target.metadata["project"] == "farm-manager"
    assert target.metadata["enabled"] is True


def test_skill_vector_syncer_ensures_collection_and_ingests_documents() -> None:
    client = _FakeClient()
    syncer = SkillVectorSyncer(
        config=SkillVectorStoreConfig(
            enabled=True,
            url="http://rag.local",
            collection="farm_manager_skill_routes_v1",
        ),
        rag_config=RAGServiceConfig(),
        client=client,  # type: ignore[arg-type]
    )

    result = syncer.sync()

    assert result.enabled is True
    assert result.collection_action == "created"
    assert result.total == result.synced
    assert result.failed == 0
    assert client.collections == ["farm_manager_skill_routes_v1"]
    assert any(item["doc_id"] == "skill:__manifest__" for item in client.ingested)
    assert any(
        item["doc_id"] == "skill:manage_cost.query_summary"
        and item["category"] == "skill_route"
        and item["metadata"]["route_key"] == "manage_cost.query_summary"
        for item in client.ingested
    )


def test_skill_vector_syncer_is_noop_when_disabled() -> None:
    client = _FakeClient()
    syncer = SkillVectorSyncer(
        config=SkillVectorStoreConfig(enabled=False),
        rag_config=RAGServiceConfig(),
        client=client,  # type: ignore[arg-type]
    )

    result = syncer.sync()

    assert result.enabled is False
    assert result.total == 0
    assert client.collections == []
    assert client.ingested == []


def test_skill_vector_syncer_skips_ingest_when_manifest_matches() -> None:
    documents = build_skill_route_documents()
    registry_hash = build_skill_registry_hash(documents)
    client = _FakeClient()
    client.documents = [
        QuillRAGListedDocument(
            doc_id="skill:__manifest__",
            extra={"metadata": {"registry_hash": registry_hash}},
        )
    ]
    syncer = SkillVectorSyncer(
        config=SkillVectorStoreConfig(
            enabled=True,
            url="http://rag.local",
            collection="farm_manager_skill_routes_v1",
        ),
        rag_config=RAGServiceConfig(),
        client=client,  # type: ignore[arg-type]
    )

    result = syncer.sync()

    assert result.sync_status == "skipped"
    assert result.total == len(documents)
    assert result.skipped == len(documents)
    assert result.synced == 0
    assert result.failed == 0
    assert client.collections == ["farm_manager_skill_routes_v1"]
    assert client.ingested == []


def test_skill_vector_syncer_does_not_update_manifest_when_document_fails() -> None:
    client = _FakeClient()
    client.fail_doc_ids = {"skill:manage_cost.query_summary"}
    syncer = SkillVectorSyncer(
        config=SkillVectorStoreConfig(
            enabled=True,
            url="http://rag.local",
            collection="farm_manager_skill_routes_v1",
        ),
        rag_config=RAGServiceConfig(),
        client=client,  # type: ignore[arg-type]
    )

    result = syncer.sync()

    assert result.sync_status == "partial_failed"
    assert result.failed == 1
    assert not any(item["doc_id"] == "skill:__manifest__" for item in client.ingested)
