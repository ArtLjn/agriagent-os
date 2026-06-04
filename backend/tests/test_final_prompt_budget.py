"""最终 prompt 预算检查测试。"""

from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.runtime.final_prompt_budget import FinalPromptBudget


def test_final_prompt_budget_compacts_large_tool_results():
    """最终预算应覆盖 system、消息和工具结果，并压缩超大工具输出。"""
    budget = FinalPromptBudget(max_tokens=80, tool_result_limit=20)
    messages = [
        HumanMessage(content="查询账务"),
        ToolMessage(content="明细" * 300, tool_call_id="tc1"),
    ]

    compacted, result = budget.apply("system prompt" * 20, messages)

    assert result.tool_result_tokens > 0
    assert "compact_tool_results" in result.actions
    assert "工具结果已压缩" in compacted[1].content


def test_final_prompt_budget_drops_oldest_messages_when_still_over_budget():
    """压缩后仍超预算时，应丢弃旧消息窗口外内容。"""
    budget = FinalPromptBudget(max_tokens=20, tool_result_limit=20)
    messages = [HumanMessage(content=f"历史消息{i}" * 20) for i in range(8)]

    compacted, result = budget.apply("system prompt" * 20, messages)

    assert len(compacted) == 4
    assert "drop_oldest_messages" in result.actions
    assert result.over_budget is True
