"""Context 与 Conversation state 配置解析测试。"""

from __future__ import annotations

from pathlib import Path

import yaml

from agent import config as config_module


def _build_from(tmp_path: Path, monkeypatch, payload: dict | None = None):
    config_file = tmp_path / "agent-config.yaml"
    if payload is not None:
        config_file.write_text(yaml.safe_dump(payload), encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_FILE", config_file)
    return config_module._build_settings()


def test_context_config_defaults_are_stable(tmp_path, monkeypatch):
    settings = _build_from(tmp_path, monkeypatch)

    assert settings.context.conversation_state_collection == "conversationStates"
    assert settings.context.summary_ttl_seconds == 86400
    assert settings.context.recent_turn_limit == 6
    assert settings.context.response_reserve_tokens == 4096
    assert settings.context.safety_margin_tokens == 1024
    assert settings.context.summary_soft_ratio == 0.60
    assert settings.context.summary_hard_ratio == 0.80
    assert settings.context.max_tool_result_summary_chars == 1200
    assert settings.context.tool_schema_mode == "all"
    assert settings.conversation_state is settings.context.conversation_state
    assert settings.context.feature_flags == {
        "context_bundle_v2": False,
        "conversation_state_v2": False,
        "summary_cas": False,
        "memory_mongo_read": False,
        "candidate_tool_schema": False,
        "long_term_memory_observation": False,
    }


def test_context_config_yaml_and_environment_overrides(tmp_path, monkeypatch):
    settings = _build_from(
        tmp_path,
        monkeypatch,
        {
            "environment": "staging",
            "redis": {"enabled": True, "port": 6381},
            "context": {
                "conversation_state": {
                    "collection": "conversationStatesStaging",
                },
                "summary_ttl_seconds": 7200,
                "recent_turn_limit": 8,
                "summary_soft_ratio": 0.55,
                "summary_hard_ratio": 0.75,
                "response_reserve_tokens": 2048,
                "safety_margin_tokens": 512,
                "max_tool_result_summary_chars": 800,
                "tool_schema_mode": "candidate",
                "feature_flags": {
                    "context_bundle_v2": True,
                    "conversation_state_v2": True,
                },
            },
        },
    )

    assert settings.environment == "staging"
    assert settings.redis.enabled is True
    assert settings.redis.port == 6381
    assert settings.context.conversation_state_collection == "conversationStatesStaging"
    assert settings.context.summary_ttl_seconds == 7200
    assert settings.context.recent_turn_limit == 8
    assert settings.context.summary_soft_ratio == 0.55
    assert settings.context.summary_hard_ratio == 0.75
    assert settings.context.response_reserve_tokens == 2048
    assert settings.context.safety_margin_tokens == 512
    assert settings.context.max_tool_result_summary_chars == 800
    assert settings.context.tool_schema_mode == "candidate"
    assert settings.context.feature_flags["context_bundle_v2"] is True
    assert settings.context.feature_flags["conversation_state_v2"] is True

    monkeypatch.setenv(
        "CONTEXT__CONVERSATION_STATE_COLLECTION", "conversationStatesEnv"
    )
    monkeypatch.setenv("CONTEXT__SUMMARY_TTL_SECONDS", "1800")
    monkeypatch.setenv("CONTEXT__RECENT_TURN_LIMIT", "4")
    monkeypatch.setenv("CONTEXT__RESPONSE_RESERVE_TOKENS", "3072")
    monkeypatch.setenv("CONTEXT__SAFETY_MARGIN_TOKENS", "768")
    monkeypatch.setenv("CONTEXT__SUMMARY_SOFT_RATIO", "0.65")
    monkeypatch.setenv("CONTEXT__SUMMARY_HARD_RATIO", "0.85")
    monkeypatch.setenv("CONTEXT__MAX_TOOL_RESULT_SUMMARY_CHARS", "600")
    monkeypatch.setenv("CONTEXT__TOOL_SCHEMA_MODE", "all")
    monkeypatch.setenv("CONTEXT__FEATURE_FLAGS__CONTEXT_BUNDLE_V2", "false")
    monkeypatch.setenv("FEATURE_FLAGS__CANDIDATE_TOOL_SCHEMA", "true")

    settings = config_module._build_settings()

    assert settings.context.conversation_state_collection == "conversationStatesEnv"
    assert settings.context.summary_ttl_seconds == 1800
    assert settings.context.recent_turn_limit == 4
    assert settings.context.response_reserve_tokens == 3072
    assert settings.context.safety_margin_tokens == 768
    assert settings.context.summary_soft_ratio == 0.65
    assert settings.context.summary_hard_ratio == 0.85
    assert settings.context.max_tool_result_summary_chars == 600
    assert settings.context.tool_schema_mode == "all"
    assert settings.context.feature_flags["context_bundle_v2"] is False
    assert settings.context.feature_flags["candidate_tool_schema"] is True
