"""兼容入口：Prompt 渲染器已迁移到 app.prompt.renderer。"""

from app.prompt.renderer import _build_builtin_vars, render_prompt, render_prompt_input

__all__ = ["_build_builtin_vars", "render_prompt", "render_prompt_input"]
