"""最终 prompt 预算检查测试。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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
    """压缩后仍超预算时，应摘要旧内容并保留最近消息。"""
    budget = FinalPromptBudget(max_tokens=20, tool_result_limit=20)
    messages = [HumanMessage(content=f"历史消息{i}" * 20) for i in range(8)]

    compacted, result = budget.apply("system prompt" * 20, messages)

    assert len(compacted) == 7
    assert "summarize_old_messages" in result.actions
    assert "早期对话摘要" in compacted[0].content
    assert result.over_budget is True


def test_final_prompt_budget_summarizes_old_messages_before_recent_window():
    """超预算时应保留早期会话摘要，而不是直接丢掉所有旧轮次。"""
    budget = FinalPromptBudget(max_tokens=30, tool_result_limit=20, recent_messages=2)
    messages = [
        HumanMessage(content="你的功能"),
        AIMessage(content="我是芽芽，可以查数据、记账、管理种植。"),
        HumanMessage(content="我的茬口"),
        AIMessage(content="当前活跃茬口有夏季水稻、夏季苹果、夏季玉米。"),
        HumanMessage(content="我想种橘子"),
        AIMessage(content="需要我帮你创建一个橘子茬口吗？确认后执行。"),
    ]

    compacted, result = budget.apply("system prompt" * 20, messages)

    assert "summarize_old_messages" in result.actions
    assert len(compacted) == 3
    assert isinstance(compacted[0], AIMessage)
    assert "早期对话摘要" in compacted[0].content
    assert "你的功能" in compacted[0].content
    assert "夏季水稻" in compacted[0].content
    assert compacted[-2].content == "我想种橘子"
