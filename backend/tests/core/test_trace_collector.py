"""Tests for app.core.trace_collector。"""
from unittest.mock import MagicMock

import pytest

from app.core.trace_context import init_trace, clear_trace


@pytest.fixture(autouse=True)
def _clean_trace() -> None:
    yield
    clear_trace()


class TestTraceCollector:
    def test_record_without_context_skips(self) -> None:
        """没有 trace 上下文时 record 不入队。"""
        clear_trace()
        from app.core.trace_collector import TraceCollector
        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector.record(
            node_type="llm_call", node_name="llm",
            input_data="test", output_data="ok",
        )
        collector._dao.record.assert_not_called()

    def test_record_with_context_enqueues(self) -> None:
        """有 trace 上下文时 record 入队。"""
        init_trace(farm_id=1)
        from app.core.trace_collector import TraceCollector
        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector.record(
            node_type="llm_call", node_name="llm",
            input_data="test", output_data="ok",
            start_time=1000.0, end_time=1001.5,
        )
        collector._dao.record.assert_called_once()
        call_kwargs = collector._dao.record.call_args[0][0]
        assert call_kwargs["node_type"] == "llm_call"
        assert call_kwargs["duration_ms"] == 1500

    def test_record_accumulates_token_stats(self) -> None:
        """record 同时调用 token 统计累加。"""
        init_trace(farm_id=1)
        from app.core.trace_collector import TraceCollector
        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector._dao.accumulate_token_stats = MagicMock()
        collector.record(
            node_type="llm_call", node_name="llm",
            input_data="test", output_data="ok",
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )
        collector._dao.accumulate_token_stats.assert_called_once()
