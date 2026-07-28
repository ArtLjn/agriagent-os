"""同步 Skill Registry operation 到 QuillRAG 向量集合。"""

from __future__ import annotations

import argparse
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

from app.infra.quillrag_client import QuillRAGClient
from app.shared.config import RAGServiceConfig, SkillVectorStoreConfig, settings
from app.skills.registry import CapabilityDefinition, OperationDefinition, load_skill_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillRouteDocument:
    """一条 operation 对应的 RAG 入库文档。"""

    route_key: str
    doc_id: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SkillVectorSyncResult:
    """Skill 向量同步结果。"""

    enabled: bool
    collection: str
    total: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    collection_action: str = ""
    sync_status: str = "noop"
    registry_hash: str = ""
    remote_registry_hash: str = ""
    errors: list[dict[str, str]] = field(default_factory=list)


class SkillVectorSyncer:
    """把本地 Skill Registry 同步到 QuillRAG。"""

    def __init__(
        self,
        *,
        config: SkillVectorStoreConfig,
        rag_config: RAGServiceConfig,
        client: QuillRAGClient | None = None,
    ) -> None:
        self.config = config
        self.rag_config = rag_config
        self.client = client or QuillRAGClient(
            base_url=_effective_url(config, rag_config),
            api_key=_effective_api_key(config, rag_config),
            timeout_seconds=config.sync_timeout_seconds,
            retry=config.retry,
        )

    def sync(self) -> SkillVectorSyncResult:
        if not self.config.enabled:
            return SkillVectorSyncResult(enabled=False, collection=self.config.collection)
        if not _effective_url(self.config, self.rag_config):
            return SkillVectorSyncResult(
                enabled=True,
                collection=self.config.collection,
                failed=1,
                sync_status="failed",
                errors=[{"route_key": "-", "error": "SKILL_VECTOR_RAG_URL_MISSING"}],
            )
        collection_action = self._ensure_collection()
        documents = build_skill_route_documents()
        registry_hash = build_skill_registry_hash(documents)
        remote_registry_hash = self._load_remote_registry_hash()
        if remote_registry_hash == registry_hash:
            return SkillVectorSyncResult(
                enabled=True,
                collection=self.config.collection,
                total=len(documents),
                skipped=len(documents),
                collection_action=collection_action,
                sync_status="skipped",
                registry_hash=registry_hash,
                remote_registry_hash=remote_registry_hash,
            )

        synced = 0
        errors: list[dict[str, str]] = []
        for document in documents:
            result = self.client.ingest_text(
                collection=self.config.collection,
                text=document.text,
                source=document.route_key,
                category="skill_route",
                doc_id=document.doc_id,
                metadata=document.metadata,
            )
            if result.ok:
                synced += 1
                continue
            errors.append(
                {
                    "route_key": document.route_key,
                    "error": result.error_code or "INGEST_FAILED",
                }
            )
        if not errors:
            manifest_error = self._sync_manifest(documents, registry_hash)
            if manifest_error:
                errors.append(manifest_error)
        return SkillVectorSyncResult(
            enabled=True,
            collection=self.config.collection,
            total=len(documents),
            synced=synced,
            failed=len(errors),
            collection_action=collection_action,
            sync_status="synced" if not errors else "partial_failed",
            registry_hash=registry_hash,
            remote_registry_hash=remote_registry_hash,
            errors=errors,
        )

    def _ensure_collection(self) -> str:
        if not self.config.create_collection_on_startup:
            return "skipped"
        result = self.client.ensure_collection(collection=self.config.collection)
        if not result.ok:
            raise RuntimeError(result.error_code or "ENSURE_COLLECTION_FAILED")
        return str(result.data.get("action") or "")

    def _load_remote_registry_hash(self) -> str:
        result = self.client.list_documents(
            collection=self.config.collection,
            page=1,
            page_size=100,
        )
        if not result.ok:
            logger.warning(
                "Skill 向量同步前检查失败，将执行同步 | collection=%s error=%s",
                self.config.collection,
                result.error_code,
            )
            return ""
        for document in result.documents:
            if document.doc_id != _MANIFEST_DOC_ID:
                continue
            metadata = _metadata_from_extra(document.extra)
            return str(metadata.get("registry_hash") or "")
        return ""

    def _sync_manifest(
        self,
        documents: list[SkillRouteDocument],
        registry_hash: str,
    ) -> dict[str, str] | None:
        result = self.client.ingest_text(
            collection=self.config.collection,
            text=_manifest_text(documents, registry_hash),
            source="skill_route_manifest",
            category="skill_route_manifest",
            doc_id=_MANIFEST_DOC_ID,
            metadata={
                "project": "farm-manager",
                "category": "skill_route_manifest",
                "doc_id": _MANIFEST_DOC_ID,
                "registry_hash": registry_hash,
                "route_count": len(documents),
                "routes": [document.route_key for document in documents],
            },
        )
        if result.ok:
            return None
        return {
            "route_key": "__manifest__",
            "error": result.error_code or "MANIFEST_INGEST_FAILED",
        }


def sync_skill_vectors_on_startup() -> SkillVectorSyncResult:
    """应用启动时调用；失败只由调用方决定是否阻断。"""
    config = settings.skill_vector_store
    if not (config.enabled and config.sync_on_startup):
        return SkillVectorSyncResult(enabled=config.enabled, collection=config.collection)
    result = SkillVectorSyncer(config=config, rag_config=settings.rag_service).sync()
    logger.info(
        "Skill 向量同步完成 | collection=%s status=%s total=%s synced=%s "
        "skipped=%s failed=%s action=%s",
        result.collection,
        result.sync_status,
        result.total,
        result.synced,
        result.skipped,
        result.failed,
        result.collection_action,
    )
    return result


def build_skill_route_documents() -> list[SkillRouteDocument]:
    """从 Skill Registry 生成 operation 粒度入库文档。"""
    registry = load_skill_registry()
    documents: list[SkillRouteDocument] = []
    for capability in registry.capabilities.values():
        if capability.status != "active":
            continue
        for operation in capability.operations.values():
            documents.append(_build_document(capability, operation))
    return documents


def build_skill_registry_hash(documents: list[SkillRouteDocument]) -> str:
    """生成稳定的 Registry 内容指纹，用于同步前检查。"""
    lines: list[str] = []
    for document in sorted(documents, key=lambda item: item.route_key):
        lines.append(document.doc_id)
        lines.append(document.route_key)
        lines.append(_sha256(document.text))
        lines.append(str(document.metadata.get("registry_version") or ""))
    return _sha256("\n".join(lines))


def _build_document(
    capability: CapabilityDefinition,
    operation: OperationDefinition,
) -> SkillRouteDocument:
    route_key = f"{capability.name}.{operation.name}"
    text = _document_text(capability, operation)
    metadata = _document_metadata(capability, operation, route_key, text)
    return SkillRouteDocument(
        route_key=route_key,
        doc_id=f"skill:{route_key}",
        text=text,
        metadata=metadata,
    )


def _document_text(
    capability: CapabilityDefinition,
    operation: OperationDefinition,
) -> str:
    lines = [
        f"Skill: {capability.name}",
        f"Capability: {capability.capability}",
        f"Operation: {operation.name}",
        f"Domain: {capability.domain}",
        f"Risk: {operation.risk}",
        f"Capability description: {capability.description}",
        f"Operation description: {operation.description}",
    ]
    lines.extend(_list_section("Tags", capability.tags))
    lines.extend(_list_section("Legacy aliases", operation.legacy_aliases))
    lines.extend(_list_section("Examples", capability.examples))
    lines.extend(_list_section("Anti examples", capability.anti_examples))
    return "\n".join(line for line in lines if line)


def _document_metadata(
    capability: CapabilityDefinition,
    operation: OperationDefinition,
    route_key: str,
    text: str,
) -> dict[str, Any]:
    return {
        "project": "farm-manager",
        "route_key": route_key,
        "capability": capability.name,
        "capability_code": capability.capability,
        "operation": operation.name,
        "legacy_alias": operation.legacy_aliases[0] if operation.legacy_aliases else "",
        "legacy_aliases": list(operation.legacy_aliases),
        "skill_name": capability.name,
        "domain": capability.domain,
        "risk": operation.risk,
        "operation_risk": operation.risk,
        "enabled": True,
        "status": capability.status,
        "tags": list(capability.tags),
        "intents": [operation.name, *list(operation.legacy_aliases)],
        "entities": list(capability.tags),
        "trigger_examples": list(capability.examples),
        "anti_examples": list(capability.anti_examples),
        "doc_hash": _sha256(text),
        "registry_version": capability.version,
    }


def _list_section(title: str, values: tuple[str, ...]) -> list[str]:
    if not values:
        return []
    return [f"{title}:"] + [f"- {value}" for value in values if value]


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _manifest_text(documents: list[SkillRouteDocument], registry_hash: str) -> str:
    routes = "\n".join(f"- {document.route_key}" for document in documents)
    return (
        "Skill route registry manifest\n"
        f"Registry hash: {registry_hash}\n"
        f"Route count: {len(documents)}\n"
        "Routes:\n"
        f"{routes}"
    )


def _metadata_from_extra(extra: dict[str, Any]) -> dict[str, Any]:
    metadata = extra.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return extra


_MANIFEST_DOC_ID = "skill:__manifest__"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 Skill 向量集合")
    parser.add_argument("--collection", default=settings.skill_vector_store.collection)
    args = parser.parse_args()
    config = settings.skill_vector_store.model_copy(
        update={"enabled": True, "collection": args.collection}
    )
    result = SkillVectorSyncer(config=config, rag_config=settings.rag_service).sync()
    print(
        f"collection={result.collection} status={result.sync_status} "
        f"total={result.total} synced={result.synced} skipped={result.skipped} "
        f"failed={result.failed} action={result.collection_action}"
    )


if __name__ == "__main__":
    main()


__all__ = [
    "SkillRouteDocument",
    "SkillVectorSyncResult",
    "SkillVectorSyncer",
    "build_skill_registry_hash",
    "build_skill_route_documents",
    "sync_skill_vectors_on_startup",
]
