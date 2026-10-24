"""上下文计量：使用 UTF-8 字节数保守计费，避免字符比例低估中英文混合与工具 JSON。

兼容模型没有统一 tokenizer；字节级 BPE 的 token 数不超过输入字节数，另预留协议余量。
这不是 Provider 的精确计费值，Trace 必须保留计量模式。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from agent.platforms.llm.client import MODEL

DEFAULT_MAX_CONTEXT = 32_768
DEFAULT_RESPONSE_RESERVE = 4_096
DEFAULT_SAFETY_MARGIN = 1_024

# 工作窗口独立于厂商最大窗口；Flash 官方上限 1M，这里按保守字节计量限定为 64K。
# 来源：https://help.aliyun.com/zh/model-studio/qwen3-6-flash
# 网关实际额度更低时通过 CONTEXT__MODEL_CONTEXT_TOKENS 配置覆盖。
MODEL_CONTEXT_MAP: list[tuple[str, int]] = [
    ("qwen3.6-flash", 64_000),
    ("qwen3.6-35b", 128_000),
    ("qwen3.6-plus", 128_000),
    ("qwen3.7-max", 128_000),
    ("qwen3.5-35b", 128_000),
    ("qwen3-235b", 128_000),
    ("glm-5", 128_000),
    ("deepseek-v4", 128_000),
    ("qwen2.5-7b", 32_000),
]

# 阈值（仿 Claude Code）
THRESHOLD_GREEN = 0.5
THRESHOLD_YELLOW = 0.7
THRESHOLD_ORANGE = 0.85
THRESHOLD_RED = 0.95


def get_model_context(model_id: str | None) -> int:
    """根据模型 id 返回上下文窗口大小。"""
    configured = os.getenv("CONTEXT__MODEL_CONTEXT_TOKENS")
    if configured:
        value = int(configured)
        if value <= 0:
            raise ValueError("invalid_model_context_tokens")
        return value
    if not model_id:
        model_id = MODEL
    mid = model_id.lower()
    for prefix, size in MODEL_CONTEXT_MAP:
        if prefix in mid:
            return size
    return DEFAULT_MAX_CONTEXT


def count_tokens(text: str) -> int:
    """估算字符串的 token 数。"""
    if not text:
        return 0
    return len(text.encode("utf-8"))


def count_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """估算 messages 列表的总 token 数（含每条 message 的开销）。"""
    return sum(
        count_tokens(json.dumps(m, ensure_ascii=False, separators=(",", ":"))) + 16
        for m in messages
    )


def count_tools_tokens(tools: list[dict[str, Any]] | None) -> int:
    """估算 Tool Schema，避免只看 messages 导致实际请求超预算。"""
    if not tools:
        return 0
    return (
        count_tokens(json.dumps(tools, ensure_ascii=False, separators=(",", ":")))
        + len(tools) * 16
    )


@dataclass
class ContextUsage:
    """上下文使用情况。"""

    used: int
    total: int
    ratio: float
    level: str  # green | yellow | orange | red
    message_tokens: int = 0
    tool_schema_tokens: int = 0
    response_reserve: int = 0
    safety_margin: int = 0
    usable: int = 0
    estimation_mode: str = "utf8_upper_bound"
    decision: str = "within_budget"

    @property
    def percent(self) -> int:
        return int(self.ratio * 100)


def compute_usage(
    messages: list[dict[str, Any]],
    total: int | None = None,
    *,
    tools: list[dict[str, Any]] | None = None,
    response_reserve: int = DEFAULT_RESPONSE_RESERVE,
    safety_margin: int = DEFAULT_SAFETY_MARGIN,
) -> ContextUsage:
    """计算最终请求的消息、Tool Schema 与输出预留预算。"""
    if total is None:
        total = get_model_context(MODEL)
    message_tokens = count_messages_tokens(messages)
    tool_schema_tokens = count_tools_tokens(tools)
    used = message_tokens + tool_schema_tokens
    usable = max(total - response_reserve - safety_margin, 0)
    decision = "within_budget" if used <= usable else "budget_exceeded"
    ratio = min(used / total, 1.0) if total else 0
    if ratio < THRESHOLD_GREEN:
        level = "green"
    elif ratio < THRESHOLD_YELLOW:
        level = "yellow"
    elif ratio < THRESHOLD_ORANGE:
        level = "orange"
    else:
        level = "red"
    return ContextUsage(
        used=used,
        total=total,
        ratio=ratio,
        level=level,
        message_tokens=message_tokens,
        tool_schema_tokens=tool_schema_tokens,
        response_reserve=response_reserve,
        safety_margin=safety_margin,
        usable=usable,
        decision=decision,
    )


def should_compress(usage: ContextUsage) -> bool:
    """soft 阈值：>= 70% 触发异步压缩。"""
    return usage.ratio >= THRESHOLD_YELLOW


def must_compress(usage: ContextUsage) -> bool:
    """hard 阈值：>= 85% 必须同步压缩。"""
    return usage.ratio >= THRESHOLD_ORANGE
