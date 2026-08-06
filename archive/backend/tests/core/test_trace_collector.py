"""Tests for app.infra.trace_collector。"""

from datetime import date

from unittest.mock import MagicMock

import pytest

from app.infra.trace_context import init_trace, clear_trace


@pytest.fixture(autouse=True)
def _clean_trace() -> None:
    yield
    clear_trace()


class TestTraceCollector:
    def test_record_without_context_skips(self) -> None:
        """没有 trace 上下文时 record 不入队。"""
        clear_trace()
        from app.infra.trace_collector import TraceCollector

        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector.record(
            node_type="llm_call",
            node_name="llm",
            input_data="test",
            output_data="ok",
        )
        collector._dao.record.assert_not_called()

    def test_record_with_context_enqueues(self) -> None:
        """有 trace 上下文时 record 入队。"""
        init_trace(farm_id=1)
        from app.infra.trace_collector import TraceCollector

        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector.record(
            node_type="llm_call",
            node_name="llm",
            input_data="test",
            output_data="ok",
            start_time=1000.0,
            end_time=1001.5,
        )
        collector._dao.record.assert_called_once()
        call_kwargs = collector._dao.record.call_args[0][0]
        assert call_kwargs["node_type"] == "llm_call"
        assert call_kwargs["duration_ms"] == 1500

    def test_record_accumulates_provider_token_stats_with_user(self) -> None:
        """provider 真实 token usage 才累计到用户维度统计。"""
        init_trace(farm_id=1, user_id="u1", call_type="chat")
        from app.infra.trace_collector import TraceCollector

        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector._dao.accumulate_token_stats = MagicMock()
        collector.record(
            node_type="llm_call",
            node_name="llm",
            input_data="test",
            output_data="ok",
            token_usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "usage_source": "provider",
            },
        )
        collector._dao.accumulate_token_stats.assert_called_once_with(
            farm_id=1,
            user_id="u1",
            date_str=date.today().isoformat(),
            model="llm",
            call_type="chat",
            prompt_tokens=100,
            completion_tokens=50,
        )

    def test_record_skips_missing_token_usage_source(self) -> None:
        """缺真实 usage 来源时不累计 token 统计。"""
        init_trace(farm_id=1, user_id="u1", call_type="chat")
        from app.infra.trace_collector import TraceCollector

        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector._dao.accumulate_token_stats = MagicMock()
        collector.record(
            node_type="llm_call",
            node_name="llm",
            input_data="test",
            output_data="ok",
            token_usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "usage_source": "missing",
            },
        )
        collector._dao.accumulate_token_stats.assert_not_called()

    def test_reflection_check_records_without_accumulating_token_stats(self) -> None:
        """reflection_check 只记录 trace，不累计 token 统计。"""
        init_trace(farm_id=1, user_id="u1", call_type="chat")
        from app.infra.trace_collector import TraceCollector

        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector._dao.accumulate_token_stats = MagicMock()
        collector.record(
            node_type="reflection_check",
            node_name="pre_write_plan",
            input_data={"skill_name": "create_cost_record"},
            output_data={"decision": "block_write"},
            token_usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "usage_source": "provider",
            },
        )

        collector._dao.record.assert_called_once()
        collector._dao.accumulate_token_stats.assert_not_called()
