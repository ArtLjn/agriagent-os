"""Trace payload 安全边界。

Trace 只保存可诊断的脱敏摘要，不保存凭证、隐藏推理链或无限大的外部
payload。该边界独立于 Collector，便于 API、回放和测试复用同一套规则。
"""

from __future__ import annotations

import json
import re
from typing import Any

_SENSITIVE_KEY = re.compile(
    r"(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"password|passwd|secret|credential|cookie|set-cookie|private[_-]?key)",
    re.IGNORECASE,
)
_HIDDEN_REASONING_KEY = re.compile(
    r"(?:chain[_-]?of[_-]?thought|hidden[_-]?thought|reasoning[_-]?content|"
    r"internal[_-]?monologue|scratchpad)",
    re.IGNORECASE,
)
_REDACTED = "[REDACTED]"
_HIDDEN = "[HIDDEN_REASONING_OMITTED]"


def sanitize_payload(value: Any, *, max_chars: int) -> Any:
    """递归脱敏并限制序列化后的 Trace payload 大小。"""
    sanitized = _sanitize_value(value)
    serialized = json.dumps(sanitized, ensure_ascii=False, default=str)
    if len(serialized) <= max_chars:
        return sanitized
    return {
        "__truncated": True,
        "__original_len": len(serialized),
        "preview": serialized[:max_chars],
    }


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                _HIDDEN
                if _HIDDEN_REASONING_KEY.search(str(key))
                else _REDACTED
                if _SENSITIVE_KEY.search(str(key))
                else _sanitize_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return value
    return value


def safe_token_usage(value: Any) -> dict[str, int] | None:
    """只保留 token usage 数值字段，拒绝把 provider 原始响应带入 Trace。"""
    if not isinstance(value, dict):
        return None
    aliases = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
        "reasoning_tokens": ("reasoning_tokens",),
        "cached_tokens": ("cached_tokens",),
    }
    result: dict[str, int] = {}
    for target, keys in aliases.items():
        for key in keys:
            try:
                if value.get(key) is not None:
                    result[target] = max(0, int(value[key]))
                    break
            except (TypeError, ValueError):
                continue
    return result or None


__all__ = ["sanitize_payload", "safe_token_usage"]
