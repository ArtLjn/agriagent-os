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
    """仅保留可作为下一轮上下文的已完成对话。"""
    if not isinstance(messages, list):
        return []

    dialogue: list[dict[str, str]] = []
    pending_user: dict[str, str] | None = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        if role == "assistant" and message.get("tool_calls"):
            continue
        if not content.strip():
            continue
        normalized = {"role": role, "content": content}
        if role == "user":
            # 没有最终答复的旧用户消息不能成为下一轮待办。
            pending_user = normalized
        elif pending_user is not None:
            dialogue.extend([pending_user, normalized])
            pending_user = None
    return dialogue


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
