"""助手回复角色偏好。"""

from typing import Literal

AssistantRole = Literal["professional", "warm", "creative"]

DEFAULT_ASSISTANT_ROLE: AssistantRole = "warm"

ASSISTANT_ROLE_LABELS: dict[str, str] = {
    "professional": "冷静专业型",
    "warm": "温暖陪伴型",
    "creative": "灵感创意型",
}

ASSISTANT_ROLE_TEMPERATURES: dict[str, float] = {
    "professional": 0.3,
    "warm": 0.6,
    "creative": 0.8,
}

ASSISTANT_ROLE_PROMPTS: dict[str, str] = {
    "professional": (
        "语气偏好：冷静专业型。回复应简洁、准确、克制，先给结论再补充必要解释；"
        "不使用夸张表达，遇到不确定信息要明确说明。"
    ),
    "warm": (
        "语气偏好：温暖陪伴型。回复应自然、亲切、耐心，先理解用户处境再给建议；"
        "可以适度鼓励，但不要油腻、夸张或说教。"
    ),
    "creative": (
        "语气偏好：灵感创意型。回复应鲜活、有画面感，主动提供多个方向和变体；"
        "可以适度轻松有趣，但仍要清晰、实用。"
    ),
}


def normalize_assistant_role(value: str | None) -> AssistantRole:
    """归一化助手角色，非法或空值回退到默认角色。"""
    if value in ASSISTANT_ROLE_PROMPTS:
        return value  # type: ignore[return-value]
    return DEFAULT_ASSISTANT_ROLE


def assistant_role_label(value: str | None) -> str:
    """返回助手角色中文标签。"""
    role = normalize_assistant_role(value)
    return ASSISTANT_ROLE_LABELS[role]


def assistant_role_prompt(value: str | None) -> str:
    """返回助手角色对应的 prompt 片段。"""
    role = normalize_assistant_role(value)
    temperature = ASSISTANT_ROLE_TEMPERATURES[role]
    return f"{ASSISTANT_ROLE_PROMPTS[role]} 回复温度参考：{temperature}。"


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
