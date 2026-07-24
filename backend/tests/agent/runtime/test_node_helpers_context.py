"""Runtime Context 拼装测试。"""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.runtime.node_helpers import (
    _append_runtime_context,
    _record_prompt_budget,
)
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


def test_record_prompt_budget_records_final_llm_context_snapshot() -> None:
    """Trace 应记录最终送入 LLM 的 system prompt 和压缩后消息。"""
    collector = MagicMock()
    system_text = "系统提示" * 800
    raw_messages = [
        HumanMessage(content="会被 compact_messages 过滤的旧消息"),
        HumanMessage(content="用户要查看茬口"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call-1",
                    "name": "manage_crop_cycle",
                    "args": {"action": "list"},
                }
            ],
        ),
        ToolMessage(content="当前活跃茬口：夏季西瓜", tool_call_id="call-1"),
    ]
    bundle = ContextBundle(
        blocks=[
            ContextBlock(
                key="farm",
                source="farm",
                purpose="农场状态",
                content="农场：测试农场",
                priority=80,
            )
        ],
        token_budget=200,
        token_estimate=32,
    )

    _record_prompt_budget(
        collector=collector,
        system_text=system_text,
        prompt_scene="agent",
        context_bundle=bundle,
        state={"messages": raw_messages},
        compact_messages_func=lambda messages: messages[1:],
        find_last_human_message_func=lambda messages: messages[-3].content,
    )

    records = [call.kwargs for call in collector.record.call_args_list]
    snapshot_record = next(
        item
        for item in records
        if item["node_type"] == "prompt_budget"
        and item["node_name"] == "final_llm_context"
    )
    output = snapshot_record["output_data"]
    assert output["system_prompt"] == system_text
    assert output["context_blocks"] == ["farm"]
    assert (
        output["budget"]["total_tokens"]
        == snapshot_record["token_usage"]["prompt_tokens"]
    )
    assert [message["role"] for message in output["messages"]] == [
        "user",
        "assistant",
        "tool",
    ]
    assert output["messages"][0]["content"] == "用户要查看茬口"
    assert output["messages"][1]["tool_calls"][0]["name"] == "manage_crop_cycle"
    assert output["messages"][2]["tool_call_id"] == "call-1"
