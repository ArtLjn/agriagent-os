"""Context trace payload 安全摘要构造。"""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.context.models import ContextBlock, ContextBundle
from app.context.renderer import ContextRenderer


PREVIEW_LIMIT = 120
REDACTED = "[REDACTED]"
SENSITIVE_KEYS = {
    "api-key",
    "apikey",
    "x-api-key",
    "authorization",
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
}
SAFE_RAG_SOURCE_METADATA_KEYS = {
    "source",
    "title",
    "url",
    "doc_id",
    "chunk_index",
    "collection",
}

_MONGO_URI_PASSWORD_RE = re.compile(
    r"(mongodb(?:\+srv)?://[^:/@\s]+:)([^@/\s]+)(@)",
    re.IGNORECASE,
)
_INLINE_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|x-api-key|authorization|token|secret|password)"
    r"(\s*[:=]\s*)(bearer\s+)?[^\s,;，；。]+"
)


def build_context_trace_payload(bundle: ContextBundle) -> dict[str, Any]:
    """构造可落 Mongo 的 ContextBundle trace 摘要，不保存完整正文。"""
    selected_blocks = [_block_summary(block) for block in bundle.blocks]
    payload: dict[str, Any] = {
        "token_budget": bundle.token_budget,
        "token_estimate": bundle.token_estimate,
        "selected_blocks": selected_blocks,
        "blocks": selected_blocks,
        "compressed_blocks": [
            _block_summary(block) for block in bundle.compressed_blocks
        ],
        "dropped_blocks": [_block_summary(block) for block in bundle.dropped_blocks],
        "selector_errors": _selector_errors(bundle.metadata.get("selector_errors")),
        "allowlist_filtered_keys": _string_list(
            bundle.metadata.get("allowlist_filtered_keys")
        ),
        "context_dependency_diagnostics": _sanitize(
            bundle.metadata.get("context_dependency_diagnostics", [])
        ),
        "policy": _policy_summary(bundle.metadata.get("policy")),
        "sections": _section_summary(bundle),
    }
    selector_metadata = _selector_metadata_summary(
        bundle.metadata.get("selector_metadata")
    )
    if selector_metadata:
        payload["selector_metadata"] = selector_metadata
    return payload


def _block_summary(block: ContextBlock) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "key": _sanitize_text(block.key),
        "source": _sanitize_text(block.source),
        "purpose": _sanitize_text(block.purpose),
        "priority": block.priority,
        "token_estimate": block.token_estimate or 0,
        "required": block.required,
        "compressed": block.is_compressed,
        "reason": _sanitize_text(block.reason),
        "layer": _sanitize(block.metadata.get("layer", "")),
        "cache_scope": _sanitize(block.metadata.get("cache_scope", "")),
        "required_reason": _sanitize(block.metadata.get("required_reason", "")),
        "selected_by_skill_dependencies": _sanitize(
            block.metadata.get("selected_by_skill_dependencies", [])
        ),
        "preview": _preview(block.content),
    }
    if block.key == "rag_knowledge" or block.source == "external_rag":
        summary["rag"] = _rag_summary(block.metadata)
    return summary


def _selector_errors(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    errors = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        errors.append(
            {
                "selector": _sanitize_text(str(item.get("selector") or ""))[:80],
                "error": _sanitize_text(str(item.get("error") or ""))[:200],
            }
        )
    return errors


def _selector_metadata_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    summarized: dict[str, Any] = {}
    knowledge = value.get("knowledge")
    if isinstance(knowledge, Mapping):
        summarized["knowledge"] = _rag_summary(knowledge)
    return summarized


def _policy_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    dependency_map = value.get("context_dependency_map")
    dependency_keys = []
    if isinstance(dependency_map, Mapping):
        dependency_keys = sorted(str(key) for key in dependency_map)
    return {
        "intent": _sanitize(value.get("intent", "")),
        "selected_tool_names": _string_list(value.get("selected_tool_names")),
        "enabled_layers": _string_list(value.get("enabled_layers")),
        "context_dependency_keys": dependency_keys,
    }


def _section_summary(bundle: ContextBundle) -> list[dict[str, Any]]:
    summary = ContextRenderer().debug_summary(bundle)
    return _sanitize(summary.get("sections", []))


def _rag_summary(metadata: Mapping[str, Any]) -> dict[str, Any]:
    sources = _rag_sources(metadata.get("sources"))
    top_score = metadata.get("top_score")
    if top_score is None and sources:
        scores = [source["score"] for source in sources if "score" in source]
        top_score = max(scores) if scores else None
    source_count = (
        metadata.get("source_count") or metadata.get("result_count") or len(sources)
    )
    summary: dict[str, Any] = {
        "collection": _sanitize(metadata.get("collection", "")),
        "mode": _sanitize(metadata.get("mode", metadata.get("requested_mode", ""))),
        "actual_mode": _sanitize(metadata.get("actual_mode", "")),
        "warning": _sanitize(metadata.get("warning", "")),
        "source_count": source_count,
        "sources": sources,
    }
    if top_score is not None:
        summary["top_score"] = top_score
    for key in (
        "rag_called",
        "rag_skipped",
        "rag_empty",
        "rag_unavailable",
        "rag_error_code",
        "rag_error_summary",
    ):
        if key in metadata:
            summary[key] = _sanitize(metadata[key])
    return summary


def _rag_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sources = []
    for item in value[:5]:
        if not isinstance(item, Mapping):
            continue
        source: dict[str, Any] = {}
        for key in ("doc_id", "chunk_index", "score"):
            if key in item:
                source[key] = _sanitize(item[key])
        source_metadata = item.get("metadata")
        if isinstance(source_metadata, Mapping):
            safe_metadata = {
                key: _sanitize(source_metadata[key])
                for key in SAFE_RAG_SOURCE_METADATA_KEYS
                if key in source_metadata and not _is_sensitive_key(key)
            }
            if safe_metadata:
                source["metadata"] = safe_metadata
        sources.append(source)
    return sources


def _preview(text: str) -> str:
    compact = " ".join(_sanitize_text(text).split())
    if len(compact) <= PREVIEW_LIMIT:
        return compact
    return compact[: PREVIEW_LIMIT - 1].rstrip() + "..."


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = {}
        for key, nested in value.items():
            key_text = str(key)
            sanitized[key_text] = (
                REDACTED if _is_sensitive_key(key_text) else _sanitize(nested)
            )
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _sanitize_text(text: str) -> str:
    redacted = _MONGO_URI_PASSWORD_RE.sub(r"\1" + REDACTED + r"\3", text)
    return _INLINE_SECRET_RE.sub(r"\1\2" + REDACTED, redacted)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("_", "-")
    return normalized in SENSITIVE_KEYS


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return sorted(_sanitize_text(str(item)) for item in value)


__all__ = ["build_context_trace_payload"]
