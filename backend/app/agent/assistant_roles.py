"""助手回复角色偏好。"""

from pathlib import Path
from typing import Literal

import yaml

AssistantRole = Literal["professional", "warm", "creative"]

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
_ROLE_CONFIG_PATH = _PROMPTS_DIR / "assistant_roles.yaml"


def _load_role_config() -> dict:
    """从 prompts 目录读取助手角色配置。"""
    data = yaml.safe_load(_ROLE_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    roles = data.get("roles") or {}
    if not isinstance(roles, dict) or "warm" not in roles:
        raise ValueError("assistant_roles.yaml 缺少 roles.warm 默认角色配置")
    return data


_ROLE_CONFIG = _load_role_config()
_ROLE_DEFINITIONS: dict[str, dict] = _ROLE_CONFIG["roles"]

DEFAULT_ASSISTANT_ROLE: AssistantRole = _ROLE_CONFIG.get("default", "warm")

ASSISTANT_ROLE_LABELS: dict[str, str] = {
    role: str(definition["label"])
    for role, definition in _ROLE_DEFINITIONS.items()
}

ASSISTANT_ROLE_TEMPERATURES: dict[str, float] = {
    role: float(definition["temperature"])
    for role, definition in _ROLE_DEFINITIONS.items()
}

ASSISTANT_ROLE_PROMPTS: dict[str, str] = {
    role: str(definition["prompt"])
    for role, definition in _ROLE_DEFINITIONS.items()
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
