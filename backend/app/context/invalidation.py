"""Context 缓存失效 helper。"""

from app.context.cache import get_farm_ctx_cache, get_prompt_cache


def invalidate_farm_context(farm_id: int) -> dict[str, int | bool]:
    """清理指定农场的 prompt 和运行时上下文缓存。"""
    prompt_invalidated = get_prompt_cache().invalidate(farm_id)
    farm_context_invalidated = get_farm_ctx_cache().invalidate(farm_id)
    return {
        "prompt_invalidated": prompt_invalidated,
        "farm_context_invalidated": farm_context_invalidated,
    }


__all__ = ["invalidate_farm_context"]
