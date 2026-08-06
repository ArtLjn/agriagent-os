"""final_llm_context v2 快照契约测试。"""

import json

from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.runtime.final_prompt_budget import FinalPromptBudget
from app.agent.runtime.node_helpers import _record_final_llm_context_trace
from app.context.core.models import ContextBlock, ContextBundle


class FakeCollector:
    """捕获 trace record 入参。"""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


def test_final_llm_context_snapshot_v2_is_structured_and_sanitized() -> None:
    """最终 LLM 快照应包含 v2 结构、压缩信息，并脱敏敏感内容。"""
    collector = FakeCollector()
    bundle = ContextBundle(
        blocks=[
            ContextBlock(
                key="farm",
                source="farm",
                purpose="农场状态",
                content="农场：测试农场 password=secret",
                priority=80,
            ),
            ContextBlock(
                key="conversation_summary",
                source="memory",
                purpose="历史摘要",
                content="用户之前询问过灌溉策略 password=secret",
                priority=60,
                is_compressed=True,
                reason="compressed_to_fit_budget",
                metadata={"original_tokens": 120},
            ),
        ],
        token_budget=200,
        token_estimate=64,
        compressed_blocks=[
            ContextBlock(
                key="conversation_summary",
                source="memory",
                purpose="历史摘要",
                content="用户之前询问过灌溉策略 password=secret",
                priority=60,
                token_estimate=32,
                is_compressed=True,
                reason="compressed_to_fit_budget",
                metadata={"original_tokens": 120},
            )
        ],
        metadata={
            "context_pack": {
                "recent_message_ids": [123],
                "summary_version": 4,
                "summary_hash": "sha256:abc",
                "selected_blocks": ["conversation_summary"],
            }
        },
    )
    messages = [
        HumanMessage(content="查看农场，password=secret"),
        ToolMessage(
            content="[工具结果已压缩]\ntool: get_farm_status\nstatus: success\n"
            "summary: 已返回农场状态 password=secret\nref: tool_call_id=tc1",
            tool_call_id="tc1",
        ),
    ]
    compacted, final_budget = FinalPromptBudget(max_tokens=200).apply(
        "系统提示 password=secret",
        messages,
    )

    _record_final_llm_context_trace(
        collector=collector,
        system_text="系统提示 password=secret",
        messages=compacted,
        context_bundle=bundle,
        final_budget=final_budget,
    )

    assert collector.records[0]["duration_ms"] >= 1
    output = collector.records[0]["output_data"]
    serialized = json.dumps(output, ensure_ascii=False)
    assert output["schema_version"] == 2
    assert output["system_prompt"] == "系统提示 password=[REDACTED]"
    assert output["context_blocks"] == ["farm", "conversation_summary"]
    assert output["runtime_context"]["sections"]
    assert output["runtime_context"]["context_pack"]["summary_version"] == 4
    assert output["runtime_context"]["context_pack"]["recent_message_ids"] == [123]
    assert output["runtime_context"]["context_pack"]["summary_hash"] == "sha256:abc"
    assert output["runtime_context"]["sections"][0]["blocks"][0]["content_preview"]
    assert output["budget"]["actions"] == final_budget.summary()["actions"]
    assert output["compression"]["context_compressed_count"] == 1
    assert output["messages"][0]["content_preview"] == "查看农场，password=[REDACTED]"
    assert output["messages"][1]["compressed"] is True
    assert "password=secret" not in serialized
