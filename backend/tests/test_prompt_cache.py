"""System prompt + farm context TTL 缓存测试。"""

import time

from app.agent.prompt_cache import (
    PromptCache,
    FarmContextCache,
    clear_all_caches,
    get_prompt_cache,
    get_farm_ctx_cache,
)
from app.context.invalidation import invalidate_farm_context


class TestPromptCache:
    """system prompt 渲染结果缓存。"""

    def test_cache_miss_returns_none(self):
        cache = PromptCache(ttl_seconds=3600)
        result = cache.get(farm_id=1, date_str="2026-06-02")
        assert result is None

    def test_cache_set_and_get(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-02", value="rendered prompt")
        result = cache.get(farm_id=1, date_str="2026-06-02")
        assert result == "rendered prompt"

    def test_cache_key_includes_farm_and_date(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-02", value="farm1")
        cache.set(farm_id=2, date_str="2026-06-02", value="farm2")
        assert cache.get(farm_id=1, date_str="2026-06-02") == "farm1"
        assert cache.get(farm_id=2, date_str="2026-06-02") == "farm2"

    def test_cache_different_dates(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-01", value="day1")
        cache.set(farm_id=1, date_str="2026-06-02", value="day2")
        assert cache.get(farm_id=1, date_str="2026-06-01") == "day1"
        assert cache.get(farm_id=1, date_str="2026-06-02") == "day2"

    def test_cache_expires_after_ttl(self):
        cache = PromptCache(ttl_seconds=1)
        cache.set(farm_id=1, date_str="2026-06-02", value="expired")
        time.sleep(1.1)
        assert cache.get(farm_id=1, date_str="2026-06-02") is None

    def test_cache_invalidate_by_farm(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-02", value="v1")
        cache.set(farm_id=2, date_str="2026-06-02", value="v2")
        cache.invalidate(farm_id=1)
        assert cache.get(farm_id=1, date_str="2026-06-02") is None
        assert cache.get(farm_id=2, date_str="2026-06-02") == "v2"


class TestFarmContextCache:
    """农场上下文缓存。"""

    def test_cache_miss_returns_none(self):
        cache = FarmContextCache(ttl_seconds=300)
        assert cache.get(farm_id=1) is None

    def test_cache_set_and_get(self):
        cache = FarmContextCache(ttl_seconds=300)
        ctx = {"display_name": "张三", "farm_location": "北京"}
        cache.set(farm_id=1, value=ctx)
        assert cache.get(farm_id=1) == ctx

    def test_cache_expires(self):
        cache = FarmContextCache(ttl_seconds=1)
        cache.set(farm_id=1, value={"display_name": "张三"})
        time.sleep(1.1)
        assert cache.get(farm_id=1) is None

    def test_cache_invalidate(self):
        cache = FarmContextCache(ttl_seconds=300)
        cache.set(farm_id=1, value={"display_name": "张三"})
        cache.invalidate(farm_id=1)
        assert cache.get(farm_id=1) is None


class TestClearAllCaches:
    """全局缓存清理。"""

    def test_clear_all(self):
        pc = get_prompt_cache()
        fc = get_farm_ctx_cache()
        pc.set(farm_id=1, date_str="2026-06-02", value="prompt")
        fc.set(farm_id=1, value={"display_name": "张三"})
        clear_all_caches()
        assert pc.get(farm_id=1, date_str="2026-06-02") is None
        assert fc.get(farm_id=1) is None


class TestInvalidateFarmContext:
    """农场上下文失效 helper。"""

    def test_invalidate_global_prompt_and_farm_context_caches(self):
        pc = get_prompt_cache()
        fc = get_farm_ctx_cache()
        clear_all_caches()
        pc.set(farm_id=1, date_str="2026-06-02", value="prompt")
        pc.set(farm_id=1, date_str="2026-06-03", value="prompt next")
        pc.set(farm_id=2, date_str="2026-06-02", value="other farm")
        fc.set(farm_id=1, value={"display_name": "张三"})
        fc.set(farm_id=2, value={"display_name": "李四"})

        result = invalidate_farm_context(1)

        assert result == {
            "prompt_invalidated": 2,
            "farm_context_invalidated": True,
        }
        assert pc.get(farm_id=1, date_str="2026-06-02") is None
        assert pc.get(farm_id=1, date_str="2026-06-03") is None
        assert fc.get(farm_id=1) is None
        assert pc.get(farm_id=2, date_str="2026-06-02") == "other farm"
        assert fc.get(farm_id=2) == {"display_name": "李四"}
        clear_all_caches()
