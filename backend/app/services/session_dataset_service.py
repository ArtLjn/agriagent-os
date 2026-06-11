"""从 Agent 事件日志构建调优/评测样本。"""

from collections import defaultdict
from typing import Any


def _events_by_turn(events: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        turn_id = event.get("turn_id")
        if turn_id is not None:
            grouped[int(turn_id)].append(event)
    return grouped


def build_sft_samples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建回复调优 SFT 样本。"""
    samples: list[dict[str, Any]] = []
    for turn_id, rows in sorted(_events_by_turn(events).items()):
        user = next((row for row in rows if row.get("event_type") == "message.user"), None)
        assistant = next(
            (row for row in rows if row.get("event_type") == "message.assistant"),
            None,
        )
        if user is None or assistant is None:
            continue
        tool_results = [
            {
                "tool_name": row.get("payload", {}).get("tool_name"),
                "result": row.get("payload", {}).get("result"),
            }
            for row in rows
            if row.get("event_type") == "tool.call.finished"
        ]
        samples.append(
            {
                "turn_id": turn_id,
                "instruction": user.get("payload", {}).get("content", ""),
                "tool_results": tool_results,
                "response": assistant.get("payload", {}).get("content", ""),
                "source": "agent_event_log",
            }
        )
    return samples


def build_tool_selection_samples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建工具选择训练/评测样本。"""
    samples: list[dict[str, Any]] = []
    for turn_id, rows in sorted(_events_by_turn(events).items()):
        user = next((row for row in rows if row.get("event_type") == "message.user"), None)
        router = next(
            (row for row in rows if row.get("event_type") == "router.decision"),
            None,
        )
        if user is None or router is None:
            continue
        actual_tools = [
            row.get("payload", {}).get("tool_name")
            for row in rows
            if row.get("event_type") == "tool.call.finished"
            and row.get("payload", {}).get("tool_name")
        ]
        payload = router.get("payload", {})
        samples.append(
            {
                "turn_id": turn_id,
                "input": user.get("payload", {}).get("content", ""),
                "selected_tools": payload.get("selected_tools") or [],
                "rejected_tools": payload.get("rejected_tools") or [],
                "actual_tools": actual_tools,
                "fallback": bool(payload.get("fallback")),
                "source": "agent_event_log",
            }
        )
    return samples
