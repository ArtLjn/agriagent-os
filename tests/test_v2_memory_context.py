"""会话上下文只保留已完成的用户-助手对。"""

from agent.core import context, memory, react
from agent.core.turn import Turn


def test_load_messages_discards_tool_trace_and_unanswered_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(memory, "_CONV_DIR", tmp_path)
    conversation_id = "legacy"
    memory.save_messages(
        conversation_id,
        [
            {"role": "user", "content": "已经回答的问题"},
            {"role": "assistant", "content": "这是已完成答复"},
            {"role": "user", "content": "旧的未完成问题"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call-1"}]},
            {"role": "tool", "content": '{"location":"虎丘区"}'},
            {"role": "user", "content": "另一个旧的未完成问题"},
        ],
    )

    assert memory.load_messages(conversation_id) == [
        {"role": "user", "content": "已经回答的问题"},
        {"role": "assistant", "content": "这是已完成答复"},
    ]


def test_persist_memory_adds_final_answer_and_excludes_tool_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(memory, "_CONV_DIR", tmp_path)
    turn = Turn(conversation_id="current", user_input="查询天气")
    turn.messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "查询天气"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call-1"}]},
        {"role": "tool", "content": '{"weather":"小雨"}'},
    ]
    turn.final_answer = "虎丘区今天小雨。"

    react._persist_memory(turn)

    assert memory.load_messages("current") == [
        {"role": "user", "content": "查询天气"},
        {"role": "assistant", "content": "[上轮工具调用: →weather=小雨]\n\n虎丘区今天小雨。"},
    ]


def test_context_keeps_current_request_as_only_user_message() -> None:
    messages = context.build_initial_messages(
        "查询天气如何",
        {
            "messages": [
                {"role": "user", "content": "现在几点了"},
                {"role": "assistant", "content": "现在是下午三点。"},
            ]
        },
    )

    user_messages = [message for message in messages if message["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"].startswith("查询天气如何")
    assert "[当前时间:" in user_messages[0]["content"]
    assert "现在几点了" in messages[-2]["content"]
    assert "不得重复回答" in messages[-2]["content"]
