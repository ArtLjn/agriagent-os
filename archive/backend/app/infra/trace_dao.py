"""Trace 数据访问对象 — 批量 INSERT + Token 统计累加。"""

import json
import logging
from collections import deque
from datetime import date
from typing import Any

from app.shared.database import SessionLocal
from app.infra.repository_runtime import get_trace_repository, resolve_maybe_awaitable
from app.platforms.evaluation.token_stats_models import TokenDailyStats
from app.platforms.evaluation.trace_models import TraceRecord

logger = logging.getLogger(__name__)

MAX_TRACE_JSON_LEN = 128_000
MAX_TRACE_STRING_LEN = 16_000
MAX_TRACE_LIST_ITEMS = 100


class TraceDAO:
    """SQLite 批量写入器，内存队列 + flush 机制。"""

    def __init__(self, max_queue: int = 1000, batch_size: int = 20) -> None:
        self._queue: deque[dict[str, Any]] = deque(maxlen=max_queue)
        self._batch_size = batch_size
        self._total_flushed = 0

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    def record(self, trace_data: dict[str, Any]) -> None:
        """将一条 trace 数据入队。"""
        if "output_data" in trace_data and trace_data["output_data"]:
            trace_data["output_data"] = _truncate_json_value(trace_data["output_data"])
        self._queue.append(trace_data)

    async def flush_now(self) -> int:
        """立即将队列中的所有数据写入 Trace Repository。"""
        if not self._queue:
            return 0

        items = list(self._queue)
        self._queue.clear()

        db = SessionLocal()
        try:
            repo = get_trace_repository(db)
            for item in items:
                record = TraceRecord(**item)
                await resolve_maybe_awaitable(repo.insert(record))
            self._total_flushed += len(items)
            return len(items)
        except Exception:
            db.rollback()
            logger.exception("批量写入 trace 失败，丢弃 %d 条", len(items))
            return 0
        finally:
            db.close()

    def accumulate_token_stats(
        self,
        farm_id: int,
        user_id: str | None,
        date_str: str | date,
        model: str,
        call_type: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """累加 Token 日用量统计（UPSERT 逻辑）。"""
        total = prompt_tokens + completion_tokens
        db = SessionLocal()
        try:
            existing = (
                db.query(TokenDailyStats)
                .filter(
                    TokenDailyStats.user_id == user_id,
                    TokenDailyStats.farm_id == farm_id,
                    TokenDailyStats.date == _coerce_date(date_str),
                    TokenDailyStats.model == model,
                    TokenDailyStats.call_type == call_type,
                )
                .first()
            )
            if existing:
                existing.prompt_tokens += prompt_tokens
                existing.completion_tokens += completion_tokens
                existing.total_tokens += total
                existing.request_count += 1
            else:
                db.add(
                    TokenDailyStats(
                        user_id=user_id,
                        farm_id=farm_id,
                        date=_coerce_date(date_str),
                        model=model,
                        call_type=call_type,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total,
                        request_count=1,
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("累加 token 统计失败")
        finally:
            db.close()


def _coerce_date(value: str | date) -> date:
    """兼容旧调用方传入的 ISO 日期字符串。"""
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _truncate_json_value(value: Any) -> Any:
    """限制 trace 输出体积，同时保持 JSON 结构可展示。"""
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    if len(serialized) <= MAX_TRACE_JSON_LEN:
        return value
    clipped = _clip_json_value(value)
    if isinstance(clipped, dict):
        clipped["__trace_truncated"] = True
        clipped["__trace_original_json_len"] = len(serialized)
        return clipped
    return {
        "__trace_truncated": True,
        "__trace_original_json_len": len(serialized),
        "value": clipped,
    }


def _clip_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clip_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        clipped_items = [
            _clip_json_value(item) for item in value[:MAX_TRACE_LIST_ITEMS]
        ]
        if len(value) > MAX_TRACE_LIST_ITEMS:
            clipped_items.append(
                {
                    "__trace_truncated": True,
                    "dropped_items": len(value) - MAX_TRACE_LIST_ITEMS,
                }
            )
        return clipped_items
    if isinstance(value, str) and len(value) > MAX_TRACE_STRING_LEN:
        return f"{value[:MAX_TRACE_STRING_LEN]}...[TRUNCATED]"
    return value


__all__ = ["TraceDAO"]
