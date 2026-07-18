"""Agent append-only JSONL 事件日志。"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.shared.compatibility import UTC

logger = logging.getLogger(__name__)
_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9_.=-]+")
_SEQ_CACHE: dict[str, int] = {}


@dataclass(frozen=True)
class AgentEvent:
    """Agent 事件稳定外壳。"""

    event_id: str
    event_type: str
    schema_version: int
    created_at: str
    farm_id: int
    user_id: str | None
    session_id: str
    turn_id: int | None
    request_id: str | None
    seq: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "farm_id": self.farm_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "request_id": self.request_id,
            "seq": self.seq,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class AgentEventWriteResult:
    """事件写入结果。"""

    status: str
    event_file: str | None
    seq: int | None
    error_message: str | None = None


class AgentEventWriter:
    """按日期、farm、session 分区追加 JSONL 事件。"""

    def __init__(self, base_dir: str | Path = "data/agent-events") -> None:
        self.base_dir = Path(base_dir)

    def write(
        self,
        *,
        event_type: str,
        farm_id: int,
        user_id: str | None,
        session_id: str,
        turn_id: int | None,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> AgentEventWriteResult:
        try:
            path = self.event_file_for(farm_id=farm_id, session_id=session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            seq = _next_seq(path)
            event = AgentEvent(
                event_id=uuid.uuid4().hex,
                event_type=event_type,
                schema_version=1,
                created_at=datetime.now(UTC).isoformat(),
                farm_id=farm_id,
                user_id=user_id,
                session_id=session_id,
                turn_id=turn_id,
                request_id=request_id,
                seq=seq,
                payload=payload,
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event.to_dict(), ensure_ascii=False, default=str)
                )
                handle.write("\n")
            return AgentEventWriteResult(
                status="success", event_file=str(path), seq=seq
            )
        except Exception as exc:
            logger.warning(
                "Agent event 写入失败 | farm_id=%s session_id=%s event_type=%s error=%s",
                farm_id,
                session_id,
                event_type,
                exc,
            )
            return AgentEventWriteResult(
                status="failed",
                event_file=None,
                seq=None,
                error_message=str(exc),
            )

    def event_file_for(self, *, farm_id: int, session_id: str) -> Path:
        today = datetime.now(UTC).date().isoformat()
        safe_session = _safe_segment(session_id)
        return (
            self.base_dir
            / f"dt={today}"
            / f"farm_id={farm_id}"
            / f"session_id={safe_session}"
            / "events.jsonl"
        )


def _safe_segment(value: str) -> str:
    return _SAFE_SEGMENT_RE.sub("_", value)[:120]


def _next_seq(path: Path) -> int:
    cache_key = str(path.resolve())
    if cache_key in _SEQ_CACHE:
        _SEQ_CACHE[cache_key] += 1
        return _SEQ_CACHE[cache_key]

    if not path.exists():
        _SEQ_CACHE[cache_key] = 1
        return 1
    last_seq = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                last_seq = int(json.loads(line).get("seq") or last_seq)
            except json.JSONDecodeError:
                continue
    next_seq = last_seq + 1
    _SEQ_CACHE[cache_key] = next_seq
    return next_seq


def read_event_segment(
    event_file: str | Path,
    seq_start: int | None,
    seq_end: int | None,
) -> list[dict[str, Any]]:
    """读取指定事件文件的 seq 范围。"""
    path = Path(event_file)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            seq = int(row.get("seq") or 0)
            if seq_start is not None and seq < seq_start:
                continue
            if seq_end is not None and seq > seq_end:
                continue
            rows.append(row)
    return rows
