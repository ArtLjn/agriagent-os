"""Context 压缩与 trace 安全文本工具。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from langchain_core.messages import AIMessage


REDACTED = "[REDACTED]"
SENSITIVE_KEYS = {
    "api-key",
    "apikey",
    "x-api-key",
    "authorization",
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
}
SENSITIVE_KEY_PARTS = {
    "authorization",
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
}

_MONGO_URI_PASSWORD_RE = re.compile(
    r"(mongodb(?:\+srv)?://[^:/@\s]+:)([^@/\s]+)(@)",
    re.IGNORECASE,
)
_INLINE_SECRET_RE = re.compile(
    r"(?i)\b([a-z0-9_.-]*(?:x-api-key|api[_-]?key|apikey|authorization|token|"
    r"secret|password|passwd|pwd)[a-z0-9_.-]*)"
    r"(\s*[:=]\s*)(bearer\s+)?[^\s,;，；。]+"
)


@dataclass(slots=True)
class CompressionEvent:
    """一次压缩动作的可观测事件。"""

    target: str
    key: str
    action: str
    reason: str
    original_tokens: int
    final_tokens: int
    compressor: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """返回可安全写入 trace 的事件摘要。"""
        return {
            "target": safe_preview(self.target, max_chars=80),
            "key": safe_preview(self.key, max_chars=120),
            "action": safe_preview(self.action, max_chars=80),
            "reason": safe_preview(self.reason, max_chars=120),
            "original_tokens": self.original_tokens,
            "final_tokens": self.final_tokens,
            "compressor": safe_preview(self.compressor, max_chars=80),
            "metadata": safe_trace_value(self.metadata, max_chars=240),
        }


def compact_tool_result(
    *,
    content: str,
    tool_name: str | None,
    tool_call_id: str,
    status: str | None = None,
    max_summary_chars: int = 220,
) -> str:
    """把工具结果压缩为可解释、可追溯的结构化摘要。"""
    clean = " ".join(safe_text(str(content or "")).split())
    summary = safe_preview(clean, max_chars=max_summary_chars)
    return "\n".join(
        [
            "[工具结果已压缩]",
            f"tool: {safe_preview(tool_name or 'unknown', max_chars=120)}",
            f"status: {safe_preview(status or 'unknown', max_chars=80)}",
            f"summary: {summary or '工具已执行，旧结果已从上下文压缩。'}",
            f"ref: tool_call_id={safe_preview(tool_call_id, max_chars=160)}",
        ]
    )


def tool_call_names_by_id(messages: Iterable[Any]) -> dict[str, str]:
    """从 AIMessage.tool_calls 建立 tool_call_id 到工具名的映射。"""
    names: dict[str, str] = {}
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for tool_call in getattr(message, "tool_calls", None) or []:
            if not isinstance(tool_call, Mapping):
                continue
            tool_call_id = str(tool_call.get("id") or "")
            tool_name = str(tool_call.get("name") or "")
            if tool_call_id and tool_name:
                names[tool_call_id] = tool_name
    return names


def safe_trace_value(value: Any, *, max_chars: int = 1000) -> Any:
    """递归脱敏 trace 值，并对字符串做长度上限。"""
    if isinstance(value, Mapping):
        sanitized = {}
        for key, nested in value.items():
            key_text = str(key)
            sanitized[key_text] = (
                REDACTED
                if is_sensitive_key(key_text)
                else safe_trace_value(nested, max_chars=max_chars)
            )
        return sanitized
    if isinstance(value, list):
        return [safe_trace_value(item, max_chars=max_chars) for item in value]
    if isinstance(value, tuple):
        return [safe_trace_value(item, max_chars=max_chars) for item in value]
    if isinstance(value, str):
        return safe_preview(value, max_chars=max_chars)
    if value is None or isinstance(value, int | float | bool):
        return value
    return safe_preview(str(value), max_chars=max_chars)


def safe_preview(text: str | None, *, max_chars: int = 240) -> str:
    """脱敏并截断单段 trace 文本。"""
    clean = " ".join(safe_text(str(text or "")).split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "..."


def safe_text(text: str) -> str:
    """脱敏字符串中的内联密钥和 Mongo URI 密码。"""
    redacted = _MONGO_URI_PASSWORD_RE.sub(r"\1" + REDACTED + r"\3", text)
    return _INLINE_SECRET_RE.sub(r"\1\2" + REDACTED, redacted)


def is_sensitive_key(key: str) -> bool:
    """判断字典 key 是否表示敏感字段。"""
    normalized = key.strip().lower().replace("_", "-")
    compact = normalized.replace("-", "")
    if normalized in SENSITIVE_KEYS or "apikey" in compact or "xapikey" in compact:
        return True
    parts = [part for part in re.split(r"[^a-z0-9]+", normalized) if part]
    return any(part in SENSITIVE_KEY_PARTS for part in parts)


def is_tool_result_compressed(content: Any) -> bool:
    """判断工具消息正文是否已经是结构化压缩结果。"""
    return "[工具结果已压缩]" in str(content or "")


__all__ = [
    "CompressionEvent",
    "compact_tool_result",
    "is_tool_result_compressed",
    "safe_preview",
    "safe_text",
    "safe_trace_value",
    "tool_call_names_by_id",
]
