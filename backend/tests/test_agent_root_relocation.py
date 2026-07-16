"""agent 根文件归位兼容测试。"""

from importlib import import_module
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.no_db


def test_router_modules_export_new_and_legacy_paths() -> None:
    intent = import_module("app.agent.router.intent")
    legacy_intent = import_module("app.agent.intent_router")
    assert legacy_intent.IntentType is intent.IntentType
    assert legacy_intent.classify_intent is intent.classify_intent
    assert legacy_intent.get_greeting_reply is intent.get_greeting_reply

    rules = import_module("app.agent.router.rules")
    legacy_rules = import_module("app.agent.tool_selection_rules")
    assert legacy_rules.TOOL_CHAIN_MAP is rules.TOOL_CHAIN_MAP
    assert legacy_rules.WRITE_PATTERNS is rules.WRITE_PATTERNS
    assert legacy_rules.QUERY_TRIGGERS is rules.QUERY_TRIGGERS

    selector = import_module("app.agent.router.tool_selector")
    legacy_selector = import_module("app.agent.tool_selector")
    assert legacy_selector.ToolSelectionResult is selector.ToolSelectionResult
    assert legacy_selector.select_tools is selector.select_tools
    assert legacy_selector.expand_by_chain is selector.expand_by_chain
    assert legacy_selector.DISABLED_SKILLS is rules.DISABLED_SKILLS
    assert legacy_selector.PLANTING_ADVICE_HINTS is rules.PLANTING_ADVICE_HINTS
    assert legacy_selector.QUERY_INTENT_HINTS is rules.QUERY_INTENT_HINTS
    assert legacy_selector.QUERY_TRIGGERS is rules.QUERY_TRIGGERS
    assert legacy_selector.TOOL_CHAIN_MAP is rules.TOOL_CHAIN_MAP
    assert legacy_selector.WRITE_INTENT_HINTS is rules.WRITE_INTENT_HINTS
    assert legacy_selector.WRITE_PATTERNS is rules.WRITE_PATTERNS


def test_core_modules_export_new_and_legacy_paths() -> None:
    llm = import_module("app.core.llm")
    legacy_llm = import_module("app.agent.llm")
    assert legacy_llm.LlmNotConfiguredError is llm.LlmNotConfiguredError
    assert legacy_llm.get_llm is llm.get_llm

    roles = import_module("app.core.settings.roles")
    legacy_roles = import_module("app.agent.assistant_roles")
    assert legacy_roles.DEFAULT_ASSISTANT_ROLE == roles.DEFAULT_ASSISTANT_ROLE
    assert legacy_roles.normalize_assistant_role is roles.normalize_assistant_role
    assert legacy_roles.assistant_role_prompt is roles.assistant_role_prompt


def test_legacy_llm_patch_targets_still_drive_get_llm() -> None:
    legacy_llm = import_module("app.agent.llm")

    manager = MagicMock()
    manager.fallback_mode = True
    chat_instance = MagicMock()

    with (
        patch("app.core.llm_client_manager.get_llm_manager", return_value=manager),
        patch("app.agent.llm.settings") as mock_settings,
        patch("app.agent.llm.ChatOpenAI", return_value=chat_instance) as mock_chat,
    ):
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen-test"
        mock_settings.ai_base_url = "https://example.test/v1"
        mock_settings.circuit_breaker_config = MagicMock(
            retry_max=1,
            retry_backoff_base=1,
        )
        mock_settings.ai = MagicMock(enable_thinking=True)

        assert legacy_llm.get_llm() is chat_instance

    mock_chat.assert_called_once()
