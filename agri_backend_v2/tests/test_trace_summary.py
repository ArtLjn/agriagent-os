"""Trace summary 对 root span 和资源 span 的聚合契约测试。"""

from agent.domains.harness.observability.trace.summary import build_trace_request_summary


def test_summary_uses_root_duration_without_double_counting_children() -> None:
    summary = build_trace_request_summary(
        [
            {
                "request_id": "trace-1",
                "trace_id": "trace-1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "node_type": "trace_root",
                "node_name": "turn",
                "span_kind": "root",
                "duration_ms": 1000,
                "start_time": "2026-08-19T10:00:00",
                "end_time": "2026-08-19T10:00:01",
                "status": "success",
            },
            {
                "request_id": "trace-1",
                "trace_id": "trace-1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "node_type": "llm_call",
                "node_name": "model",
                "duration_ms": 700,
                "status": "success",
                "token_usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 18,
                    "total_tokens": 138,
                },
            },
            {
                "request_id": "trace-1",
                "trace_id": "trace-1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "node_type": "mcp_call",
                "node_name": "get_weather",
                "layer": "resource",
                "duration_ms": 200,
                "status": "success",
            },
        ]
    )

    assert summary is not None
    assert summary["total_duration_ms"] == 1000
    assert summary["logical_span_count"] == 2
    assert summary["resource_span_count"] == 1
    assert summary["metrics"]["mcp_calls"] == 1
    assert summary["metrics"]["prompt_tokens"] == 120
    assert summary["metrics"]["completion_tokens"] == 18
    assert summary["metrics"]["total_tokens"] == 138


def test_finalization_warning_is_partial_when_visible_turn_completed() -> None:
    summary = build_trace_request_summary(
        [
            {
                "request_id": "trace-partial",
                "trace_id": "trace-partial",
                "node_type": "trace_root",
                "node_name": "turn",
                "duration_ms": 100,
                "status": "success",
            },
            {
                "request_id": "trace-partial",
                "trace_id": "trace-partial",
                "node_type": "persistence_state",
                "node_name": "turn.finalization",
                "status": "fallback",
                "error_message": "turn_finalization_incomplete",
                "output_data": {
                    "message_status": "ready",
                    "session_status": "unavailable",
                    "observation_status": "ready",
                },
            },
            {
                "request_id": "trace-partial",
                "trace_id": "trace-partial",
                "node_type": "turn",
                "node_name": "outcome",
                "status": "success",
                "output_data": {"status": "completed"},
            },
        ]
    )

    assert summary is not None
    assert summary["status"] == "partial"
    assert summary["status_reason"] == "turn_finalization_incomplete"
    assert summary["error_count"] == 0
    assert summary["warning_count"] == 1
