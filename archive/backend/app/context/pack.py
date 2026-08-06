"""ContextPack：稳定的会话上下文组装入口。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.context.core.models import ContextBlock, estimate_tokens
from app.domains.conversation.models import Conversation
from app.infra.repository_runtime import (
    get_conversation_message_repository,
    resolve_maybe_awaitable,
)
from app.shared.compatibility import UTC

CONTEXT_CURSOR_KEY = "context_cursor"


@dataclass(frozen=True, slots=True)
class MessageSnapshot:
    """进入 ContextPack 的对话消息快照。"""

    message_id: int | None
    role: str
    content: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConversationSummaryBlock:
    """会话 running summary 及其覆盖边界。"""

    content: str
    version: int
    summarized_until_message_id: int | None
    summarized_until_created_at: datetime | None


@dataclass(frozen=True, slots=True)
class ContextPackDiagnostics:
    """ContextPack 选择诊断信息。"""

    recent_message_ids: list[int]
    summary_version: int | None = None
    summary_hash: str | None = None
    token_estimate: int = 0
    selected_blocks: list[str] = field(default_factory=list)
    compressed_blocks: list[str] = field(default_factory=list)
    dropped_blocks: list[str] = field(default_factory=list)
    compaction_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ContextPack:
    """最终给 Agent Runtime 或 ContextBuilder 消费的会话上下文包。"""

    conversation_id: int | None
    session_id: str | None
    farm_id: int
    user_id: str | None
    summary: ConversationSummaryBlock | None
    recent_messages: list[MessageSnapshot]
    diagnostics: ContextPackDiagnostics

    def to_context_blocks(self) -> list[ContextBlock]:
        """转换为兼容 ContextBuilder 的 block 列表。"""
        blocks: list[ContextBlock] = []
        if self.summary is not None:
            blocks.append(
                ContextBlock(
                    key="conversation_summary",
                    source="context_pack.conversation",
                    purpose="会话摘要",
                    content=self.summary.content,
                    priority=65,
                    compressible=True,
                    metadata={
                        "layer": "working",
                        "cache_scope": "session",
                        "summary_version": self.summary.version,
                        "summarized_until_message_id": (
                            self.summary.summarized_until_message_id
                        ),
                    },
                )
            )
        if self.recent_messages:
            blocks.append(
                ContextBlock(
                    key="recent_messages",
                    source="context_pack.conversation",
                    purpose="最近对话",
                    content=_format_recent_messages(self.recent_messages),
                    priority=70,
                    compressible=True,
                    min_tokens=48,
                    metadata={
                        "layer": "working",
                        "cache_scope": "session",
                        "message_ids": self.diagnostics.recent_message_ids,
                    },
                )
            )
        return blocks


class ContextPackService:
    """从持久化会话事实源构建 ContextPack。"""

    def __init__(
        self,
        *,
        recent_message_limit: int = 8,
        max_recent_without_summary: int = 12,
    ) -> None:
        self.recent_message_limit = recent_message_limit
        self.max_recent_without_summary = max_recent_without_summary

    async def build(
        self,
        *,
        db,
        farm_id: int,
        session_id: str | None,
        user_id: str | None = None,
    ) -> ContextPack:
        conversation = _load_conversation(
            db=db,
            farm_id=farm_id,
            session_id=session_id,
        )
        if conversation is None:
            return _empty_pack(farm_id=farm_id, session_id=session_id, user_id=user_id)

        cursor = _summary_cursor(conversation)
        messages = await _load_messages(db=db, farm_id=farm_id, session_id=session_id)
        summary = _build_summary_block(conversation, cursor)
        recent_messages = _select_recent_messages(
            messages=messages,
            cursor_message_id=_cursor_message_id(cursor),
            has_summary=summary is not None,
            recent_message_limit=self.recent_message_limit,
            max_recent_without_summary=self.max_recent_without_summary,
        )
        snapshots = [_message_snapshot(message) for message in recent_messages]
        diagnostics = _build_diagnostics(
            summary=summary,
            summary_hash=_summary_hash(cursor),
            recent_messages=snapshots,
        )
        return ContextPack(
            conversation_id=conversation.id,
            session_id=conversation.session_id,
            farm_id=conversation.farm_id,
            user_id=conversation.user_id or user_id,
            summary=summary,
            recent_messages=snapshots,
            diagnostics=diagnostics,
        )


def _load_conversation(
    *,
    db,
    farm_id: int,
    session_id: str | None,
) -> Conversation | None:
    if not session_id:
        return None
    return (
        db.query(Conversation)
        .filter(Conversation.farm_id == farm_id, Conversation.session_id == session_id)
        .first()
    )


async def _load_messages(*, db, farm_id: int, session_id: str | None) -> list[Any]:
    if not session_id:
        return []
    return await resolve_maybe_awaitable(
        get_conversation_message_repository(db).list_by_session(
            farm_id=farm_id,
            session_id=session_id,
        )
    )


def _summary_cursor(conversation: Conversation) -> dict[str, Any]:
    meta_json = conversation.meta_json or {}
    cursor = meta_json.get(CONTEXT_CURSOR_KEY)
    return dict(cursor) if isinstance(cursor, dict) else {}


def _cursor_message_id(cursor: dict[str, Any]) -> int | None:
    value = cursor.get("summarized_until_message_id")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _summary_hash(cursor: dict[str, Any]) -> str | None:
    value = cursor.get("summary_hash")
    return str(value) if value is not None else None


def _build_summary_block(
    conversation: Conversation,
    cursor: dict[str, Any],
) -> ConversationSummaryBlock | None:
    if not conversation.summary:
        return None
    return ConversationSummaryBlock(
        content=conversation.summary,
        version=int(cursor.get("summary_version") or 0),
        summarized_until_message_id=_cursor_message_id(cursor),
        summarized_until_created_at=_parse_datetime(
            cursor.get("summarized_until_created_at")
        ),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_aware_utc(value)
    try:
        return _as_aware_utc(datetime.fromisoformat(str(value)))
    except ValueError:
        return None


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _select_recent_messages(
    *,
    messages: list[Any],
    cursor_message_id: int | None,
    has_summary: bool,
    recent_message_limit: int,
    max_recent_without_summary: int,
) -> list[Any]:
    if not has_summary:
        return messages[-max_recent_without_summary:]
    if cursor_message_id is None:
        return messages[-recent_message_limit:]
    after_cursor = [
        message
        for message in messages
        if _message_id(message) is None or _message_id(message) > cursor_message_id
    ]
    return after_cursor[-recent_message_limit:]


def _message_snapshot(message: Any) -> MessageSnapshot:
    return MessageSnapshot(
        message_id=_message_id(message),
        role=str(getattr(message, "role", "")),
        content=str(getattr(message, "content", "")),
        created_at=_parse_datetime(getattr(message, "created_at", None)),
        metadata=dict(getattr(message, "meta_json", None) or {}),
    )


def _message_id(message: Any) -> int | None:
    value = getattr(message, "id", None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_diagnostics(
    *,
    summary: ConversationSummaryBlock | None,
    summary_hash: str | None,
    recent_messages: list[MessageSnapshot],
) -> ContextPackDiagnostics:
    selected_blocks = []
    token_estimate = 0
    if summary is not None:
        selected_blocks.append("conversation_summary")
        token_estimate += estimate_tokens(summary.content)
    if recent_messages:
        selected_blocks.append("recent_messages")
        token_estimate += estimate_tokens(_format_recent_messages(recent_messages))
    return ContextPackDiagnostics(
        recent_message_ids=[
            message.message_id
            for message in recent_messages
            if message.message_id is not None
        ],
        summary_version=summary.version if summary is not None else None,
        summary_hash=summary_hash,
        token_estimate=token_estimate,
        selected_blocks=selected_blocks,
    )


def _format_recent_messages(messages: list[MessageSnapshot]) -> str:
    return "\n".join(f"{message.role}: {message.content}" for message in messages)


def _empty_pack(
    *,
    farm_id: int,
    session_id: str | None,
    user_id: str | None,
) -> ContextPack:
    return ContextPack(
        conversation_id=None,
        session_id=session_id,
        farm_id=farm_id,
        user_id=user_id,
        summary=None,
        recent_messages=[],
        diagnostics=ContextPackDiagnostics(recent_message_ids=[]),
    )


__all__ = [
    "ContextPack",
    "ContextPackDiagnostics",
    "ContextPackService",
    "ConversationSummaryBlock",
    "MessageSnapshot",
]
