"""System prompt + farm context TTL 缓存，基于内存字典。"""

import logging
import time

logger = logging.getLogger(__name__)


class PromptCache:
    """按 (farm_id, date_str) 缓存渲染后的 system prompt。"""

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[tuple[int, str], tuple[str, float]] = {}
        self._ttl = ttl_seconds

    def get(self, farm_id: int, date_str: str) -> str | None:
        key = (farm_id, date_str)
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() >= expire_at:
            del self._store[key]
            return None
        logger.debug("PROMPT CACHE HIT | farm=%s date=%s", farm_id, date_str)
        return value

    def set(self, farm_id: int, date_str: str, value: str) -> None:
        key = (farm_id, date_str)
        self._store[key] = (value, time.time() + self._ttl)
        logger.debug(
            "PROMPT CACHE SET | farm=%s date=%s ttl=%ds",
            farm_id, date_str, self._ttl,
        )

    def invalidate(self, farm_id: int) -> int:
        keys = [k for k in self._store if k[0] == farm_id]
        for k in keys:
            del self._store[k]
        return len(keys)


class FarmContextCache:
    """按 farm_id 缓存农场上下文。"""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[int, tuple[dict, float]] = {}
        self._ttl = ttl_seconds

    def get(self, farm_id: int) -> dict | None:
        entry = self._store.get(farm_id)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() >= expire_at:
            del self._store[farm_id]
            return None
        logger.debug("FARM CTX CACHE HIT | farm=%s", farm_id)
        return value

    def set(self, farm_id: int, value: dict) -> None:
        self._store[farm_id] = (value, time.time() + self._ttl)
        logger.debug("FARM CTX CACHE SET | farm=%s ttl=%ds", farm_id, self._ttl)

    def invalidate(self, farm_id: int) -> bool:
        if farm_id in self._store:
            del self._store[farm_id]
            return True
        return False


_prompt_cache = PromptCache(ttl_seconds=3600)
_farm_ctx_cache = FarmContextCache(ttl_seconds=300)


def get_prompt_cache() -> PromptCache:
    return _prompt_cache


def get_farm_ctx_cache() -> FarmContextCache:
    return _farm_ctx_cache


def clear_all_caches() -> None:
    _prompt_cache._store.clear()
    _farm_ctx_cache._store.clear()
