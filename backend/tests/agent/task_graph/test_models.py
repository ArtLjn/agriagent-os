"""Task Graph 数据模型契约测试。"""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.agent.task_graph.models import (
    EvaluationReport,
    ExecutionState,
    FactSource,
    NodeResult,
    PlanningSlot,
    PlanningSlotSet,
    RawContext,
)

pytestmark = pytest.mark.no_db


class UnknownTraceObject:
    pass


def test_models_export_json_safe_trace_payloads_and_redact_sensitive_values() -> None:
    slot = PlanningSlot(
        name="total_area_mu",
        value=30,
        source=FactSource(kind="user_input", ref="message:1"),
        normalized_unit="mu",
    )
    slot_set = PlanningSlotSet(
        task_type="planting_plan",
        slots={"total_area_mu": slot},
        missing_required_slots=["crop"],
    )
    context = RawContext(
        request_id="req-1",
        session_id="sess-1",
        user_id="user-1",
        memory_refs=["mem-1"],
        runtime_refs=[datetime(2026, 7, 29, tzinfo=timezone.utc)],
        trace_metadata={"api_key": "sk-secret", "safe": "ok"},
    )
    state = ExecutionState(
        execution_id="exec-1",
        graph_id="graph-1",
        status="waiting_user",
        current_node_id=None,
        waiting_for="confirmation",
    )
    result = NodeResult(
        node_id="n1",
        status="success",
        output_type="FarmStatus",
        output={"secret": "value", "farm_count": 1},
        facts={"total_area_mu": slot},
    )
    report = EvaluationReport(
        evaluation_id="eval-1",
        request_id="req-1",
        task_type="planting_plan",
        planner_version="planner.v1",
        slot_score=1.0,
        plan_ir_valid=True,
        graph_compile_success=True,
        contract_pass_rate=1.0,
        capability_success_rate=1.0,
        repair_count=0,
        retry_count=0,
        hallucination_count=0,
        latency_ms=10,
        token_count=20,
        capability_metrics={"QueryFarmStatus": {"success": True}},
    )

    payloads = [
        slot_set.to_trace_payload(),
        context.to_trace_payload(),
        state.to_trace_payload(),
        result.to_trace_payload(),
        report.to_trace_payload(),
    ]

    json.dumps(payloads, ensure_ascii=False)
    assert payloads[0]["slots"]["total_area_mu"]["source"]["kind"] == "user_input"
    assert payloads[1]["runtime_refs"][0] == "2026-07-29T00:00:00Z"
    assert payloads[1]["trace_metadata"]["api_key"] == "[REDACTED]"
    assert payloads[3]["output"]["secret"] == "[REDACTED]"
    assert payloads[4]["capability_metrics"]["QueryFarmStatus"]["success"] is True


def test_trace_payload_handles_unknown_any_objects_without_raising() -> None:
    context = RawContext(
        request_id="req-1",
        runtime_refs=[UnknownTraceObject()],
        trace_metadata={"token": "secret-value"},
    )

    payload = context.to_trace_payload()

    json.dumps(payload, ensure_ascii=False)
    assert payload["runtime_refs"][0] == "<UnknownTraceObject>"
    assert payload["trace_metadata"]["token"] == "[REDACTED]"


def test_trace_payload_redacts_common_sensitive_key_variants() -> None:
    context = RawContext(
        request_id="req-1",
        trace_metadata={
            "access_token": "a",
            "refreshToken": "b",
            "password_hash": "c",
            "x-api-key": "d",
            "apiKey": "e",
            "safe": "ok",
        },
    )

    payload = context.to_trace_payload()

    assert payload["trace_metadata"] == {
        "access_token": "[REDACTED]",
        "refreshToken": "[REDACTED]",
        "password_hash": "[REDACTED]",
        "x-api-key": "[REDACTED]",
        "apiKey": "[REDACTED]",
        "safe": "ok",
    }


def test_model_constraints_reject_invalid_scores_and_mixed_execution_state() -> None:
    with pytest.raises(ValidationError):
        FactSource(kind="user_input", confidence=1.1)
    with pytest.raises(ValidationError):
        EvaluationReport(
            evaluation_id="eval-1",
            request_id="req-1",
            task_type="planting_plan",
            planner_version="planner.v1",
            slot_score=-0.1,
            plan_ir_valid=True,
            graph_compile_success=True,
            contract_pass_rate=1.0,
            capability_success_rate=1.0,
            repair_count=0,
            retry_count=0,
            hallucination_count=0,
            latency_ms=10,
            token_count=20,
        )
    with pytest.raises(ValidationError):
        EvaluationReport(
            evaluation_id="eval-1",
            request_id="req-1",
            task_type="planting_plan",
            planner_version="planner.v1",
            slot_score=1.0,
            plan_ir_valid=True,
            graph_compile_success=True,
            contract_pass_rate=1.0,
            capability_success_rate=1.0,
            repair_count=0,
            retry_count=0,
            hallucination_count=0,
            latency_ms=10,
            token_count=20,
            capability_metrics={"QueryFarmStatus": {}},
        )
    with pytest.raises(ValidationError):
        ExecutionState(
            execution_id="exec-1",
            graph_id="graph-1",
            status="failed",
            waiting_for="confirmation",
        )
