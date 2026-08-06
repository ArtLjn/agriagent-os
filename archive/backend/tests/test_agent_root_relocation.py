"""agent 根文件归位后的真实路径测试。"""

from importlib import import_module
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.no_db


def test_router_modules_export_expected_public_api() -> None:
    intent = import_module("app.agent.router.intent")
    assert intent.IntentType is not None
    assert intent.classify_intent is not None
    assert intent.get_greeting_reply is not None

    rules = import_module("app.agent.router.rules")
    assert rules.TOOL_CHAIN_MAP
    assert rules.WRITE_PATTERNS
    assert rules.QUERY_TRIGGERS

    selector = import_module("app.agent.router.tool_selector")
    assert selector.ToolSelectionResult is not None
    assert selector.select_tools is not None
    assert selector.expand_by_chain is not None
    assert selector.DISABLED_SKILLS is rules.DISABLED_SKILLS
    assert selector.PLANTING_ADVICE_HINTS is rules.PLANTING_ADVICE_HINTS
    assert selector.QUERY_INTENT_HINTS is rules.QUERY_INTENT_HINTS
    assert selector.QUERY_TRIGGERS is rules.QUERY_TRIGGERS
    assert selector.TOOL_CHAIN_MAP is rules.TOOL_CHAIN_MAP
    assert selector.WRITE_INTENT_HINTS is rules.WRITE_INTENT_HINTS
    assert selector.WRITE_PATTERNS is rules.WRITE_PATTERNS


def test_shared_modules_export_expected_public_api() -> None:
    llm = import_module("app.shared.llm")
    assert llm.LlmNotConfiguredError is not None
    assert llm.get_llm is not None

    roles = import_module("app.shared.config")
    assert roles.DEFAULT_ASSISTANT_ROLE
    assert roles.normalize_assistant_role is not None
    assert roles.assistant_role_prompt is not None


def test_shared_llm_patch_target_drives_get_llm() -> None:
    llm = import_module("app.shared.llm")

    manager = MagicMock()
    manager.fallback_mode = True
    chat_instance = MagicMock()

    with (
        patch("app.shared.llm.get_llm_manager", return_value=manager),
        patch("app.shared.llm.settings") as mock_settings,
        patch("app.shared.llm.ChatOpenAI", return_value=chat_instance) as mock_chat,
    ):
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen-test"
        mock_settings.ai_base_url = "https://example.test/v1"
        mock_settings.circuit_breaker_config = MagicMock(
            retry_max=1,
            retry_backoff_base=1,
        )
        mock_settings.ai = MagicMock(enable_thinking=True)

        assert llm.get_llm() is chat_instance

    mock_chat.assert_called_once()
