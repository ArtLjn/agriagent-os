"""Token 估算 + 上下文占用计算。

不引入 tiktoken（避免下载 BPE 表）。近似算法：
- 中文 1 字 ≈ 1.5 token
- 英文/符号 1 char ≈ 0.25 token
误差 < 15%（qwen/glm 等中文模型）。

参考：harness_study/_example/core/tokenizer.py
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.platforms.llm.client import MODEL

DEFAULT_MAX_CONTEXT = 32_768
DEFAULT_RESPONSE_RESERVE = 4_096
DEFAULT_SAFETY_MARGIN = 1_024

# 演示用的小阈值：聊几轮就能看到 30%/50%/70% 变化，触发 summarizer。
# 真实模型支持 128K/1M，但小阈值让压缩机制更容易触发。
MODEL_CONTEXT_MAP: list[tuple[str, int]] = [
    ("qwen3.6-flash", 32_000),
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
    if not model_id:
        return DEFAULT_MAX_CONTEXT
    mid = model_id.lower()
    for prefix, size in MODEL_CONTEXT_MAP:
        if prefix in mid:
            return size
    return DEFAULT_MAX_CONTEXT


def count_tokens(text: str) -> int:
    """估算字符串的 token 数。"""
    if not text:
        return 0
    chinese = sum(1 for c in text if "一" <= c <= "鿿")
    other = len(text) - chinese
    return int(chinese * 1.5 + other / 4)


def count_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """估算 messages 列表的总 token 数（含每条 message 的开销）。"""
    total = 0
    for m in messages:
        total += 4  # role/content 等字段开销
        content = m.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += count_tokens(str(part.get("text", "")))
        # tool_calls 的 arguments 也算
        tc = m.get("tool_calls")
        if tc:
            for call in tc:
                fn = call.get("function", {}) if isinstance(call, dict) else {}
                total += count_tokens(fn.get("arguments", "") or "")
    return total


def count_tools_tokens(tools: list[dict[str, Any]] | None) -> int:
    """估算 Tool Schema，避免只看 messages 导致实际请求超预算。"""
    if not tools:
        return 0
    return count_tokens(str(tools)) + len(tools) * 8


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
    estimation_mode: str = "approximate"
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
