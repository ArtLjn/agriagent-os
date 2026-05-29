"""天气数据进程内缓存，dict + TTL 模式。"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 600  # 10 分钟
_ALERT_TTL = 1800  # 30 分钟
_ALERT_PREFIX = "alert:"


class WeatherCache:
    """进程内字典缓存，支持 TTL 过期。"""

    _ALERT_TTL = _ALERT_TTL
    _ALERT_PREFIX = _ALERT_PREFIX

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    @staticmethod
    def make_key(
        location: str, days: int = 7, lat: float | None = None, lon: float | None = None
    ) -> str:
        parts = [location or "", str(days)]
        if lat is not None:
            parts.append(f"{lat:.4f}")
        if lon is not None:
            parts.append(f"{lon:.4f}")
        return "|".join(parts)

    def get(self, key: str) -> tuple[Any, bool]:
        if key not in self._store:
            logger.debug("CACHE MISS key=%s (not found)", key)
            return None, False

        value, expire_at = self._store[key]
        if time.time() >= expire_at:
            del self._store[key]
            logger.debug("CACHE MISS key=%s (expired)", key)
            return None, False

        logger.debug("CACHE HIT key=%s", key)
        return value, True

    def set(self, key: str, value: Any, ttl: int = _DEFAULT_TTL) -> None:
        expire_at = time.time() + ttl
        self._store[key] = (value, expire_at)
        logger.debug("CACHE SET key=%s ttl=%ds", key, ttl)

    def clear(self) -> None:
        self._store.clear()
        logger.info("CACHE CLEARED")

    def get_alert(self, city: str) -> tuple[list | None, bool]:
        key = f"{self._ALERT_PREFIX}{city}"
        return self.get(key)

    def set_alert(self, city: str, alerts: list, ttl: int = _ALERT_TTL) -> None:
        key = f"{self._ALERT_PREFIX}{city}"
        self.set(key, alerts, ttl=ttl)


weather_cache = WeatherCache()

__all__ = ["WeatherCache", "weather_cache"]
