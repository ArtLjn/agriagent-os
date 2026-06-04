"""Tests for app.services.quota_service。"""

from datetime import date
from unittest.mock import MagicMock, patch

from app.models.farm import Farm
from app.models.user import User
from app.services.quota_service import (
    QuotaCheckResult,
    check_quota,
    check_user_quota,
    get_month_range,
    get_period_usage,
    get_user_quota_limits,
    get_week_range,
)


def test_get_month_range_returns_natural_month() -> None:
    start, end = get_month_range(date(2026, 6, 4))
    assert start == date(2026, 6, 1)
    assert end == date(2026, 6, 30)


def test_get_week_range_starts_monday() -> None:
    start, end = get_week_range(date(2026, 6, 4))
    assert start == date(2026, 6, 1)
    assert end == date(2026, 6, 7)


def test_get_user_quota_limits_uses_custom_values() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=500,
        token_weekly_limit=100,
    )
    db.query.return_value.filter.return_value.first.return_value = user

    limits = get_user_quota_limits("u1", db)

    assert limits.monthly_limit == 500
    assert limits.weekly_limit == 100


def test_get_user_quota_limits_preserves_zero_custom_values() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=0,
        token_weekly_limit=0,
    )
    db.query.return_value.filter.return_value.first.return_value = user

    limits = get_user_quota_limits("u1", db)

    assert limits.monthly_limit == 0
    assert limits.weekly_limit == 0


def test_get_period_usage_sums_user_tokens() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = 123

    usage = get_period_usage(
        user_id="u1",
        start=date(2026, 6, 1),
        end=date(2026, 6, 7),
        db=db,
    )

    assert usage == 123


def test_check_user_quota_rejects_missing_user_id() -> None:
    db = MagicMock()

    result = check_user_quota(None, db)

    assert isinstance(result, QuotaCheckResult)
    assert result.allowed is False
    assert result.exceeded_period == "identity"


def test_check_user_quota_rejects_unknown_user_id() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    result = check_user_quota("unknown", db)

    assert result.allowed is False
    assert result.exceeded_period == "identity"


def test_check_user_quota_allows_under_limits() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=500,
        token_weekly_limit=100,
    )
    db.query.return_value.filter.return_value.first.return_value = user
    with patch("app.services.quota_service.get_period_usage", side_effect=[10, 20]):
        result = check_user_quota("u1", db, today=date(2026, 6, 4))

    assert result.allowed is True
    assert result.exceeded_period is None
    assert result.monthly_usage == 10
    assert result.monthly_remaining == 490
    assert result.weekly_usage == 20
    assert result.weekly_remaining == 80


def test_check_user_quota_rejects_weekly_over_limit() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=1000,
        token_weekly_limit=100,
    )
    db.query.return_value.filter.return_value.first.return_value = user
    with patch("app.services.quota_service.get_period_usage", side_effect=[50, 100]):
        result = check_user_quota("u1", db, today=date(2026, 6, 4))

    assert result.allowed is False
    assert result.exceeded_period == "week"
    assert result.monthly_remaining == 950
    assert result.weekly_remaining == 0
    assert result.reset_at == "2026-06-08"


def test_check_user_quota_rejects_monthly_over_limit_with_next_month_reset() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=1000,
        token_weekly_limit=100,
    )
    db.query.return_value.filter.return_value.first.return_value = user
    with patch("app.services.quota_service.get_period_usage", side_effect=[1000, 50]):
        result = check_user_quota("u1", db, today=date(2026, 6, 4))

    assert result.allowed is False
    assert result.exceeded_period == "month"
    assert result.monthly_remaining == 0
    assert result.weekly_remaining == 50
    assert result.reset_at == "2026-07-01"


def test_check_user_quota_reports_zero_remaining_for_zero_limits() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=0,
        token_weekly_limit=0,
    )
    db.query.return_value.filter.return_value.first.return_value = user
    with patch("app.services.quota_service.get_period_usage", side_effect=[0, 0]):
        result = check_user_quota("u1", db, today=date(2026, 6, 4))

    assert result.allowed is False
    assert result.exceeded_period == "month"
    assert result.monthly_remaining == 0
    assert result.weekly_remaining == 0


@patch("app.services.quota_service.SessionLocal")
def test_check_quota_wraps_farm_user_lookup(mock_session_local) -> None:
    db = MagicMock()
    mock_session_local.return_value = db
    db.query.return_value.filter.return_value.first.return_value = Farm(
        id=1,
        name="f",
        user_id="u1",
    )
    with patch("app.services.quota_service.check_user_quota") as check_user:
        check_user.return_value = QuotaCheckResult(allowed=True)
        assert check_quota(1) is True
        check_user.assert_called_once()
        db.close.assert_called_once()


@patch("app.services.quota_service.SessionLocal")
def test_check_quota_rejects_missing_farm(mock_session_local) -> None:
    db = MagicMock()
    mock_session_local.return_value = db
    db.query.return_value.filter.return_value.first.return_value = None
    with patch("app.services.quota_service.check_user_quota") as check_user:
        check_user.return_value = QuotaCheckResult(
            allowed=False, exceeded_period="identity"
        )
        assert check_quota(1) is False
        check_user.assert_called_once_with(None, db)
        db.close.assert_called_once()
