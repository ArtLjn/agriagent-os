# backend/tests/context/test_allowlist.py
"""ContextBundle 白名单契约测试。"""
from app.context.allowlist import (
    ALLOWED_CONTEXT_KEYS,
    FORBIDDEN_CONTEXT_KEYS,
    is_allowed_key,
)


class TestAllowlistContract:
    def test_identity_keys_are_allowed(self):
        assert "farm_profile" in ALLOWED_CONTEXT_KEYS
        assert "user_settings" in ALLOWED_CONTEXT_KEYS

    def test_query_answer_keys_are_forbidden(self):
        assert "weather_snapshot" in FORBIDDEN_CONTEXT_KEYS
        assert "farm_status_snapshot" in FORBIDDEN_CONTEXT_KEYS
        assert "crop_cycle_details" in FORBIDDEN_CONTEXT_KEYS
        assert "recent_logs_summary" in FORBIDDEN_CONTEXT_KEYS
        assert "worker_list_snapshot" in FORBIDDEN_CONTEXT_KEYS
        assert "cost_summary_snapshot" in FORBIDDEN_CONTEXT_KEYS

    def test_is_allowed_key_returns_false_for_forbidden(self):
        assert is_allowed_key("weather_snapshot") is False

    def test_is_allowed_key_returns_true_for_whitelisted(self):
        assert is_allowed_key("farm_profile") is True

    def test_is_allowed_key_returns_false_for_unknown(self):
        assert is_allowed_key("totally_unknown_key") is False

    def test_no_overlap_between_allowed_and_forbidden(self):
        assert ALLOWED_CONTEXT_KEYS.isdisjoint(FORBIDDEN_CONTEXT_KEYS)
