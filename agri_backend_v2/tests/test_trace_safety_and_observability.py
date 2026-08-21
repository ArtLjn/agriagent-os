"""Trace 脱敏、预算聚合和事实源漂移回归测试。"""

from __future__ import annotations

from agent.domains.harness.memory.service import source_divergence
from agent.domains.harness.observability.trace.safety import (
    safe_token_usage,
    sanitize_payload,
)
from agent.domains.harness.observability.trace.summary import (
    build_trace_request_summary,
)


def test_trace_payload_redacts_credentials_and_hidden_reasoning() -> None:
    payload = sanitize_payload(
        {
            "authorization": "Bearer secret",
            "reasoning_content": "private chain",
            "nested": {"api_key": "key", "value": "visible"},
        },
        max_chars=2000,
    )

    assert payload["authorization"] == "[REDACTED]"
    assert payload["reasoning_content"] == "[HIDDEN_REASONING_OMITTED]"
    assert payload["nested"]["api_key"] == "[REDACTED]"
    assert payload["nested"]["value"] == "visible"


def test_trace_token_usage_keeps_only_numeric_usage_fields() -> None:
    assert safe_token_usage(
        {
            "prompt_tokens": "10",
            "completion_tokens": 3,
            "total_tokens": 13,
            "raw_response": "must not be persisted",
        }
    ) == {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}


def test_source_divergence_is_structured_and_not_treated_as_empty() -> None:
    divergence = source_divergence(
        {
            "source_status": "mongo",
            "conversation_revision": 8,
            "summary_revision": 2,
        },
        redis_conversation_revision=7,
        redis_summary_revision=2,
    )

    assert divergence == {
        "code": "conversation_revision_divergence",
        "sources": {
            "mongo": {"conversation_revision": 8},
            "redis": {"conversation_revision": 7},
        },
    }


def test_precomputed_divergent_session_view_remains_divergent() -> None:
    divergence = source_divergence(
        {
            "source_status": "divergent",
            "source_divergence": {
                "code": "summary_source_revision_ahead",
                "sources": {"mongo": {"summary_revision": 3}},
            },
        }
    )

    assert divergence["code"] == "summary_source_revision_ahead"


def test_trace_summary_aggregates_context_and_memory_metrics() -> None:
    summary = build_trace_request_summary(
        [
            {
                "request_id": "request-1",
                "trace_id": "trace-1",
                "node_type": "context_build",
                "status": "success",
                "duration_ms": 4,
                "output_data": {
                    "budget": {
                        "message_tokens": 100,
                        "tool_schema_tokens": 20,
                        "response_reserve_tokens": 40,
                        "safety_margin_tokens": 10,
                        "used_tokens": 120,
                    },
                    "blocks": [
                        {"status": "compressed"},
                        {"status": "dropped"},
                    ],
                },
            },
            {
                "request_id": "request-1",
                "trace_id": "trace-1",
                "node_type": "context_source_divergence",
                "status": "error",
                "duration_ms": 1,
            },
            {
                "request_id": "request-1",
                "trace_id": "trace-1",
                "node_type": "memory_observe",
                "status": "success",
                "duration_ms": 1,
            },
        ]
    )

    assert summary is not None
    metrics = summary["metrics"]
    assert metrics["context_used_tokens"] == 120
    assert metrics["context_compressed_blocks"] == 1
    assert metrics["context_dropped_blocks"] == 1
    assert metrics["source_divergence_count"] == 1
    assert metrics["memory_observations"] == 1
