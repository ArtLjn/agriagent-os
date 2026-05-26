"""Tests for app.services.quota_service。"""

from unittest.mock import MagicMock, patch

from app.services.quota_service import check_quota, get_today_usage


class TestCheckQuota:
    @patch("app.services.quota_service.SessionLocal")
    def test_under_limit_returns_true(self, mock_sl) -> None:
        mock_db = MagicMock()
        mock_sl.return_value = mock_db
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5000

        assert check_quota(farm_id=1) is True

    @patch("app.services.quota_service.SessionLocal")
    def test_over_limit_returns_false(self, mock_sl) -> None:
        mock_db = MagicMock()
        mock_sl.return_value = mock_db
        mock_db.query.return_value.filter.return_value.scalar.return_value = 100001

        assert check_quota(farm_id=1) is False


class TestGetTodayUsage:
    @patch("app.services.quota_service.SessionLocal")
    def test_returns_usage(self, mock_sl) -> None:
        mock_db = MagicMock()
        mock_sl.return_value = mock_db
        mock_db.query.return_value.filter.return_value.scalar.return_value = 12345

        result = get_today_usage(farm_id=1)
        assert result == 12345
