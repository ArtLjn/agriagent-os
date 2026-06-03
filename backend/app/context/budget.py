"""Context token 预算策略。"""

from app.context.models import ContextBlock, ContextBundle


class TokenBudget:
    """按优先级保留、压缩或丢弃 ContextBlock。"""

    def __init__(self, max_tokens: int) -> None:
        self.max_tokens = max_tokens

    def apply(self, blocks: list[ContextBlock]) -> ContextBundle:
        """应用预算并返回 bundle。"""
        kept: list[ContextBlock] = []
        compressed: list[ContextBlock] = []
        dropped: list[ContextBlock] = []
        used = 0

        ordered = sorted(blocks, key=lambda block: (-block.priority, block.key))
        for block in ordered:
            tokens = block.token_estimate or 0
            if used + tokens <= self.max_tokens or block.required:
                kept.append(block)
                used += tokens
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
        )


__all__ = ["TokenBudget"]
