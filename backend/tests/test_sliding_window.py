"""Sliding Window 消息压缩单元测试。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.runtime.messages import sliding_window_compact


def _make_messages(rounds: int) -> list:
    """构建 N 轮对话消息列表。每轮 = Human + AI(tool_call) + Tool(result) + AI(reply)。"""
    messages = []
    for i in range(rounds):
        messages.append(HumanMessage(content=f"第{i + 1}轮问题"))
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": f"tool_{i}",
                        "args": {},
                        "id": f"tc{i}",
                    }
                ],
            )
        )
        content = f"工具返回结果第{i + 1}轮，包含很长的数据内容" * 10
        messages.append(ToolMessage(content=content, tool_call_id=f"tc{i}"))
        messages.append(AIMessage(content=f"第{i + 1}轮回答"))
    return messages


class TestSlidingWindow:
    def test_short_history_unchanged(self):
        """少于 keep_rounds 的对话不做压缩。"""
        msgs = _make_messages(3)
        result = sliding_window_compact(msgs, keep_rounds=5)
        assert len(result) == len(msgs)

    def test_long_history_compressed(self):
        """超过 keep_rounds 的对话压缩旧消息。"""
        msgs = _make_messages(8)
        result = sliding_window_compact(msgs, keep_rounds=5)
        assert len(result) == len(msgs)
        old_tool_msgs = [m for m in result[:8] if isinstance(m, ToolMessage)]
        for m in old_tool_msgs:
            assert "[工具结果已压缩]" in m.content
            assert "tool: tool_" in m.content
            assert "ref: tool_call_id=tc" in m.content

    def test_old_tool_results_use_tool_call_names_from_ai_messages(self):
        """旧工具结果压缩时应从 AIMessage.tool_calls 解析工具名。"""
        msgs = _make_messages(8)
        result = sliding_window_compact(msgs, keep_rounds=5)

        assert "[工具结果已压缩]" in result[2].content
        assert "tool: tool_0" in result[2].content
        assert "status: " in result[2].content
        assert "summary: " in result[2].content
        assert "ref: tool_call_id=tc0" in result[2].content
        assert result[2].name == "tool_0"
        assert result[2].status == "success"

    def test_recent_rounds_preserved(self):
        """最近 keep_rounds 轮完整保留。"""
        msgs = _make_messages(8)
        result = sliding_window_compact(msgs, keep_rounds=5)
        recent_tool_msgs = [m for m in result[-20:] if isinstance(m, ToolMessage)]
        for m in recent_tool_msgs:
            assert "很长的数据内容" in m.content
            assert "[工具结果已压缩]" not in m.content

    def test_empty_messages(self):
        result = sliding_window_compact([], keep_rounds=5)
        assert result == []

    def test_human_messages_never_compressed(self):
        """HumanMessage 永远不压缩。"""
        msgs = _make_messages(8)
        result = sliding_window_compact(msgs, keep_rounds=5)
        for m in result:
            if isinstance(m, HumanMessage):
                assert len(m.content) > 0
                assert not m.content.startswith("[历史]")
