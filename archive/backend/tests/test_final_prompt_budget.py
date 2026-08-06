"""最终 prompt 预算检查测试。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.runtime.final_prompt_budget import FinalPromptBudget


def test_final_prompt_budget_compacts_large_tool_results():
    """最终预算应覆盖 system、消息和工具结果，并压缩超大工具输出。"""
    budget = FinalPromptBudget(max_tokens=80, tool_result_limit=20)
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "get_farm_status",
                    "args": {"farm_id": 1},
                }
            ],
        ),
        ToolMessage(content="明细" * 300, tool_call_id="tc1"),
    ]

    compacted, result = budget.apply("system prompt" * 20, messages)

    assert result.tool_result_tokens > 0
    assert "compact_tool_results" in result.actions
    assert result.message_count_before == len(messages)
    assert result.message_count_after == len(compacted)
    assert result.tool_result_tokens_before >= result.tool_result_tokens_after
    assert result.compression_events
    assert "工具结果已压缩" in compacted[1].content
    assert "tool: get_farm_status" in compacted[1].content
    assert "ref: tool_call_id=tc1" in compacted[1].content
    assert compacted[1].name == "get_farm_status"
    assert compacted[1].status == "success"
    assert compacted[1].tool_call_id == "tc1"
    summary = result.summary()
    assert summary["message_count_before"] == len(messages)
    assert summary["tool_result_tokens_before"] >= summary["tool_result_tokens_after"]
    assert summary["compression_events"][0]["key"] == "tc1"


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


def test_final_prompt_budget_summarizes_on_round_boundary_with_tool_metadata():
    """二次摘要应按最近轮次切分，并保留旧工具消息的引用元数据。"""
    budget = FinalPromptBudget(max_tokens=20, tool_result_limit=10, recent_messages=2)
    messages = [
        HumanMessage(content="查农场"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc-old",
                    "name": "get_farm_status",
                    "args": {"farm_id": 1},
                }
            ],
        ),
        ToolMessage(content="历史工具明细" * 80, tool_call_id="tc-old"),
        AIMessage(content="这是旧回复"),
        HumanMessage(content="继续问"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc-recent",
                    "name": "get_cycle",
                    "args": {"farm_id": 1},
                }
            ],
        ),
        ToolMessage(content="最近工具结果" * 2, tool_call_id="tc-recent"),
    ]

    compacted, result = budget.apply("system prompt" * 20, messages)

    assert "summarize_old_messages" in result.actions
    assert compacted[1].content == "继续问"
    assert isinstance(compacted[-1], ToolMessage)
    assert compacted[-1].tool_call_id == "tc-recent"
    assert "tool_call_id=tc-old" in compacted[0].content
    assert "name=get_farm_status" in compacted[0].content
    assert "status=success" in compacted[0].content
