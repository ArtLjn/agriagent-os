"""兼容入口：LLM 客户端已迁移到 app.core.llm。"""

from types import ModuleType
import sys

import app.core.llm as _core_llm

ChatOpenAI = _core_llm.ChatOpenAI
LlmNotConfiguredError = _core_llm.LlmNotConfiguredError
get_llm = _core_llm.get_llm
settings = _core_llm.settings


class _LlmCompatModule(ModuleType):
    """转发旧 patch target，避免迁移破坏历史测试和外部补丁点。"""

    def __setattr__(self, name: str, value) -> None:
        if name in {"ChatOpenAI", "settings"}:
            setattr(_core_llm, name, value)
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _LlmCompatModule

__all__ = ["ChatOpenAI", "LlmNotConfiguredError", "get_llm", "settings"]
