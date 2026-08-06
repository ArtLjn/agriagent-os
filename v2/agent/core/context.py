"""LLM context assembly.

Builds the system prompt, message list, and OpenAI tool schema for a Turn.
Pure functions; no side effects on Turn.

Inputs:
  - turn.memory_snapshot (from agent.memory.snapshot)
  - turn.business_tools (from BusinessClient.list_tools())

Outputs feed into agent.llm.chat(messages, tools).
"""
from __future__ import annotations

import json
from typing import Any


from agent.prompts import render_system_prompt


def _format_memory(memory_snapshot: dict[str, Any]) -> str:
    """Render long-term facts as a readable block."""
    lt = memory_snapshot.get("long_term") or {}
    if not lt:
        return "（暂无长期记忆）"
    lines = []
    for k, v in lt.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def build_system_prompt(memory_snapshot: dict[str, Any]) -> str:
    """Compose system prompt with memory injected (loaded from prompts/system.md)."""
    return render_system_prompt(
        memory_block=_format_memory(memory_snapshot),
    )


def build_initial_messages(
    user_input: str,
    memory_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the messages list at turn start: system + history + new user msg."""
    messages: list[dict[str, Any]] = []
    messages.append({"role": "system", "content": build_system_prompt(memory_snapshot)})
    # Append prior conversation messages (already includes old user/assistant).
    for m in memory_snapshot.get("messages", []):
        # Skip stale system prompts from prior turns.
        if m.get("role") == "system":
            continue
        messages.append(m)
    messages.append({"role": "user", "content": user_input})
    return messages


def mcp_tools_to_openai(business_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool descriptors to OpenAI tools schema.

    MCP gives: {name, description, input_schema}
    OpenAI wants: {"type": "function", "function": {name, description, parameters}}
    """
    out: list[dict[str, Any]] = []
    for t in business_tools:
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
            },
        })
    return out


def assistant_message_with_tool_calls(
    content: str,
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build assistant message matching OpenAI format with tool_calls."""
    if not tool_calls:
        return {"role": "assistant", "content": content}
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                },
            }
            for tc in tool_calls
        ],
    }


def tool_result_message(tool_call_id: str, name: str, result: Any) -> dict[str, Any]:
    """Build the 'tool' role message feeding back tool results to LLM."""
    if isinstance(result, (dict, list)):
        content = json.dumps(result, ensure_ascii=False)
    else:
        content = str(result)
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": content,
    }
