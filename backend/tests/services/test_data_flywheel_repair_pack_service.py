"""数据飞轮 repair pack 服务测试。"""

from typing import Any

import pytest

from app.services.data_flywheel_repair_pack_service import (
    build_repair_pack_payload,
    derive_repair_candidate,
    group_samples_by_fix_target,
    sanitize_debug_evidence,
)
from app.services.data_flywheel_repair_pack_chain import (
    build_chain_repair_pack_payload,
    derive_chain_repair_candidate,
)

pytestmark = pytest.mark.no_db


def _sample_detail(
    labels: list[str],
    *,
    sample_id: str = "turn:1:sess-1:12",
    case_json: dict[str, Any] | None = None,
    debug_export: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sample = {
        "sample_id": sample_id,
        "session_id": "sess-1",
        "turn_id": 12,
        "request_id": "req-1",
        "user_input_preview": "安排王大妈去5号棚收水稻",
        "assistant_reply_preview": "已安排王大妈去5号棚收水稻",
        "selected_tools": ["create_operation_work_order"],
    }
    issue_candidates = [
        {
            "type": label,
            "severity": "high",
            "reason": f"{label} reason",
            "evidence": "debug evidence",
            "suggested_label": label,
        }
        for label in labels
    ]
    detail = {
        "sample": sample,
        "quality_labels": labels,
        "labels": [{"label": label, "status": "open"} for label in labels],
        "prelabels": [],
        "issue_candidates": issue_candidates,
        "source": source
        or {
            "event_file": "events.jsonl",
            "event_seq_start": 1,
            "event_seq_end": 5,
            "event_log_status": "available",
        },
        "messages": [
            {"role": "user", "content": "安排王大妈去5号棚收水稻"},
            {"role": "assistant", "content": "已安排王大妈去5号棚收水稻"},
        ],
        "debug_export": debug_export
        or {
            "events": [{"payload": {"token": "sk-secret-value"}}],
        },
    }
    if case_json is not None:
        detail["case_draft"] = {"case_json": case_json}
    return detail


@pytest.mark.parametrize(
    ("label", "fix_target", "priority"),
    [
        ("sensitive_info_leak", "guardrail", 100),
        ("pending_missed", "pending_plan", 90),
        ("disabled_worker_used", "tool_guardrail", 85),
        ("missing_wage", "domain_policy", 80),
        ("tool_error_ignored", "tool_result_state", 78),
        ("hallucinated_execution", "tool_result_state", 78),
        ("wrong_tool_selection", "router", 75),
        ("bad_reply", "prompt_or_sft", 50),
        ("off_topic", "prompt_or_sft", 50),
        ("unclear_custom_label", "manual_triage", 10),
    ],
)
def test_derive_repair_candidate_routes_labels(
    label: str, fix_target: str, priority: int
) -> None:
    candidate = derive_repair_candidate(_sample_detail([label]))

    assert candidate["fix_target"] == fix_target
    assert candidate["priority"] == priority
    assert candidate["labels"] == [label]
    assert candidate["verification_commands"]


def test_derive_repair_candidate_keeps_secondary_targets_by_priority() -> None:
    candidate = derive_repair_candidate(
        _sample_detail(["bad_reply", "sensitive_info_leak", "wrong_tool_selection"])
    )

    assert candidate["fix_target"] == "guardrail"
    assert candidate["priority"] == 100
    assert candidate["secondary_targets"] == [
        {
            "label": "wrong_tool_selection",
            "fix_target": "router",
            "priority": 75,
        },
        {
            "label": "bad_reply",
            "fix_target": "prompt_or_sft",
            "priority": 50,
        },
    ]


def test_derive_repair_candidate_uses_pending_prelabel_labels() -> None:
    detail = _sample_detail([])
    detail["quality_labels"] = []
    detail["labels"] = []
    detail["issue_candidates"] = []
    detail["prelabels"] = [
        {
            "status": "pending",
            "labels": ["wrong_tool_selection"],
        }
    ]

    candidate = derive_repair_candidate(detail)

    assert candidate["fix_target"] == "router"
    assert candidate["labels"] == ["wrong_tool_selection"]


def test_derive_chain_repair_candidate_routes_parameter_scope_to_router() -> None:
    detail = {
        "chain": {
            "chain_id": "chain:1:sess-1:12",
            "session_id": "sess-1",
            "trigger_turn_id": 12,
            "context_turn_ids": [11],
            "result_turn_ids": [13],
            "status": "accepted",
            "diagnosis": {
                "candidate_type": "tool_parameter_mismatch",
                "suggested_labels": ["wrong_tool_selection"],
            },
            "human_review": {
                "final_labels": ["needs_regression", "wrong_tool_selection"],
                "expected_behavior": "确认批量结算时应保留所有待结算工人。",
                "root_cause": "参数抽取收窄了批量作用域",
            },
        },
        "evidence_checklist": [{"key": "event_log", "status": "present"}],
    }

    candidate = derive_chain_repair_candidate(detail)

    assert candidate["fix_target"] == "router"
    assert candidate["regression_ready"] is True
    assert "参数抽取" in candidate["suggested_action"]
    assert "批量作用域" in candidate["suggested_action"]
    assert "pending 确认" in candidate["suggested_action"]
    assert candidate["labels"] == [
        "needs_regression",
        "wrong_tool_selection",
        "tool_parameter_mismatch",
    ]


def test_regression_ready_true_when_pending_case_has_assertions() -> None:
    candidate = derive_repair_candidate(
        _sample_detail(
            ["pending_missed"],
            case_json={
                "expected_pending_action": {
                    "skill_name": "create_operation_work_order"
                },
                "issue_assertions": [],
            },
        )
    )

    assert candidate["regression_ready"] is True


def test_regression_ready_false_for_generated_fallback_assertions() -> None:
    candidate = derive_repair_candidate(_sample_detail(["pending_missed"]))

    assert candidate["regression_ready"] is False


def test_build_repair_pack_payload_rejects_mixed_fix_targets() -> None:
    samples = [
        _sample_detail(["pending_missed"], sample_id="turn:1:sess-1:12"),
        _sample_detail(["wrong_tool_selection"], sample_id="turn:1:sess-1:13"),
    ]

    with pytest.raises(ValueError, match="MIXED_FIX_TARGETS"):
        build_repair_pack_payload(samples, pack_id="pack-1", export_path="repair-packs")

    groups = group_samples_by_fix_target(samples)
    assert sorted(groups) == ["pending_plan", "router"]
    assert groups["pending_plan"][0]["sample"]["sample_id"] == "turn:1:sess-1:12"


def test_build_repair_pack_payload_allows_manual_fix_target_override() -> None:
    samples = [
        _sample_detail(["pending_missed"], sample_id="turn:1:sess-1:12"),
        _sample_detail(["wrong_tool_selection"], sample_id="turn:1:sess-1:13"),
    ]

    payload = build_repair_pack_payload(
        samples,
        pack_id="pack-1",
        export_path="repair-packs/pack-1",
        fix_target_override="router",
    )

    assert payload["manifest"]["fix_target"] == "router"
    assert {case["fix_target"] for case in payload["cases_jsonl"]} == {"router"}
    assert payload["cases_jsonl"][0]["secondary_targets"][0]["fix_target"] == (
        "pending_plan"
    )
    assert payload["manifest"]["verification_commands"] == [
        "pytest tests/services/test_data_flywheel_service.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ]


def test_build_repair_pack_payload_returns_memory_files_and_vibecoding_readme() -> None:
    payload = build_repair_pack_payload(
        [
            _sample_detail(
                ["pending_missed"],
                case_json={
                    "case_id": "case-1",
                    "expected_pending_action": {
                        "skill_name": "create_operation_work_order"
                    },
                    "issue_assertions": [{"type": "pending_missed"}],
                },
            )
        ],
        pack_id="pack-1",
        export_path="repair-packs/pack-1",
        created_by="admin-1",
    )

    assert payload["manifest"]["pack_id"] == "pack-1"
    assert payload["manifest"]["fix_target"] == "pending_plan"
    assert payload["manifest"]["source_sample_ids"] == ["turn:1:sess-1:12"]
    assert len(payload["cases_jsonl"]) == 1
    assert payload["cases_jsonl"][0]["source_debug_json"] == (
        "debug/turn_1_sess_1_12.json"
    )
    assert "vibecoding" in payload["readme"]
    assert "先复现或补回归测试" in payload["readme"]
    assert "禁止把 bad reply 直接作为训练数据使用" in payload["readme"]
    assert "debug/turn_1_sess_1_12.json" in payload["debug_files"]
    assert "regression-drafts/case-1.json" in payload["regression_drafts"]


def test_build_chain_repair_pack_payload_keeps_trace_fields() -> None:
    detail = {
        "chain": {
            "chain_id": "chain:1:sess-1:12",
            "session_id": "sess-1",
            "trigger_turn_id": 12,
            "context_turn_ids": [11],
            "result_turn_ids": [13],
            "status": "accepted",
            "diagnosis": {
                "candidate_type": "bulk_intent_narrowed_to_single_entity",
                "summary": "批量意图被收窄",
            },
            "human_review": {
                "final_labels": ["needs_regression", "wrong_tool_selection"],
                "expected_behavior": "确认批量结算时应保留所有待结算工人。",
                "root_cause": "参数抽取收窄了批量作用域",
            },
        },
        "trigger_turn": {
            "turn_id": 12,
            "request_id": "req-12",
            "user_input_preview": "把这些人工都结清",
            "assistant_reply_preview": "已为王大妈创建结算确认。",
        },
        "timeline": [
            {
                "turn_id": 11,
                "messages": [{"role": "assistant", "content": "王大妈、李四未结"}],
                "tool_events": [],
                "pending_lifecycle": [],
            },
            {
                "turn_id": 12,
                "messages": [{"role": "user", "content": "把这些人工都结清"}],
                "tool_events": [],
                "pending_lifecycle": [{"event_type": "pending.plan.created"}],
            },
            {
                "turn_id": 13,
                "messages": [{"role": "user", "content": "确认"}],
                "tool_events": [{"event_type": "tool.call.finished"}],
                "pending_lifecycle": [],
            },
        ],
        "evidence_checklist": [
            {"key": "event_log", "status": "present"},
            {"key": "db_diff", "status": "needs_human"},
        ],
        "case_draft": {
            "case_json": {
                "case_id": "regression-chain-1",
                "metadata": {"chain_id": "chain:1:sess-1:12"},
                "issue_assertions": [{"type": "bulk_intent_narrowed_to_single_entity"}],
            }
        },
    }

    payload = build_chain_repair_pack_payload(
        detail,
        pack_id="repair-router-abc",
        export_path="repair-packs/repair-router-abc",
        created_by="admin-1",
    )

    manifest = payload["manifest"]
    case = payload["cases_jsonl"][0]
    assert manifest["source_chain_ids"] == ["chain:1:sess-1:12"]
    assert manifest["source_sample_ids"] == ["turn:1:sess-1:12"]
    assert manifest["fix_target"] == "router"
    assert manifest["root_cause"] == "参数抽取收窄了批量作用域"
    assert manifest["expected_behavior"] == "确认批量结算时应保留所有待结算工人。"
    assert manifest["warnings"] == [
        {
            "chain_id": "chain:1:sess-1:12",
            "reason": "EVIDENCE_NEEDS_HUMAN",
            "evidence_key": "db_diff",
        }
    ]
    assert case["chain_id"] == "chain:1:sess-1:12"
    assert case["trigger_turn_id"] == 12
    assert case["context_turn_ids"] == [11]
    assert case["result_turn_ids"] == [13]
    assert case["source_debug_json"] == "debug/chain_1_sess_1_12.json"
    assert case["regression_draft"] == "regression-drafts/regression-chain-1.json"
    debug = payload["debug_files"]["debug/chain_1_sess_1_12.json"]
    assert [turn["turn_id"] for turn in debug["related_turns"]] == [11, 12, 13]


def test_sanitize_debug_evidence_redacts_secrets_env_and_phone_numbers() -> None:
    evidence = {
        "api_key": "sk-live-abcdef",
        "nested": {
            "AUTH_TOKEN": "bearer-token",
            "notes": (
                "电话 13812345678，.env OPENAI_API_KEY=sk-prod-xyz，"
                "地址江苏省苏州市吴中区星湖街123号"
            ),
        },
        "events": [
            {
                "payload": "secret=top-secret password=hunter2 mobile=19987654321",
            }
        ],
    }

    sanitized = sanitize_debug_evidence(evidence)

    assert sanitized["api_key"].startswith("[REDACTED_SECRET]:")
    assert sanitized["nested"]["AUTH_TOKEN"].startswith("[REDACTED_SECRET]:")
    assert "138****5678" in sanitized["nested"]["notes"]
    assert "OPENAI_API_KEY=[REDACTED_SECRET]:" in sanitized["nested"]["notes"]
    assert "[REDACTED_ADDRESS:" in sanitized["nested"]["notes"]
    assert "星湖街123号" not in sanitized["nested"]["notes"]
    assert "top-secret" not in sanitized["events"][0]["payload"]
    assert "hunter2" not in sanitized["events"][0]["payload"]
    assert "199****4321" in sanitized["events"][0]["payload"]
