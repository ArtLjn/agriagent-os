"""Trace 调试器 agri_backend_v2 消息召回与结果判定测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from agent.infra.trace.context import clear_trace


def _load_debugger():
    path = (
        Path(__file__).resolve().parents[2]
        / ".codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py"
    )
    spec = importlib.util.spec_from_file_location("trace_chain_debugger", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v2_message_dedup_keeps_user_and_assistant_same_trace() -> None:
    debugger = _load_debugger()
    items = [
        {
            "message_id": "message-user",
            "trace_id": "trace-1",
            "role": "user",
            "content": "查询天气",
        },
        {
            "message_id": "message-assistant",
            "trace_id": "trace-1",
            "role": "assistant",
            "content": "今天晴天",
        },
    ]

    assert [item["role"] for item in debugger.unique_v2_items(items)] == [
        "user",
        "assistant",
    ]
    clear_trace()


def test_business_outcome_uses_assistant_message_as_persistence_evidence() -> None:
    debugger = _load_debugger()
    message = debugger.MessageItem(
        source="agri_backend_v2-mongo",
        storage_id="message-assistant",
        role="assistant",
        content="今天晴天",
        created_at=None,
        turn_id="turn-1",
        session_id="conversation-1",
        farm_id=1,
        meta=None,
        event_file=None,
        event_seq_range=None,
    )

    result = debugger.build_business_outcome([], [], [], [], [message])

    assert result["reply_persisted"] is True
    assert result["reply_persistence_evidence"] == "confirmed"
