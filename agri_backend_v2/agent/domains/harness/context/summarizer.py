"""基于 Mongo Conversation State 的 Short Memory rolling summary。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from agent.domains.harness.memory import service as memory
from agent.platforms.llm.client import chat

logger = logging.getLogger(__name__)

KEEP_RECENT_TURNS = 6
MIN_OLD_TURNS_TO_SUMMARIZE = 2
SUMMARY_HISTORY_LIMIT = 2000

SUMMARY_PROMPT = """把以下多轮对话总结成 200 字以内的关键信息，便于后续 Agent 参考。
要点：
1. 用户的意图、偏好、已知信息和实体 ID
2. 已经执行过哪些工具，结果如何
3. 待办、未解决的问题和当前状态

只输出总结正文，不要任何前缀和解释。

对话：
__DIALOG__
"""


@dataclass(frozen=True)
class SummaryResult:
    """摘要任务结果，明确区分成功、跳过、冲突和不可用。"""

    summary: str | None
    status: str
    source_status: str
    summary_revision: int = 0
    conversation_revision: int = 0
    source_from_message_id: str | None = None
    source_to_message_id: str | None = None
    content_hash: str | None = None
    error_code: str | None = None


def _summary_text(turns: list[list[dict[str, Any]]]) -> str:
    prompt = SUMMARY_PROMPT.replace(
        "__DIALOG__", json.dumps(turns, ensure_ascii=False, indent=2)
    )
    result = chat(
        [
            {"role": "system", "content": "你是对话总结助手。"},
            {"role": "user", "content": prompt},
        ]
    )
    text = result.get("content", "") if isinstance(result, dict) else str(result)
    return text.strip()


def _message_id(message: dict[str, Any]) -> str | None:
    value = message.get("message_id") or message.get("_id") or message.get("turn_id")
    return str(value) if value is not None else None


def _summary_key(
    conversation_id: str,
    source_revision: int,
    source_from: str | None,
    source_to: str | None,
) -> str:
    raw = "|".join(
        [conversation_id, str(source_revision), source_from or "", source_to or ""]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"summary:{digest}"


async def maybe_summarize_async(
    conversation_id: str,
    force: bool = False,
    *,
    user_id: str,
    farm_id: int,
    source_conversation_revision: int,
) -> SummaryResult:
    """基于不可变 Session revision 生成并 CAS 提交摘要。"""
    from agent.config import settings
    from agent.platforms.persistence.mongo import chat_store

    if not settings.mongodb.enabled:
        return SummaryResult(
            None, "unavailable", "unavailable", error_code="mongo_disabled"
        )

    state = await chat_store.get_conversation_state(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
    )
    if state and state.get("status") == "unavailable":
        return SummaryResult(
            None,
            "unavailable",
            "unavailable",
            error_code=state.get("code"),
        )
    current_revision = int((state or {}).get("conversation_revision", 0) or 0)
    if current_revision != source_conversation_revision:
        return SummaryResult(
            None,
            "conflict",
            "mongo",
            conversation_revision=current_revision,
            error_code="summary_source_revision_conflict",
        )

    history = await chat_store.load_recent(
        conversation_id,
        limit=SUMMARY_HISTORY_LIMIT,
        user_id=user_id,
        farm_id=farm_id,
    )
    turns = memory.complete_turns(history)
    if len(turns) < KEEP_RECENT_TURNS + MIN_OLD_TURNS_TO_SUMMARIZE:
        return SummaryResult(
            None,
            "skipped",
            "mongo",
            conversation_revision=current_revision,
        )
    if not force and len(turns) < KEEP_RECENT_TURNS + MIN_OLD_TURNS_TO_SUMMARIZE + 2:
        return SummaryResult(
            None,
            "skipped",
            "mongo",
            conversation_revision=current_revision,
        )

    old_turns = turns[:-KEEP_RECENT_TURNS]
    source_from = _message_id(old_turns[0][0])
    source_to = _message_id(old_turns[-1][-1])
    summary_key = _summary_key(
        conversation_id, source_conversation_revision, source_from, source_to
    )
    claim = await chat_store.claim_summary_generation(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
        source_conversation_revision=source_conversation_revision,
        summary_key=summary_key,
    )
    if claim.get("status") == "idempotent" and claim.get("summary_status") == "ready":
        return SummaryResult(
            claim.get("summary"),
            "idempotent",
            "mongo",
            int(claim.get("summary_revision", 0) or 0),
            int(claim.get("conversation_revision", 0) or 0),
            source_from,
            source_to,
            claim.get("summary_content_hash"),
        )
    if not claim.get("ok"):
        return SummaryResult(
            None,
            claim.get("status", "conflict"),
            claim.get("source_status", "mongo"),
            conversation_revision=int(claim.get("actual_revision", 0) or 0),
            error_code=claim.get("code"),
        )

    claim_revision = int(claim.get("conversation_revision", 0) or 0)
    try:
        summary = await asyncio.to_thread(_summary_text, old_turns)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "summary generation failed conversation=%s revision=%s error=%s",
            conversation_id,
            source_conversation_revision,
            exc,
        )
        return await _save_failed(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            claim_revision=claim_revision,
            source_revision=source_conversation_revision,
            summary_key=summary_key,
            source_from=source_from,
            source_to=source_to,
            error_code="summary_generation_failed",
        )

    if not summary:
        return await _save_failed(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            claim_revision=claim_revision,
            source_revision=source_conversation_revision,
            summary_key=summary_key,
            source_from=source_from,
            source_to=source_to,
            error_code="summary_empty",
        )

    now = datetime.now(timezone.utc)
    content_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    saved = await chat_store.save_summary_result(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
        expected_revision=claim_revision,
        source_conversation_revision=source_conversation_revision,
        summary_key=summary_key,
        summary=summary,
        status="ready",
        source_from_message_id=source_from,
        source_to_message_id=source_to,
        content_hash=content_hash,
        generated_by="agent.domains.harness.context.summarizer",
        created_at=now.isoformat(),
        expires_at=(
            now + timedelta(seconds=settings.context.summary_ttl_seconds)
        ).isoformat(),
    )
    if not saved.get("ok"):
        return SummaryResult(
            None,
            saved.get("status", "conflict"),
            saved.get("source_status", "mongo"),
            conversation_revision=int(saved.get("actual_revision", 0) or 0),
            error_code=saved.get("code"),
        )
    return SummaryResult(
        summary,
        saved.get("status", "ready"),
        saved.get("source_status", "mongo"),
        int(saved.get("summary_revision", 0) or 0),
        int(saved.get("conversation_revision", 0) or 0),
        source_from,
        source_to,
        content_hash,
    )


async def _save_failed(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int,
    claim_revision: int,
    source_revision: int,
    summary_key: str,
    source_from: str | None,
    source_to: str | None,
    error_code: str,
) -> SummaryResult:
    from agent.platforms.persistence.mongo import chat_store

    saved = await chat_store.save_summary_result(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
        expected_revision=claim_revision,
        source_conversation_revision=source_revision,
        summary_key=summary_key,
        status="failed",
        source_from_message_id=source_from,
        source_to_message_id=source_to,
    )
    return SummaryResult(
        None,
        "failed",
        saved.get("source_status", "mongo"),
        conversation_revision=int(saved.get("conversation_revision", 0) or 0),
        error_code=error_code,
    )


def build_summary_message(summary: str) -> dict[str, Any]:
    """兼容旧测试的构造器；生产 Context 不调用此函数。"""
    return {"role": "assistant", "content": f"[CONVERSATION_SUMMARY] {summary}"}
