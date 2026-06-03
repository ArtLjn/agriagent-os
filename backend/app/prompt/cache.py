"""Prompt 缓存入口。

底层 TTL 缓存由 Context 模块统一维护，Prompt 模块保留该入口以表达
Prompt 工程边界并避免历史 import 断裂。
"""

from app.context.cache import (
    FarmContextCache,
    PromptCache,
    clear_all_caches,
    get_farm_ctx_cache,
    get_prompt_cache,
)

__all__ = [
    "FarmContextCache",
    "PromptCache",
    "clear_all_caches",
    "get_farm_ctx_cache",
    "get_prompt_cache",
]
