"""Runtime Context 拼装测试。"""

from app.agent.runtime.node_helpers import _append_runtime_context
from app.context.models import ContextBlock, ContextBundle


def test_append_runtime_context_uses_sectioned_prompt_text() -> None:
    bundle = ContextBundle(
        blocks=[
            ContextBlock(
                key="farm",
                source="farm",
                purpose="农场状态",
                content="农场：测试农场",
                priority=80,
            ),
            ContextBlock(
                key="retrieval",
                source="rag",
                purpose="检索证据",
                content="资料：番茄适合排水良好的土壤",
                priority=70,
            ),
        ],
        token_budget=200,
        token_estimate=32,
    )

    text = _append_runtime_context("系统提示", bundle)

    assert text.startswith("系统提示\n\n<runtime_context>")
    assert "## Evidence\n\n### retrieval\n资料：番茄适合排水良好的土壤" in text
    assert "## Context\n\n### farm\n农场：测试农场" in text
    assert text.index("## Evidence") < text.index("## Context")
    assert text.endswith("</runtime_context>")
