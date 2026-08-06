"""Agent 建议 use case 测试。"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_get_daily_runs_service_in_worker_thread(monkeypatch) -> None:
    from app.application.advice import use_case as advice_use_case

    caller_thread = threading.get_ident()
    observed: dict[str, int] = {}

    async def _fake_get_daily_advice(*_args, **_kwargs):
        observed["thread"] = threading.get_ident()
        return "daily-response"

    monkeypatch.setattr(advice_use_case, "get_daily_advice", _fake_get_daily_advice)

    result = await advice_use_case.get_daily(
        SimpleNamespace(),
        SimpleNamespace(id=1, user_id="user-1"),
        cycle_id=None,
    )

    assert result == "daily-response"
    assert observed["thread"] != caller_thread
