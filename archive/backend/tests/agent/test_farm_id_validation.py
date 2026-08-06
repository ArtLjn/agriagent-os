"""Agent farm_id 显式校验回归测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langchain_core.messages import HumanMessage

from app.agent.errors import FarmIdMissingError
from app.agent.runtime.nodes import _farm_id_or_rejection
from app.application.chat.use_case import chat
from app.domains.conversation.agent_schemas import ChatRequest
from tests.agent.test_exception_logging import _load_lint_module

pytestmark = pytest.mark.no_db


def _state_without_farm_id() -> dict:
    return {
        "messages": [HumanMessage(content="你好")],
        "farm_uid": "farm-uid-1",
        "intent": "agent",
        "user_id": "user-1",
        "session_id": "session-1",
    }


def test_farm_id_missing_raises_fail_closed() -> None:
    with pytest.raises(FarmIdMissingError, match="农场标识缺失"):
        _farm_id_or_rejection(_state_without_farm_id())


def test_farm_id_invalid_raises_fail_closed() -> None:
    state = {**_state_without_farm_id(), "farm_id": 0}

    with pytest.raises(FarmIdMissingError, match="农场标识缺失"):
        _farm_id_or_rejection(state)


def test_farm_id_legacy_flag_falls_back_to_default(caplog) -> None:
    state = _state_without_farm_id()
    settings = SimpleNamespace(
        agent=SimpleNamespace(strict_farm_id=False),
        token_quota=SimpleNamespace(over_quota_action="reject"),
    )

    with (
        patch("app.agent.runtime.nodes.settings", settings),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
    ):
        farm_id, rejection = _farm_id_or_rejection(state)

    assert farm_id == 1
    assert rejection is None
    assert "strict_farm_id disabled" in caplog.text


@pytest.mark.asyncio
async def test_chat_rejects_invalid_farm_id_before_agent_execution() -> None:
    farm = MagicMock(id=None, user_id="user-1")

    with (
        patch(
            "app.application.chat.use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as pending,
        patch(
            "app.application.chat.use_case.invoke_advisor", new_callable=AsyncMock
        ) as advisor,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await chat(
                MagicMock(),
                ChatRequest(message="今天怎么安排"),
                farm,
                request_id="req-farm-missing",
            )

    assert exc_info.value.status_code == 400
    assert "农场标识缺失" in str(exc_info.value.detail)
    pending.assert_not_called()
    advisor.assert_not_called()


def test_lint_detects_farm_id_integer_default(tmp_path) -> None:
    lint_module = _load_lint_module()
    source = tmp_path / "bad_farm_id.py"
    source.write_text(
        (
            """
def bad(state):
    return state.get("farm_"""
            """id", 1)
"""
        ),
        encoding="utf-8",
    )

    violations = lint_module.find_violations([source])

    assert len(violations) == 1
    assert violations[0].message == "farm_id 禁止使用整数默认值回退"
