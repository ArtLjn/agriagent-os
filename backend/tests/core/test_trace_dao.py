"""Tests for app.core.trace_dao。"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.infra.trace_dao import TraceDAO


@pytest.fixture
def dao():
    """创建 TraceDAO 实例（不启动后台 worker）。"""
    return TraceDAO()


class TestTraceDAORecord:
    def test_enqueue_trace(self, dao) -> None:
        dao.record(
            {
                "request_id": "abc12345",
                "farm_id": 1,
                "round_index": 0,
                "node_type": "llm_call",
                "node_name": "llm",
                "status": "success",
                "duration_ms": 100,
            }
        )
        assert dao.queue_size == 1

    def test_enqueue_multiple(self, dao) -> None:
        for i in range(5):
            dao.record(
                {
                    "request_id": f"req{i:08d}",
                    "farm_id": 1,
                    "node_type": "skill_call",
                    "node_name": f"skill_{i}",
                }
            )
        assert dao.queue_size == 5


class TestTraceDAOFlushBatch:
    @patch("app.infra.trace_dao.SessionLocal")
    def test_flush_writes_batch(self, mock_session_local, dao) -> None:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        for i in range(3):
            dao.record(
                {
                    "request_id": f"req{i:08d}",
                    "farm_id": 1,
                    "node_type": "llm_call",
                    "node_name": "llm",
                }
            )

        asyncio.get_event_loop().run_until_complete(dao.flush_now())

        assert mock_session.add.call_count == 3
        assert mock_session.commit.call_count == 1
        assert dao.queue_size == 0

    @patch("app.infra.trace_dao.SessionLocal")
    def test_flush_handles_db_error(self, mock_session_local, dao) -> None:
        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("DB error")
        mock_session_local.return_value = mock_session

        dao.record(
            {
                "request_id": "err000001",
                "farm_id": 1,
                "node_type": "llm_call",
                "node_name": "llm",
            }
        )

        # 不应抛出异常
        asyncio.get_event_loop().run_until_complete(dao.flush_now())
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestTokenStatsAccumulation:
    @patch("app.infra.trace_dao.SessionLocal")
    def test_accumulate_new_entry(self, mock_session_local, dao) -> None:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None

        dao.accumulate_token_stats(
            farm_id=1,
            date_str="2026-05-26",
            model="qwen3.6-flash",
            call_type="chat",
            prompt_tokens=100,
            completion_tokens=50,
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
