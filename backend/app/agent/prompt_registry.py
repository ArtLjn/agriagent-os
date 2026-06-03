"""兼容入口：Prompt 注册表已迁移到 app.prompt.registry。"""

from app.prompt.registry import PromptRegistry, get_registry

__all__ = ["PromptRegistry", "get_registry"]
