"""Tests for trace 相关数据模型。"""
from app.models.trace import TraceRecord
from app.models.token_stats import TokenDailyStats


class TestTraceRecord:
    def test_create_trace_record(self) -> None:
        record = TraceRecord(
            request_id="abc12345",
            farm_id=1,
            round_index=0,
            node_type="llm_call",
            node_name="llm",
            status="success",
            duration_ms=150,
        )
        assert record.request_id == "abc12345"
        assert record.node_type == "llm_call"
        assert record.status == "success"

    def test_trace_record_defaults(self) -> None:
        record = TraceRecord(
            request_id="abc12345",
            farm_id=1,
            node_type="skill_call",
            node_name="get_weather",
        )
        # SQLAlchemy default 在实例化时不生效，仅验证字段存在和 None 值
        assert record.round_index is None
        assert record.status is None
        assert record.input_data is None
        assert record.output_data is None
        assert record.token_usage is None
        assert record.error_message is None


class TestTokenDailyStats:
    def test_create_stats(self) -> None:
        stats = TokenDailyStats(
            farm_id=1,
            date="2026-05-26",
            model="qwen3.6-flash",
            call_type="chat",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            request_count=1,
        )
        assert stats.farm_id == 1
        assert stats.total_tokens == 150
        assert stats.request_count == 1

    def test_unique_constraint_fields(self) -> None:
        stats = TokenDailyStats(
            farm_id=1,
            date="2026-05-26",
            model="qwen3.6-flash",
            call_type="chat",
        )
        # SQLAlchemy default 在实例化时不生效，仅验证字段存在
        assert stats.estimated_cost_cny is None
