"""Tests for app.infra.trace_context。"""

import pytest

from app.infra.trace_context import (
    TraceInfo,
    clear_trace,
    get_trace,
    get_round_index,
    increment_round,
    init_trace,
)


@pytest.fixture(autouse=True)
def _clean_trace() -> None:
    """每个测试前清理上下文。"""
    clear_trace()


class TestInitTrace:
    def test_init_returns_trace_info(self) -> None:
        trace = init_trace(farm_id=1)
        assert isinstance(trace, TraceInfo)
        assert trace.farm_id == 1
        assert len(trace.request_id) == 8
        assert trace.created_at > 0

    def test_init_with_session_id(self) -> None:
        trace = init_trace(farm_id=1, session_id="sess-abc")
        assert trace.session_id == "sess-abc"

    def test_init_with_user_id_and_call_type(self) -> None:
        trace = init_trace(farm_id=1, user_id="u1", call_type="stream_chat")
        assert trace.user_id == "u1"
        assert trace.call_type == "stream_chat"

    def test_init_default_session_id_is_empty(self) -> None:
        trace = init_trace(farm_id=1)
        assert trace.session_id == ""

    def test_init_generates_unique_request_ids(self) -> None:
        t1 = init_trace(farm_id=1)
        t2 = init_trace(farm_id=1)
        assert t1.request_id != t2.request_id

    def test_init_with_zero_farm_id(self) -> None:
        """farm_id=0 也是合法边界值。"""
        trace = init_trace(farm_id=0)
        assert trace.farm_id == 0

    def test_init_with_negative_farm_id(self) -> None:
        """farm_id 为负数时不应抛异常（由调用方校验）。"""
        trace = init_trace(farm_id=-1)
        assert trace.farm_id == -1


class TestGetTrace:
    def test_get_after_init(self) -> None:
        trace = init_trace(farm_id=1)
        assert get_trace() is trace

    def test_get_returns_none_before_init(self) -> None:
        assert get_trace() is None


class TestClearTrace:
    def test_clear_removes_context(self) -> None:
        init_trace(farm_id=1)
        clear_trace()
        assert get_trace() is None

    def test_clear_idempotent(self) -> None:
        clear_trace()
        clear_trace()
        assert get_trace() is None


class TestRoundTracking:
    def test_round_starts_at_zero(self) -> None:
        init_trace(farm_id=1)
        assert get_round_index() == 0

    def test_increment_round(self) -> None:
        init_trace(farm_id=1)
        assert increment_round() == 1
        assert get_round_index() == 1
        assert increment_round() == 2

    def test_round_resets_on_init(self) -> None:
        init_trace(farm_id=1)
        increment_round()
        increment_round()
        init_trace(farm_id=1)
        assert get_round_index() == 0

    def test_round_returns_zero_without_context(self) -> None:
        assert get_round_index() == 0


class TestAllExport:
    def test_all_exports(self) -> None:
        from app.infra import trace_context

        expected = [
            "TraceInfo",
            "init_trace",
            "get_trace",
            "clear_trace",
            "get_round_index",
            "increment_round",
        ]
        assert trace_context.__all__ == expected
