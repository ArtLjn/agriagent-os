"""Context 构建流水线。

本模块集中维护预算裁剪、压缩、注入白名单、渲染和 trace 安全文本工具。
旧的 ``app.context.pipeline.<name>`` 导入路径通过底部兼容模块保留。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Iterable, Mapping

from langchain_core.messages import AIMessage

from app.context.core.document import ContextDocument, ContextSection
from app.context.core.models import ContextBlock, ContextBundle
from app.context.core.registry import prompt_allowed_keys, section_for_key


ALLOWED_CONTEXT_KEYS: frozenset[str] = prompt_allowed_keys()
FORBIDDEN_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "weather_snapshot",
        "weather_summary",
        "farm_status_snapshot",
        "crop_cycle_details",
        "crop_stage_details",
        "recent_logs_summary",
        "worker_list_snapshot",
        "cost_summary_snapshot",
        "debt_summary_snapshot",
        "labor_payables_snapshot",
    }
)


def is_allowed_key(key: str) -> bool:
    """判断 block key 是否允许注入 ContextBundle。"""
    if key in FORBIDDEN_CONTEXT_KEYS:
        return False
    return key in ALLOWED_CONTEXT_KEYS


class TokenBudget:
    """按优先级保留、压缩或丢弃 ContextBlock。"""

    def __init__(self, max_tokens: int) -> None:
        self.max_tokens = max_tokens

    def apply(self, blocks: list[ContextBlock]) -> ContextBundle:
        """应用预算并返回 bundle。"""
        kept: list[ContextBlock] = []
        compressed: list[ContextBlock] = []
        dropped: list[ContextBlock] = []
        over_budget_required_blocks: list[str] = []
        used = 0

        ordered = sorted(blocks, key=lambda block: (-block.priority, block.key))
        for block in ordered:
            tokens = block.token_estimate or 0
            if used + tokens <= self.max_tokens:
                kept.append(block)
                used += tokens
                continue

            if block.required:
                kept.append(block)
                used += tokens
                over_budget_required_blocks.append(block.key)
                continue

            remaining = self.max_tokens - used
            if block.compressible and remaining >= block.min_tokens:
                compact = block.compressed_copy(remaining)
                kept.append(compact)
                compressed.append(compact)
                used += compact.token_estimate or 0
                continue

            dropped.append(block.with_reason("token_budget_exceeded"))

        return ContextBundle(
            blocks=kept,
            token_budget=self.max_tokens,
            token_estimate=used,
            compressed_blocks=compressed,
            dropped_blocks=dropped,
            metadata={
                "budget_exceeded": used > self.max_tokens,
                "over_budget_required_blocks": over_budget_required_blocks,
            },
        )


class ContextRenderer:
    """将 ContextBundle 渲染为分区化 prompt 和日志摘要。"""

    SECTION_NAMES: tuple[str, ...] = (
        "Role & Policies",
        "Task",
        "Evidence",
        "Context",
        "Output",
    )

    def section_name_for_key(self, key: str) -> str:
        """按 block key 解析分区，未知 key 归入 Context。"""
        return section_for_key(key)

    def render_document(self, bundle: ContextBundle) -> ContextDocument:
        """把 ContextBundle 转为稳定分区顺序的 ContextDocument。"""
        grouped = {name: [] for name in self.SECTION_NAMES}
        for block in bundle.blocks:
            grouped[self.section_name_for_key(block.key)].append(block)
        return ContextDocument(
            sections=tuple(
                ContextSection(name=name, blocks=tuple(grouped[name]))
                for name in self.SECTION_NAMES
            )
        )

    def render_prompt_text(self, bundle: ContextBundle) -> str:
        """渲染可注入模型的分区化上下文。"""
        return self.render_document(bundle).render_prompt_text()

    def debug_summary(self, bundle: ContextBundle) -> dict:
        """渲染日志友好的分区摘要，不包含正文。"""
        return self.render_document(bundle).debug_summary()


def compress_text(text: str, max_chars: int) -> str:
    """按字符预算压缩文本，保留稳定的省略标记。"""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars == 1:
        return "…"
    return text[: max_chars - 1].rstrip() + "…"


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


def _install_legacy_module(module_name: str, exported_names: tuple[str, ...]) -> None:
    module = ModuleType(f"{__name__}.{module_name}")
    module.__doc__ = "兼容入口；实际维护点是 app.context.pipeline。"
    for exported_name in exported_names:
        setattr(module, exported_name, globals()[exported_name])
    module.__all__ = list(exported_names)
    sys.modules[module.__name__] = module
    setattr(sys.modules[__name__], module_name, module)


def _install_legacy_pipeline_modules() -> None:
    _install_legacy_module(
        "allowlist",
        ("ALLOWED_CONTEXT_KEYS", "FORBIDDEN_CONTEXT_KEYS", "is_allowed_key"),
    )
    _install_legacy_module("budget", ("TokenBudget",))
    _install_legacy_module("renderer", ("ContextRenderer",))
    _install_legacy_module("compressors", ("compress_text",))
    _install_legacy_module(
        "compression",
        (
            "CompressionEvent",
            "compact_tool_result",
            "is_tool_result_compressed",
            "safe_preview",
            "safe_text",
            "safe_trace_value",
            "tool_call_names_by_id",
        ),
    )
    text_module = ModuleType(f"{__name__}.compressors.text")
    text_module.__doc__ = "兼容入口；实际维护点是 app.context.pipeline。"
    text_module.compress_text = compress_text
    text_module.__all__ = ["compress_text"]
    sys.modules[text_module.__name__] = text_module
    sys.modules[f"{__name__}.compressors"].text = text_module


_install_legacy_pipeline_modules()

__all__ = [
    "ALLOWED_CONTEXT_KEYS",
    "CompressionEvent",
    "ContextRenderer",
    "FORBIDDEN_CONTEXT_KEYS",
    "TokenBudget",
    "compact_tool_result",
    "compress_text",
    "is_allowed_key",
    "is_tool_result_compressed",
    "safe_preview",
    "safe_text",
    "safe_trace_value",
    "tool_call_names_by_id",
]
