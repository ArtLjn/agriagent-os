"""Skill TTL 缓存装饰器，基于内存字典。"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from functools import wraps

from skillify.models.schemas import ResultStatus, SkillResult

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, str], tuple[str, float]] = {}


def _make_key(skill_name: str, params: dict, farm_id: int | None = None) -> str:
    key_payload = {"farm_id": farm_id, "params": params}
    raw = json.dumps(key_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


def cached(ttl_seconds: int, key_fn: Callable[[dict], str] | None = None):
    """装饰 Skill.execute()，按 (skill_name, params_hash) 缓存结果。"""
    if ttl_seconds <= 0:

        def decorator(fn):
            return fn

        return decorator

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(self, params: dict, context, **kwargs):
            farm_id = getattr(context, "farm_id", None)
            farm_cache_prefix = (
                f"farm:{farm_id}" if isinstance(farm_id, int) else "farm:none"
            )
            params_key = key_fn(params) if key_fn else _make_key(self.name(), params)
            cache_key = f"{farm_cache_prefix}:{params_key}"
            full_key = (self.name(), cache_key)

            if full_key in _cache:
                result, expire_at = _cache[full_key]
                age = time.time() - (expire_at - ttl_seconds)
                if time.time() < expire_at:
                    logger.info(
                        "CACHE HIT skill=%s age=%.0fs ttl=%ds",
                        self.name(),
                        age,
                        ttl_seconds,
                    )
                    return SkillResult(status=ResultStatus.SUCCESS, reply=result)
                del _cache[full_key]

            logger.info("CACHE MISS skill=%s", self.name())
            result = await fn(self, params, context, **kwargs)

            if result.status.value == "success":
                _cache[full_key] = (result.reply, time.time() + ttl_seconds)

            return result

        return wrapper

    return decorator


def clear_cache(skill_name: str | None = None) -> int:
    """清除缓存，返回清除条数。"""
    if skill_name:
        keys = [k for k in _cache if k[0] == skill_name]
        for k in keys:
            del _cache[k]
        return len(keys)
    count = len(_cache)
    _cache.clear()
    return count


__all__ = ["cached", "clear_cache"]
