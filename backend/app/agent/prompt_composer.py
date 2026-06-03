"""兼容入口：Prompt 组合器已迁移到 app.prompt.composer。"""

from app.prompt.composer import PromptComposer, get_composer

__all__ = ["PromptComposer", "get_composer"]
