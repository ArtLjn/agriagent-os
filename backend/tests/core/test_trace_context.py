"""Tests for app.core.trace_context。"""

from app.core.trace_context import (
    TraceInfo,
    clear_trace,
    get_trace,
    get_round_index,
    increment_round,
    init_trace,
)


class TestInitTrace:
    def test_init_returns_trace_info(self):
        trace = init_trace(farm_id=1)
        assert isinstance(trace, TraceInfo)
        assert trace.farm_id == 1
        assert len(trace.request_id) == 8
        assert trace.created_at > 0

    def test_init_with_session_id(self):
        trace = init_trace(farm_id=1, session_id="sess-abc")
        assert trace.session_id == "sess-abc"

    def test_init_generates_unique_request_ids(self):
        t1 = init_trace(farm_id=1)
        t2 = init_trace(farm_id=1)
        assert t1.request_id != t2.request_id


class TestGetTrace:
    def test_get_after_init(self):
        trace = init_trace(farm_id=1)
        assert get_trace() is trace

    def test_get_returns_none_before_init(self):
        clear_trace()
        assert get_trace() is None


class TestClearTrace:
    def test_clear_removes_context(self):
        init_trace(farm_id=1)
        clear_trace()
        assert get_trace() is None

    def test_clear_idempotent(self):
        clear_trace()
        clear_trace()
        assert get_trace() is None


class TestRoundTracking:
    def test_round_starts_at_zero(self):
        init_trace(farm_id=1)
        assert get_round_index() == 0

    def test_increment_round(self):
        init_trace(farm_id=1)
        assert increment_round() == 1
        assert get_round_index() == 1
        assert increment_round() == 2

    def test_round_resets_on_init(self):
        init_trace(farm_id=1)
        increment_round()
        increment_round()
        init_trace(farm_id=1)
        assert get_round_index() == 0

    def test_round_returns_zero_without_context(self):
        clear_trace()
        assert get_round_index() == 0
