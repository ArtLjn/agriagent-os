"""兼容入口：助手角色配置已迁移到 app.core.settings.roles。"""

from app.core.settings.roles import (
    ASSISTANT_ROLE_LABELS,
    ASSISTANT_ROLE_PROMPTS,
    ASSISTANT_ROLE_TEMPERATURES,
    DEFAULT_ASSISTANT_ROLE,
    AssistantRole,
    assistant_role_label,
    assistant_role_prompt,
    normalize_assistant_role,
)

__all__ = [
    "ASSISTANT_ROLE_LABELS",
    "ASSISTANT_ROLE_PROMPTS",
    "ASSISTANT_ROLE_TEMPERATURES",
    "AssistantRole",
    "DEFAULT_ASSISTANT_ROLE",
    "assistant_role_label",
    "assistant_role_prompt",
    "normalize_assistant_role",
]
