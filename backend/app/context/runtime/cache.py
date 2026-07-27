"""Context 相关 TTL 缓存。"""

import logging
import time
from typing import Generic, TypeVar

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


__all__ = [
    "FarmContextCache",
    "PromptCache",
    "TTLCache",
    "clear_all_caches",
    "get_farm_ctx_cache",
    "get_prompt_cache",
]
