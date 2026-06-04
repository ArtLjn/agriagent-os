"""Trace 收集器 — 统一入口，委托 TraceDAO 存储。"""

import asyncio
import logging
import time
from datetime import date, datetime
from typing import Any

from app.infra.trace_context import get_trace, get_round_index
from app.infra.trace_dao import TraceDAO

logger = logging.getLogger(__name__)

_dao: TraceDAO | None = None
_flush_task: asyncio.Task | None = None
_running = False


def get_trace_dao() -> TraceDAO | None:
    """获取全局 TraceDAO 实例。"""
    return _dao


def init_trace_dao() -> TraceDAO:
    """初始化全局 TraceDAO 实例。"""
    global _dao
    _dao = TraceDAO()
    logger.info("TraceDAO 已初始化")
    return _dao


class TraceCollector:
    """埋点收集入口，组装 trace 数据后委托 TraceDAO。"""

    _dao: TraceDAO

    def record(
        self,
        node_type: str,
        node_name: str,
        input_data: Any = None,
        output_data: Any = None,
        start_time: float | None = None,
        end_time: float | None = None,
        duration_ms: int | None = None,
        token_usage: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """记录一条 trace。无上下文时静默跳过。"""
        trace = get_trace()
        if trace is None:
            return

        dao = self._dao if hasattr(self, "_dao") else get_trace_dao()
        if dao is None:
            return

        if duration_ms is None:
            if start_time is None:
                start_time = time.time()
            if end_time is None:
                end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
        else:
            if start_time is None:
                start_time = time.time()
            if end_time is None:
                end_time = time.time()

        trace_data = {
            "request_id": trace.request_id,
            "session_id": trace.session_id or None,
            "farm_id": trace.farm_id,
            "round_index": get_round_index(),
            "node_type": node_type,
            "node_name": node_name,
            "input_data": input_data,
            "output_data": output_data,
            "start_time": datetime.fromtimestamp(start_time),
            "end_time": datetime.fromtimestamp(end_time),
            "duration_ms": duration_ms,
            "token_usage": token_usage,
            "status": "error" if error_message else "success",
            "error_message": error_message,
        }

        dao.record(trace_data)

        # 只累计真实 provider / LangChain usage，缺失或估算来源不入账。
        if token_usage and node_type == "llm_call":
            usage_source = token_usage.get("usage_source")
            if usage_source not in {"provider", "usage_metadata"}:
                logger.warning(
                    "跳过 token 统计：缺少真实 usage 来源 | request_id=%s | "
                    "node=%s | usage_source=%s",
                    trace.request_id,
                    node_name,
                    usage_source,
                )
                return
            dao.accumulate_token_stats(
                farm_id=trace.farm_id,
                user_id=trace.user_id,
                date_str=date.today().isoformat(),
                model=node_name,
                call_type=trace.call_type,
                prompt_tokens=token_usage.get("prompt_tokens", 0),
                completion_tokens=token_usage.get("completion_tokens", 0),
            )
        elif node_type == "llm_call":
            logger.warning(
                "跳过 token 统计：缺少 token_usage | request_id=%s | node=%s",
                trace.request_id,
                node_name,
            )


_collector: TraceCollector | None = None


def get_collector() -> TraceCollector:
    """获取全局收集器实例。"""
    global _collector
    if _collector is None:
        _collector = TraceCollector()
    return _collector


async def start_trace_system() -> None:
    """启动 trace 后台 flush worker。"""
    global _flush_task, _running
    init_trace_dao()
    _running = True
    _flush_task = asyncio.create_task(_flush_loop())
    logger.info("Trace 后台 worker 已启动")


async def stop_trace_system() -> None:
    """停止 trace 系统，flush 剩余数据。"""
    global _running, _flush_task
    _running = False
    if _flush_task:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
    # 最后 flush 一次
    dao = get_trace_dao()
    if dao and dao.queue_size > 0:
        await dao.flush_now()
    logger.info("Trace 系统已停止，剩余数据已 flush")


async def _flush_loop() -> None:
    """定时 flush：队列满时批量写入，超时时也写入避免数据积压。"""
    from app.core.config import settings

    interval = settings.trace.flush_interval

    while _running:
        try:
            await asyncio.sleep(interval)
            dao = get_trace_dao()
            if dao and dao.queue_size > 0:
                await dao.flush_now()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Trace flush 循环异常")
            await asyncio.sleep(1)


__all__ = [
    "TraceCollector",
    "get_collector",
    "get_trace_dao",
    "init_trace_dao",
    "start_trace_system",
    "stop_trace_system",
]
