"""Trace 收集器 — 统一入口，委托 TraceDAO 存储。"""

import json
import logging
import time
from datetime import date
from typing import Any

from app.core.trace_context import get_trace, get_round_index
from app.core.trace_dao import TraceDAO

logger = logging.getLogger(__name__)

_dao: TraceDAO | None = None


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

        if start_time is None:
            start_time = time.time()
        if end_time is None:
            end_time = time.time()

        duration_ms = int((end_time - start_time) * 1000)

        input_str = json.dumps(input_data, ensure_ascii=False, default=str) if input_data else None
        output_str = json.dumps(output_data, ensure_ascii=False, default=str) if output_data else None

        trace_data = {
            "request_id": trace.request_id,
            "session_id": trace.session_id or None,
            "farm_id": trace.farm_id,
            "round_index": get_round_index(),
            "node_type": node_type,
            "node_name": node_name,
            "input_data": input_str,
            "output_data": output_str,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
            "end_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(end_time)),
            "duration_ms": duration_ms,
            "token_usage": json.dumps(token_usage) if token_usage else None,
            "status": "error" if error_message else "success",
            "error_message": error_message,
        }

        dao.record(trace_data)

        # 同时累加 token 统计
        if token_usage and node_type == "llm_call":
            dao.accumulate_token_stats(
                farm_id=trace.farm_id,
                date_str=date.today().isoformat(),
                model=node_name,
                call_type="chat",
                prompt_tokens=token_usage.get("prompt_tokens", 0),
                completion_tokens=token_usage.get("completion_tokens", 0),
            )


_collector: TraceCollector | None = None


def get_collector() -> TraceCollector:
    """获取全局收集器实例。"""
    global _collector
    if _collector is None:
        _collector = TraceCollector()
    return _collector


__all__ = ["TraceCollector", "get_collector", "get_trace_dao", "init_trace_dao"]
