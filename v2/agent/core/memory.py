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
    """Load conversation message history."""
    _ensure_dirs()
    f = _conv_file(conversation_id)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_messages(conversation_id: str, messages: list[dict[str, Any]]) -> None:
    """Persist conversation messages (truncated to last N)."""
    _ensure_dirs()
    trimmed = messages[-MAX_SHORT_TERM_MESSAGES:]
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


def save_long_term(conversation_id: str, facts: dict[str, Any]) -> None:
    """Upsert long-term facts for a conversation."""
    _ensure_dirs()
    with _LOCK:
        if _MEMORY_FILE.exists():
            try:
                all_mem = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                all_mem = {}
        else:
            all_mem = {}
        all_mem[conversation_id] = facts
        _MEMORY_FILE.write_text(
            json.dumps(all_mem, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def snapshot(conversation_id: str) -> dict[str, Any]:
    """Combined short-term + long-term snapshot for prompt building."""
    return {
        "conversation_id": conversation_id,
        "messages": load_messages(conversation_id),
        "long_term": load_long_term(conversation_id),
    }


def record_turn(
    conversation_id: str,
    user_message: dict[str, Any],
    assistant_messages: list[dict[str, Any]],
    extracted_facts: dict[str, Any] | None = None,
) -> None:
    """After a turn finishes, persist messages + optionally update long-term.

    assistant_messages may include tool_calls + tool results + final answer;
    the caller decides what to keep (we just append all).
    """
    existing = load_messages(conversation_id)
    existing.append(user_message)
    existing.extend(assistant_messages)
    save_messages(conversation_id, existing)

    if extracted_facts:
        lt = load_long_term(conversation_id)
        lt.update(extracted_facts)
        save_long_term(conversation_id, lt)


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
