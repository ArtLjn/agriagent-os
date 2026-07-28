"""Context 运行时辅助。

集中维护缓存、预热、失效和 trace payload 构造。旧的
``app.context.runtime.<name>`` 导入路径通过底部兼容模块保留。
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from types import ModuleType
from typing import Any, Generic, Mapping, TypeVar

from app.context.core.models import ContextBlock, ContextBundle
from app.context.pipeline import ContextRenderer

logger = logging.getLogger(__name__)
T = TypeVar("T")


class TTLCache(Generic[T]):
    """简单内存 TTL 缓存。"""

    def __init__(self, ttl_seconds: int) -> None:
        self._store: dict[object, tuple[T, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: object) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() >= expire_at:
            del self._store[key]
            return None
        return value

    def set(self, key: object, value: T) -> None:
        self._store[key] = (value, time.time() + self._ttl)

    def invalidate(self, predicate_key: object) -> int:
        keys = [
            key
            for key in self._store
            if key == predicate_key
            or (isinstance(key, tuple) and key and key[0] == predicate_key)
        ]
        for key in keys:
            del self._store[key]
        return len(keys)

    def clear(self) -> None:
        self._store.clear()


class PromptCache:
    """按 (farm_id, date_str) 缓存渲染后的 system prompt。"""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._cache: TTLCache[str] = TTLCache(ttl_seconds)

    def get(self, farm_id: int, date_str: str) -> str | None:
        value = self._cache.get((farm_id, date_str))
        if value is not None:
            logger.debug("PROMPT CACHE HIT | farm=%s date=%s", farm_id, date_str)
        return value

    def set(self, farm_id: int, date_str: str, value: str) -> None:
        self._cache.set((farm_id, date_str), value)
        logger.debug("PROMPT CACHE SET | farm=%s date=%s", farm_id, date_str)

    def invalidate(self, farm_id: int) -> int:
        return self._cache.invalidate(farm_id)


class FarmContextCache:
    """按 farm_id 缓存运行时农场上下文。"""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._cache: TTLCache[dict] = TTLCache(ttl_seconds)

    def get(self, farm_id: int) -> dict | None:
        value = self._cache.get(farm_id)
        if value is not None:
            logger.debug("FARM CTX CACHE HIT | farm=%s", farm_id)
        return value

    def set(self, farm_id: int, value: dict) -> None:
        self._cache.set(farm_id, value)
        logger.debug("FARM CTX CACHE SET | farm=%s", farm_id)

    def invalidate(self, farm_id: int) -> bool:
        return self._cache.invalidate(farm_id) > 0


_prompt_cache = PromptCache(ttl_seconds=3600)
_farm_ctx_cache = FarmContextCache(ttl_seconds=300)


def get_prompt_cache() -> PromptCache:
    return _prompt_cache


def get_farm_ctx_cache() -> FarmContextCache:
    return _farm_ctx_cache


def clear_all_caches() -> None:
    _prompt_cache._cache.clear()
    _farm_ctx_cache._cache.clear()


def invalidate_farm_context(farm_id: int) -> dict[str, int | bool]:
    """清理指定农场的 prompt 和运行时上下文缓存。"""
    prompt_invalidated = get_prompt_cache().invalidate(farm_id)
    farm_context_invalidated = get_farm_ctx_cache().invalidate(farm_id)
    return {
        "prompt_invalidated": prompt_invalidated,
        "farm_context_invalidated": farm_context_invalidated,
    }


PRELOAD_MAP: dict[str, list[str]] = {
    "weather": ["weather"],
    "manage_cost": ["cost_summary", "cost_analytics"],
    "get_farm_status": ["farm_status"],
    "get_crop_cycle_info": ["crop_cycle"],
    "manage_farm_logs": ["farm_logs"],
}

DEPENDENCY_PRELOAD_MAP: dict[str, str] = {
    "weather": "weather",
    "crop_cycle": "crop_cycle",
    "crop_cycles": "crop_cycle",
    "active_cycles": "crop_cycle",
    "workers": "workers",
    "planting_units": "planting_units",
    "ledger": "cost_summary",
    "recent_operations": "farm_logs",
}


def dependencies_to_preload_types(dependencies: list[str]) -> list[str]:
    """将 Router context_dependencies 转为预热数据类型。"""
    data_types: list[str] = []
    for dependency in dependencies:
        data_type = DEPENDENCY_PRELOAD_MAP.get(dependency)
        if data_type is None or data_type in data_types:
            continue
        data_types.append(data_type)
    return data_types


async def warm_tool_caches(
    selected_names: list[str],
    farm_id: int,
    farm_ctx: dict,
    context_dependencies: list[str] | None = None,
) -> None:
    """并行预热已选 tool 的底层缓存，失败不影响主流程。"""
    tasks = []
    preload_types = dependencies_to_preload_types(context_dependencies or [])
    for name in selected_names:
        for data_type in PRELOAD_MAP.get(name, []):
            if data_type not in preload_types:
                preload_types.append(data_type)

    for data_type in preload_types:
        if data_type == "weather" and farm_ctx.get("farm_location"):
            try:
                from app.domains.weather.service import fetch_weather

                coords = farm_ctx.get("farm_coords", "")
                lat = float(coords.split(",")[0]) if coords else None
                lon = float(coords.split(",")[-1]) if coords else None
                tasks.append(
                    fetch_weather(
                        location=farm_ctx["farm_location"],
                        lat=lat,
                        lon=lon,
                    )
                )
            except ImportError:
                pass

    if not tasks:
        return

    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=2.0,
        )
        logger.info(
            "缓存预热完成 | tools=%s dependencies=%s tasks=%d",
            selected_names,
            context_dependencies or [],
            len(tasks),
        )
    except asyncio.TimeoutError:
        logger.warning("缓存预热超时 2s | tools=%s", selected_names)


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
SENSITIVE_KEY_PARTS = {
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
    r"(?i)\b([a-z0-9_.-]*(?:x-api-key|api[_-]?key|apikey|authorization|token|"
    r"secret|password|passwd|pwd)[a-z0-9_.-]*)"
    r"(\s*[:=]\s*)(bearer\s+)?[^\s,;，；。]+"
)


def build_context_trace_payload(bundle: ContextBundle) -> dict[str, Any]:
    """构造可落 Mongo 的 ContextBundle trace 摘要，不保存完整正文。"""
    selected_blocks = [_block_summary(block) for block in bundle.blocks]
    context_dependency_diagnostics = _sanitize(
        bundle.metadata.get("context_dependency_diagnostics", [])
    )
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
        "context_dependency_diagnostics": context_dependency_diagnostics,
        "dependency_diagnostics": _dependency_diagnostics_payload(
            context_dependency_diagnostics
        ),
        "policy": _policy_summary(bundle.metadata.get("policy")),
        "sections": _section_summary(bundle),
    }
    context_pack = _sanitize(bundle.metadata.get("context_pack"))
    if context_pack:
        payload["context_pack"] = context_pack
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


def _dependency_diagnostics_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, list):
        return {}
    diagnostics: dict[str, Any] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        block_key = _sanitize_text(str(item.get("block_key") or ""))
        if not block_key:
            continue
        status = _context_dependency_status(str(item.get("status") or ""))
        diagnostics[block_key] = {
            "status": status,
            "dependencies": _string_list(item.get("dependencies")),
        }
    return diagnostics


def _context_dependency_status(status: str) -> str:
    return {
        "selected": "available",
        "compressed": "available",
        "dropped": "skipped_by_policy",
        "unavailable": "missing_required_context",
    }.get(status, status or "missing_required_context")


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
    compact = normalized.replace("-", "")
    if normalized in SENSITIVE_KEYS or "apikey" in compact or "xapikey" in compact:
        return True
    parts = [part for part in re.split(r"[^a-z0-9]+", normalized) if part]
    return any(part in SENSITIVE_KEY_PARTS for part in parts)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return sorted(_sanitize_text(str(item)) for item in value)


def _install_legacy_module(module_name: str, exported_names: tuple[str, ...]) -> None:
    module = ModuleType(f"{__name__}.{module_name}")
    module.__doc__ = "兼容入口；实际维护点是 app.context.runtime。"
    for exported_name in exported_names:
        setattr(module, exported_name, globals()[exported_name])
    module.__all__ = list(exported_names)
    sys.modules[module.__name__] = module
    setattr(sys.modules[__name__], module_name, module)


def _install_legacy_runtime_modules() -> None:
    _install_legacy_module(
        "cache",
        (
            "FarmContextCache",
            "PromptCache",
            "TTLCache",
            "clear_all_caches",
            "get_farm_ctx_cache",
            "get_prompt_cache",
        ),
    )
    _install_legacy_module(
        "preload",
        (
            "DEPENDENCY_PRELOAD_MAP",
            "PRELOAD_MAP",
            "dependencies_to_preload_types",
            "warm_tool_caches",
        ),
    )
    _install_legacy_module("invalidation", ("invalidate_farm_context",))
    _install_legacy_module("trace", ("build_context_trace_payload",))


_install_legacy_runtime_modules()

__all__ = [
    "DEPENDENCY_PRELOAD_MAP",
    "FarmContextCache",
    "PRELOAD_MAP",
    "PromptCache",
    "TTLCache",
    "build_context_trace_payload",
    "clear_all_caches",
    "dependencies_to_preload_types",
    "get_farm_ctx_cache",
    "get_prompt_cache",
    "invalidate_farm_context",
    "warm_tool_caches",
]
