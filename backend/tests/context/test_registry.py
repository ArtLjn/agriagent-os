"""Context block 注册表契约测试。"""

from app.context.pipeline.allowlist import is_allowed_key
from app.context.core.registry import (
    BLOCK_REGISTRY,
    ContextCategory,
    block_spec,
    prompt_allowed_keys,
    section_for_key,
)
from app.context.pipeline.renderer import ContextRenderer


def test_existing_context_keys_are_registered() -> None:
    expected = {
        "farm",
        "cycle",
        "ledger",
        "weather",
        "user_settings",
        "active_task_state",
        "pending_action",
        "temporary_task_state",
        "rag_knowledge",
        "retrieval",
        "tool_result_summary",
        "short_term_recent",
        "recent_messages",
        "short_term_summary",
        "conversation",
        "conversation_summary",
        "long_term_memory",
        "output_contract",
        "citation_rule",
        "clarification_rule",
        "farm_profile",
        "user_profile",
        "session_meta",
        "current_crop_cycle_pointer",
        "pending_action_pointer",
        "pending_plan_pointer",
        "last_confirmed_at",
        "assistant_role",
    }

    assert expected.issubset(BLOCK_REGISTRY)


def test_registry_drives_allowlist_and_renderer_sections() -> None:
    assert "long_term_memory" in prompt_allowed_keys()
    assert is_allowed_key("long_term_memory") is True
    assert is_allowed_key("conversation_summary") is True
    assert is_allowed_key("recent_messages") is True
    assert block_spec("rag_knowledge").category == ContextCategory.EVIDENCE
    assert section_for_key("rag_knowledge") == "Evidence"
    assert ContextRenderer().section_name_for_key("active_task_state") == "Task"


def test_registry_does_not_expand_prompt_allowlist_for_renderer_only_keys() -> None:
    renderer_only_keys = {
        "planting_units",
        "operation_work_orders",
        "workers",
        "unpaid_labor",
        "cost_categories",
        "weather",
        "retrieval",
        "conversation",
    }

    assert renderer_only_keys.issubset(BLOCK_REGISTRY)
    for key in renderer_only_keys:
        assert is_allowed_key(key) is False
        assert section_for_key(key) in {"Context", "Evidence"}


def test_unknown_keys_are_not_prompt_allowed_but_fallback_to_context_section() -> None:
    assert block_spec("unregistered_debug_blob") is None
    assert is_allowed_key("unregistered_debug_blob") is False
    assert section_for_key("unregistered_debug_blob") == "Context"
