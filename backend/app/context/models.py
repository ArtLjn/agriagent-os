"""Context 数据模型。"""

from dataclasses import dataclass, field
from typing import Any

from app.context.compressors import compress_text


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数，中文场景按字符和空白词数取较大值。"""
    if not text:
        return 0
    compact_chars = len(text)
    word_count = len(text.split())
    return max(1, max(word_count, compact_chars // 2))


@dataclass(slots=True)
class ContextBlock:
    """可注入模型的单个上下文块。"""

    key: str
    source: str
    purpose: str
    content: str
    priority: int
    token_estimate: int | None = None
    required: bool = False
    compressible: bool = True
    min_tokens: int = 32
    ttl_seconds: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_compressed: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        if self.token_estimate is None:
            self.token_estimate = estimate_tokens(self.content)

    def compressed_copy(self, target_tokens: int) -> "ContextBlock":
        """返回压缩后的 block 副本。"""
        token_limit = max(self.min_tokens, target_tokens)
        char_limit = max(24, token_limit * 2)
        content = self.content
        content = compress_text(content, char_limit)
        return ContextBlock(
            key=self.key,
            source=self.source,
            purpose=self.purpose,
            content=content,
            priority=self.priority,
            token_estimate=min(estimate_tokens(content), token_limit),
            required=self.required,
            compressible=False,
            min_tokens=self.min_tokens,
            ttl_seconds=self.ttl_seconds,
            metadata={**self.metadata, "original_tokens": self.token_estimate},
            is_compressed=True,
            reason="compressed_to_fit_budget",
        )

    def with_reason(self, reason: str) -> "ContextBlock":
        """返回带预算决策原因的副本。"""
        return ContextBlock(
            key=self.key,
            source=self.source,
            purpose=self.purpose,
            content=self.content,
            priority=self.priority,
            token_estimate=self.token_estimate,
            required=self.required,
            compressible=self.compressible,
            min_tokens=self.min_tokens,
            ttl_seconds=self.ttl_seconds,
            metadata=dict(self.metadata),
            is_compressed=self.is_compressed,
            reason=reason,
        )

    def with_metadata(self, **metadata: Any) -> "ContextBlock":
        """返回合并 metadata 的副本。"""
        return ContextBlock(
            key=self.key,
            source=self.source,
            purpose=self.purpose,
            content=self.content,
            priority=self.priority,
            token_estimate=self.token_estimate,
            required=self.required,
            compressible=self.compressible,
            min_tokens=self.min_tokens,
            ttl_seconds=self.ttl_seconds,
            metadata={**self.metadata, **metadata},
            is_compressed=self.is_compressed,
            reason=self.reason,
        )

    def summary(self) -> dict[str, Any]:
        """输出 trace 友好的摘要。"""
        return {
            "key": self.key,
            "source": self.source,
            "purpose": self.purpose,
            "priority": self.priority,
            "token_estimate": self.token_estimate or 0,
            "required": self.required,
            "compressed": self.is_compressed,
            "reason": self.reason,
            "layer": self.metadata.get("layer", ""),
            "intent_tags": self.metadata.get("intent_tags", []),
            "required_reason": self.metadata.get("required_reason", ""),
            "cache_scope": self.metadata.get("cache_scope", ""),
            "selected_by_skill_dependencies": self.metadata.get(
                "selected_by_skill_dependencies", []
            ),
        }


@dataclass(slots=True)
class ContextBundle:
    """预算处理后的上下文集合。"""

    blocks: list[ContextBlock]
    token_budget: int
    token_estimate: int
    compressed_blocks: list[ContextBlock] = field(default_factory=list)
    dropped_blocks: list[ContextBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def render_text(self) -> str:
        """渲染为可放入 prompt 的上下文文本。"""
        return "\n\n".join(block.content for block in self.blocks if block.content)

    def summary(self) -> dict[str, Any]:
        """输出 ContextBundle trace 摘要。"""
        from app.context.renderer import ContextRenderer

        section_summary = ContextRenderer().debug_summary(self)
        summary = {
            "token_budget": self.token_budget,
            "token_estimate": self.token_estimate,
            "blocks": [block.summary() for block in self.blocks],
            "compressed_blocks": [block.summary() for block in self.compressed_blocks],
            "dropped_blocks": [block.summary() for block in self.dropped_blocks],
            **self.metadata,
        }
        summary["sections"] = section_summary["sections"]
        return summary


__all__ = ["ContextBlock", "ContextBundle", "estimate_tokens"]
