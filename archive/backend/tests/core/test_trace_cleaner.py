"""Tests for app.infra.trace_cleaner。"""

from unittest.mock import MagicMock, patch

from sqlalchemy.exc import ProgrammingError

from app.infra.trace_cleaner import clean_expired_traces


class TestCleanExpiredTraces:
    @patch("app.infra.trace_cleaner.SessionLocal")
    def test_deletes_old_records(self, mock_sl) -> None:
        mock_db = MagicMock()
        mock_sl.return_value = mock_db
        mock_db.query.return_value.filter.return_value.delete.return_value = 42

        result = clean_expired_traces()
        assert result["trace_records_deleted"] == 42

    @patch("app.infra.trace_cleaner.SessionLocal")
    def test_handles_db_error(self, mock_sl) -> None:
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB error")
        mock_sl.return_value = mock_db

        result = clean_expired_traces()
        assert result["trace_records_deleted"] == 0
        assert result["token_stats_deleted"] == 0
        mock_db.rollback.assert_called_once()

    @patch("app.infra.trace_cleaner.SessionLocal")
    def test_skips_missing_trace_table_without_rolling_back_token_cleanup(
        self, mock_sl
    ) -> None:
        mock_db = MagicMock()
        trace_query = MagicMock()
        stats_query = MagicMock()
        trace_query.filter.return_value.delete.side_effect = ProgrammingError(
            "DELETE FROM trace_records", {}, Exception("missing table")
        )
        stats_query.filter.return_value.delete.return_value = 3
        mock_db.query.side_effect = [trace_query, stats_query]
        mock_sl.return_value = mock_db

        result = clean_expired_traces()

        assert result["trace_records_deleted"] == 0
        assert result["token_stats_deleted"] == 3
        mock_db.commit.assert_called_once()
