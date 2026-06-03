"""Context token 预算策略测试。"""

from app.context.budget import TokenBudget
from app.context.models import ContextBlock


def test_budget_keeps_required_blocks_and_drops_low_priority_blocks() -> None:
    blocks = [
        ContextBlock(
            key="safety",
            source="policy",
            purpose="安全规则",
            content="安全内容",
            priority=100,
            token_estimate=10,
            required=True,
        ),
        ContextBlock(
            key="retrieval",
            source="retrieval",
            purpose="检索结果",
            content="x" * 200,
            priority=10,
            token_estimate=80,
        ),
    ]

    bundle = TokenBudget(max_tokens=30).apply(blocks)

    assert [block.key for block in bundle.blocks] == ["safety"]
    assert bundle.token_estimate == 10
    assert bundle.dropped_blocks[0].key == "retrieval"
    assert bundle.dropped_blocks[0].reason == "token_budget_exceeded"


def test_budget_compresses_low_priority_compressible_block_before_drop() -> None:
    block = ContextBlock(
        key="conversation",
        source="conversation",
        purpose="最近对话",
        content="第一轮对话。" * 80,
        priority=30,
        token_estimate=120,
        compressible=True,
        min_tokens=20,
    )

    bundle = TokenBudget(max_tokens=50).apply([block])

    assert bundle.blocks[0].key == "conversation"
    assert bundle.blocks[0].is_compressed is True
    assert bundle.blocks[0].token_estimate <= 50
    assert bundle.compressed_blocks[0].reason == "compressed_to_fit_budget"


def test_context_block_summary_includes_trace_metadata() -> None:
    block = ContextBlock(
        key="system",
        source="system",
        purpose="系统规则",
        content="系统内容",
        priority=100,
        metadata={
            "layer": "platform",
            "intent_tags": ["safety", "routing"],
            "required_reason": "system_policy",
            "cache_scope": "session",
        },
    )

    summary = block.summary()

    assert summary["layer"] == "platform"
    assert summary["intent_tags"] == ["safety", "routing"]
    assert summary["required_reason"] == "system_policy"
    assert summary["cache_scope"] == "session"


def test_context_block_summary_uses_stable_trace_metadata_defaults() -> None:
    block = ContextBlock(
        key="farm",
        source="farm",
        purpose="农场",
        content="默认农场",
        priority=90,
    )

    summary = block.summary()

    assert summary["layer"] == ""
    assert summary["intent_tags"] == []
    assert summary["required_reason"] == ""
    assert summary["cache_scope"] == ""


def test_budget_marks_required_blocks_that_exceed_budget() -> None:
    block = ContextBlock(
        key="system",
        source="system",
        purpose="系统规则",
        content="系统内容",
        priority=100,
        token_estimate=120,
        required=True,
    )

    bundle = TokenBudget(max_tokens=30).apply([block])

    assert [kept.key for kept in bundle.blocks] == ["system"]
    assert bundle.metadata["over_budget_required_blocks"] == ["system"]
    assert bundle.metadata["budget_exceeded"] is True
