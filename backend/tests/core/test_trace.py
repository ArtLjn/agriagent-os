"""Tests for app.core.trace.write_trace。"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.trace import MAX_SUMMARY_LEN, write_trace


# 覆盖 conftest.py 的 autouse clean_db fixture，避免真实数据库操作
@pytest.fixture(autouse=True)
def _override_clean_db():
    """禁用 conftest 的 clean_db，用 mock 替代。"""
    yield


@pytest.fixture
def mock_session():
    """Mock SessionLocal 返回的数据库 session。"""
    session = MagicMock()
    with patch("app.core.trace.SessionLocal", return_value=session):
        yield session


class TestWriteTraceNormal:
    """正常写入 trace 记录。"""

    def test_write_basic_trace(self, mock_session):
        write_trace(
            farm_id=1,
            session_id="sess-001",
            node_type="llm_call",
            node_name="llm",
            input_summary="hello",
            output_summary="world",
            duration_ms=100,
            tokens_used=50,
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

        trace_obj = mock_session.add.call_args[0][0]
        assert trace_obj.farm_id == 1
        assert trace_obj.session_id == "sess-001"
        assert trace_obj.node_type == "llm_call"
        assert trace_obj.node_name == "llm"
        assert trace_obj.input_summary == "hello"
        assert trace_obj.output_summary == "world"
        assert trace_obj.duration_ms == 100
        assert trace_obj.tokens_used == 50
        assert trace_obj.error_message is None

    def test_write_with_error_message(self, mock_session):
        write_trace(
            farm_id=2,
            session_id="sess-002",
            node_type="tool_call",
            node_name="get_weather",
            error_message="timeout",
        )

        trace_obj = mock_session.add.call_args[0][0]
        assert trace_obj.error_message == "timeout"
        assert trace_obj.node_type == "tool_call"

    def test_write_with_none_optionals(self, mock_session):
        write_trace(
            farm_id=1,
            session_id=None,
            node_type="llm_call",
            node_name="llm",
        )

        trace_obj = mock_session.add.call_args[0][0]
        assert trace_obj.session_id is None
        assert trace_obj.input_summary is None
        assert trace_obj.output_summary is None
        assert trace_obj.duration_ms is None
        assert trace_obj.tokens_used is None
        assert trace_obj.error_message is None

    def test_session_closed_in_finally(self, mock_session):
        """即使 commit 成功，session 也必须在 finally 中关闭。"""
        write_trace(
            farm_id=1,
            session_id="s",
            node_type="llm_call",
            node_name="llm",
        )
        mock_session.close.assert_called_once()


class TestWriteTraceTruncation:
    """长文本截断。"""

    def test_input_summary_truncated(self, mock_session):
        long_text = "a" * (MAX_SUMMARY_LEN + 100)
        write_trace(
            farm_id=1,
            session_id="s",
            node_type="llm_call",
            node_name="llm",
            input_summary=long_text,
        )

        trace_obj = mock_session.add.call_args[0][0]
        assert len(trace_obj.input_summary) == MAX_SUMMARY_LEN

    def test_output_summary_truncated(self, mock_session):
        long_text = "b" * (MAX_SUMMARY_LEN + 50)
        write_trace(
            farm_id=1,
            session_id="s",
            node_type="llm_call",
            node_name="llm",
            output_summary=long_text,
        )

        trace_obj = mock_session.add.call_args[0][0]
        assert len(trace_obj.output_summary) == MAX_SUMMARY_LEN

    def test_summary_within_limit_not_truncated(self, mock_session):
        text = "c" * MAX_SUMMARY_LEN
        write_trace(
            farm_id=1,
            session_id="s",
            node_type="llm_call",
            node_name="llm",
            input_summary=text,
        )

        trace_obj = mock_session.add.call_args[0][0]
        assert len(trace_obj.input_summary) == MAX_SUMMARY_LEN

    def test_none_summary_stays_none(self, mock_session):
        write_trace(
            farm_id=1,
            session_id="s",
            node_type="llm_call",
            node_name="llm",
            input_summary=None,
            output_summary=None,
        )

        trace_obj = mock_session.add.call_args[0][0]
        assert trace_obj.input_summary is None
        assert trace_obj.output_summary is None


class TestWriteTraceError:
    """数据库异常时不抛出，仅记录日志。"""

    def test_db_exception_no_raise(self, mock_session):
        """数据库 commit 异常时，write_trace 不应抛出异常。"""
        mock_session.commit.side_effect = Exception("DB connection lost")

        # 不应抛出异常
        write_trace(
            farm_id=1,
            session_id="s",
            node_type="llm_call",
            node_name="llm",
        )
        mock_session.close.assert_called_once()

    def test_db_exception_logs_error(self, mock_session, caplog):
        """数据库异常时应记录 ERROR 日志。"""
        mock_session.commit.side_effect = Exception("DB error")

        with caplog.at_level("ERROR", logger="app.core.trace"):
            write_trace(
                farm_id=1,
                session_id="s",
                node_type="llm_call",
                node_name="llm",
            )

        assert "写入 trace 失败" in caplog.text

    def test_session_closed_on_exception(self, mock_session):
        """数据库异常时 session 仍应在 finally 中关闭。"""
        mock_session.commit.side_effect = RuntimeError("boom")

        write_trace(
            farm_id=1,
            session_id="s",
            node_type="llm_call",
            node_name="llm",
        )
        mock_session.close.assert_called_once()
