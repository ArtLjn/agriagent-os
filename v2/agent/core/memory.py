"""Conversation memory.

Two layers, both persisted as JSON (no SQL):
  - short_term: per-conversation message log (last N messages)
  - long_term:  per-conversation facts (extracted user preferences,
                key entities, last-mentioned farm)

Each conversation has its own short-term file under data/conversations/.
Long-term is shared in data/memory.json keyed by conversation_id.

Mirrors archive/backend/app/memory/ but stripped to MVP essentials:
no summarizer, no vector store, just JSON.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"
_CONV_DIR = _DATA_DIR / "conversations"
_MEMORY_FILE = _DATA_DIR / "memory.json"
_LOCK = threading.Lock()

# Keep last N messages per conversation to bound context size.
MAX_SHORT_TERM_MESSAGES = 20


def _ensure_dirs() -> None:
    _CONV_DIR.mkdir(parents=True, exist_ok=True)


def _conv_file(conversation_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in conversation_id)
    return _CONV_DIR / f"{safe}.json"


def load_messages(conversation_id: str) -> list[dict[str, Any]]:
    """加载可注入 Prompt 的对话历史，不返回工具调用中间态。"""
    _ensure_dirs()
    f = _conv_file(conversation_id)
    if not f.exists():
        return []
    try:
        return _dialogue_messages(json.loads(f.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return []


def save_messages(conversation_id: str, messages: list[dict[str, Any]]) -> None:
    """持久化用户与最终答复；工具轨迹只属于当前 turn。"""
    _ensure_dirs()
    trimmed = _dialogue_messages(messages)[-MAX_SHORT_TERM_MESSAGES:]
    _conv_file(conversation_id).write_text(
        json.dumps(trimmed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_long_term(conversation_id: str) -> dict[str, Any]:
    """Load long-term facts for a conversation. Empty dict if missing."""
    _ensure_dirs()
    if not _MEMORY_FILE.exists():
        return {}
    try:
        all_mem = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return all_mem.get(conversation_id, {})


def snapshot(conversation_id: str) -> dict[str, Any]:
    """Combined short-term + long-term snapshot for prompt building."""
    return {
        "conversation_id": conversation_id,
        "messages": load_messages(conversation_id),
        "long_term": load_long_term(conversation_id),
    }


def _dialogue_messages(messages: Any) -> list[dict[str, str]]:
    """保留已完成对话 + 工具结果摘要（不保留原始工具数据）。

    工具结果摘要拼接到随后 assistant 回复的前面，让下一 turn 的 LLM
    能看到上一 turn 查过什么、结果是什么，避免重复查询。
    """
    if not isinstance(messages, list):
        return []

    dialogue: list[dict[str, str]] = []
    pending_user: dict[str, str] | None = None
    pending_tool_summaries: list[str] = []

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")

        # 收集工具结果摘要
        if role == "tool":
            summary = _summarize_tool_result(
                message.get("name", ""),
                message.get("content", ""),
            )
            if summary:
                pending_tool_summaries.append(summary)
            continue

        # assistant with tool_calls = 工具调用触发，跳过（摘要由 tool result 提供）
        if role == "assistant" and message.get("tool_calls"):
            continue

        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        if not content.strip():
            continue

        # 如果有待处理的工具摘要，拼接到 assistant 回复前
        if pending_tool_summaries and role == "assistant":
            tool_block = "; ".join(pending_tool_summaries)
            content = f"[上轮工具调用: {tool_block}]\n\n{content}"
            pending_tool_summaries = []

        normalized = {"role": role, "content": content}
        if role == "user":
            # 没有最终答复的旧用户消息不能成为下一轮待办。
            pending_user = normalized
        elif pending_user is not None:
            dialogue.extend([pending_user, normalized])
            pending_user = None
    return dialogue


def _summarize_tool_result(tool_name: str, content: Any) -> str:
    """从工具结果中提取关键信息摘要（≤200 字符）。

    使用数据驱动的规则注册表，按 result 中的 key 匹配提取规则。
    新增工具类型只需在 _LIST_RULES 中加一行，不需要改代码逻辑。
    """
    result = _parse_tool_content(content)
    if not isinstance(result, dict):
        return ""

    # 按规则注册表匹配列表型结果
    for rule in _LIST_RULES:
        items = result.get(rule["key"])
        if isinstance(items, list) and items:
            return _format_list_summary(tool_name, rule, items)

    # wages 查询结果（嵌套 summary.workers 结构）
    workers = result.get("workers")
    if isinstance(workers, list) and workers and "summary" in result:
        parts = [
            f"{w.get('worker_name', '?')}({w.get('total_unpaid', 0)})" for w in workers
        ]
        return f"{tool_name}→{len(workers)}工人工资:{','.join(parts)}"

    # 通用 fallback：输出 key=value（保留写操作返回的关键 ID 和状态）
    return _format_generic_summary(tool_name, result)


def _parse_tool_content(content: Any) -> dict | None:
    """解析工具结果内容为 dict。"""
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None
    elif isinstance(content, dict):
        parsed = content
    else:
        return None
    return parsed if isinstance(parsed, dict) else None


# 列表型结果的摘要规则注册表
# 新增工具类型只需加一行：key=result中的键, label=摘要标签,
# name=实体名称字段, id=实体ID字段, extra=额外提取字段, max=最大条目数
_LIST_RULES: list[dict[str, Any]] = [
    {
        "key": "workers",
        "label": "工人",
        "name": "name",
        "id": "id",
        "extra": ["default_pay_type", "default_unit_price"],
        "max": 10,
    },
    {
        "key": "work_orders",
        "label": "作业单",
        "name": "operation_type",
        "id": "id",
        "extra": [],
        "max": 10,
    },
    {
        "key": "cycles",
        "label": "茬口",
        "name": "name",
        "id": "id",
        "extra": [],
        "max": 10,
    },
    {
        "key": "categories",
        "label": "分类",
        "name": "name",
        "id": None,
        "extra": [],
        "max": 10,
    },
    {
        "key": "records",
        "label": "记录",
        "name": None,
        "id": "id",
        "extra": [],
        "max": 5,
    },
    {
        "key": "entries",
        "label": "明细",
        "name": "operation_type",
        "id": "work_order_id",
        "extra": ["payable_amount", "settlement_status"],
        "max": 5,
    },
    {
        "key": "templates",
        "label": "模板",
        "name": "name",
        "id": "id",
        "extra": [],
        "max": 10,
    },
    {
        "key": "fields",
        "label": "地块",
        "name": "name",
        "id": "id",
        "extra": [],
        "max": 10,
    },
]


def _format_list_summary(tool_name: str, rule: dict[str, Any], items: list[Any]) -> str:
    """按规则格式化列表型结果摘要。"""
    max_items = rule.get("max", 10)
    name_field = rule.get("name")
    id_field = rule.get("id")
    extra_fields = rule.get("extra", [])
    label = rule["label"]

    parts: list[str] = []
    for item in items[:max_items]:
        if not isinstance(item, dict):
            continue
        part = ""
        if name_field and name_field in item:
            part = str(item[name_field])
        if id_field and id_field in item:
            part = f"{part}({item[id_field]})" if part else f"#{item[id_field]}"
        for ef in extra_fields:
            if ef in item and item[ef] is not None:
                part += f",{item[ef]}"
        if part:
            parts.append(part)

    return f"{tool_name}→{len(items)}{label}:{','.join(parts)}"


def _format_generic_summary(tool_name: str, result: dict[str, Any]) -> str:
    """通用 fallback：输出 key=value，保留写操作返回的关键 ID 和状态。"""
    parts: list[str] = []
    for k, v in result.items():
        if isinstance(v, (str, int, float, bool)):
            parts.append(f"{k}={v}")
        elif isinstance(v, list):
            parts.append(f"{k}={len(v)}项")
        elif isinstance(v, dict):
            parts.append(f"{k}=...")
        elif v is None:
            continue
        if len(parts) >= 8:
            break
    return f"{tool_name}→{','.join(parts)}" if parts else ""


def reset_conversation(conversation_id: str) -> None:
    """Wipe a conversation's short-term + long-term memory (for /reset)."""
    f = _conv_file(conversation_id)
    if f.exists():
        f.unlink()
    with _LOCK:
        if not _MEMORY_FILE.exists():
            return
        try:
            all_mem = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if conversation_id in all_mem:
            del all_mem[conversation_id]
            _MEMORY_FILE.write_text(
                json.dumps(all_mem, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
