"""用户显式长期记忆写入入口。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.memory.long_term import MemoryRecordStore, MemoryRecordType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExplicitMemoryTurn:
    """显式长期记忆写入所需的轮次快照。"""

    farm_id: int
    user_id: str | None
    session_id: str | None
    user_input: str
    assistant_reply: str
    pending_action: object | None = None
    pending_plan: object | None = None
    pending_decision_handled: bool = False


async def record_explicit_memory_after_turn(
    db: Session,
    turn: ExplicitMemoryTurn,
) -> None:
    """用户明确要求记住时写入 confirmed 长期记忆，失败不影响回复。"""
    extraction = _extract_explicit_memory(turn)
    if extraction is None:
        return

    memory_type, content = extraction
    try:
        MemoryRecordStore(db).create_confirmed(
            farm_id=turn.farm_id,
            user_id=turn.user_id or "",
            memory_type=memory_type,
            content=content,
        )
        logger.info(
            "显式长期记忆写入成功",
            extra={
                "code": "EXPLICIT_MEMORY_RECORDED",
                "farm_id": turn.farm_id,
                "user_id": turn.user_id,
                "session_id": turn.session_id,
                "memory_type": memory_type.value,
            },
        )
    except Exception:
        logger.exception(
            "显式长期记忆写入失败",
            extra={
                "code": "EXPLICIT_MEMORY_RECORD_FAILED",
                "farm_id": turn.farm_id,
                "user_id": turn.user_id,
                "session_id": turn.session_id,
            },
        )
        try:
            db.rollback()
        except Exception:
            return


def _extract_explicit_memory(
    turn: ExplicitMemoryTurn,
) -> tuple[MemoryRecordType, str] | None:
    if not _can_consider_explicit_memory(turn):
        return None
    content = _explicit_memory_content(turn.user_input)
    if not content:
        return None
    return _classify_explicit_memory(content), content


def _can_consider_explicit_memory(turn: ExplicitMemoryTurn) -> bool:
    if not turn.user_id:
        return False
    if turn.pending_action is not None or turn.pending_plan is not None:
        return False
    if turn.pending_decision_handled:
        return False
    text = _compact_memory_text(turn.user_input)
    if not text:
        return False
    return not _is_explicit_memory_cancel(text)


def _explicit_memory_content(text: str) -> str:
    compacted = _compact_memory_text(text)
    patterns = (
        r"^(?:请你|帮我|麻烦你)?记住(?:我)?(?P<content>.+)$",
        r"^(?:请你|帮我|麻烦你)?记一下(?P<content>.+)$",
        r"^(?:请你|帮我|麻烦你)?帮我记一下(?P<content>.+)$",
        r"^(?P<content>以后默认.+)$",
        r"^(?P<content>以后都这样)$",
        r"^(?P<content>以后.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, compacted)
        if match:
            return _clean_memory_content(match.group("content"))
    return ""


def _clean_memory_content(text: str) -> str:
    cleaned = _compact_memory_text(text)
    cleaned = re.sub(r"^(这个|这点|一下|：|:)", "", cleaned)
    cleaned = cleaned.strip(" ：:，,。；;！!？? ")
    if _is_confirmation_fragment(cleaned):
        return ""
    return cleaned[:500]


def _is_confirmation_fragment(text: str) -> bool:
    return text in {"了吗", "吗", "了没", "没", "没有", "记住了吗"}


def _classify_explicit_memory(content: str) -> MemoryRecordType:
    if any(keyword in content for keyword in ("以后", "默认", "偏好", "习惯", "用亩")):
        return MemoryRecordType.PREFERENCE
    if any(keyword in content for keyword in ("就是", "别名", "叫", "昵称")):
        return MemoryRecordType.ALIAS
    return MemoryRecordType.FACT


def _is_explicit_memory_cancel(text: str) -> bool:
    return any(
        keyword in text
        for keyword in (
            "不要记",
            "别记",
            "不用记",
            "取消刚才记忆",
            "取消刚才的记忆",
            "别保存",
        )
    )


def _compact_memory_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


__all__ = ["ExplicitMemoryTurn", "record_explicit_memory_after_turn"]
