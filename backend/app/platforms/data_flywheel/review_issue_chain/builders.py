"""ReviewIssueChain 虚拟链与 AI judge payload 构建。"""

import sys
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_turn import AgentTurn
from app.platforms.data_flywheel.service import (
    _events_for_turn,
    _labels_by_sample,
    _prelabels_by_sample,
    _sample_id,
    _sample_row,
)
from app.platforms.shared.judge_service import (
    DataFlywheelJudgeClient,
    LABEL_DEFINITIONS,
    LABEL_SELECTION_RULES,
)
from app.platforms.data_flywheel.review_issue_chain.helpers import (
    ai_judge,
    chain_id,
    diagnosis,
    dominant_signal,
    evidence_checklist,
    evidence_status,
    human_review,
    regression_status,
    repair_status,
    risk_context,
    severity,
    turn_debug_summary,
)


def _chain_for_turn(
    db: Session,
    *,
    farm_id: int,
    trigger: AgentTurn,
    context_turns: list[AgentTurn],
    result_turns: list[AgentTurn],
) -> dict[str, Any]:
    sample_id = _sample_id(trigger)
    labels = _labels_by_sample(db, [sample_id]).get(sample_id, [])
    prelabels = _prelabels_by_sample(db, farm_id=farm_id, sample_ids=[sample_id]).get(
        sample_id, []
    )
    events = _patchable_events_for_turn(trigger)
    sample = _sample_row(trigger, labels, events, prelabels=prelabels)
    evidence = evidence_checklist(db, trigger, events)
    status = (
        "needs_evidence"
        if evidence_status(evidence) == "needs_evidence"
        else "ready_for_review"
    )
    return {
        "chain_id": chain_id(trigger),
        "session_id": trigger.session_id,
        "trigger_turn_id": trigger.id,
        "context_turn_ids": [turn.id for turn in context_turns],
        "result_turn_ids": [turn.id for turn in result_turns],
        "status": status,
        "severity": severity(sample),
        "dominant_signal": dominant_signal(sample),
        "risk_context": risk_context(sample),
        "diagnosis": diagnosis(sample),
        "ai_judge": ai_judge(sample),
        "human_review": human_review(labels),
        "regression": regression_status(sample, labels),
        "repair": repair_status(status, sample),
        "evidence_checklist": evidence,
        "sample": sample,
    }


def _chain_judge_input(
    db: Session,
    *,
    chain: dict[str, Any],
    trigger: AgentTurn,
    context_turns: list[AgentTurn],
    result_turns: list[AgentTurn],
) -> dict[str, Any]:
    return {
        "task": "judge_review_issue_chain",
        "prompt_version": "data-flywheel-chain-judge-v1",
        "judge_instructions": (
            "请基于完整 ReviewIssueChain evidence pack 给出 AI 预判。"
            "只能输出建议标签、根因草稿、置信度、理由和修复建议；"
            "不能输出最终人工结论。所有自然语言字段必须使用简体中文。"
        ),
        "label_definitions": LABEL_DEFINITIONS,
        "label_selection_rules": LABEL_SELECTION_RULES,
        "chain": {
            "chain_id": chain["chain_id"],
            "session_id": chain["session_id"],
            "trigger_turn_id": chain["trigger_turn_id"],
            "status": chain["status"],
            "severity": chain["severity"],
            "dominant_signal": chain["dominant_signal"],
            "diagnosis": chain["diagnosis"],
            "evidence_status": evidence_status(chain["evidence_checklist"]),
            "evidence_checklist": chain["evidence_checklist"],
        },
        "trigger_turn": turn_debug_summary(db, trigger),
        "context_turns": [turn_debug_summary(db, turn) for turn in context_turns],
        "result_turns": [turn_debug_summary(db, turn) for turn in result_turns],
        "output_schema": {
            "type": "object",
            "required": [
                "labels",
                "root_cause",
                "severity",
                "confidence",
                "reason",
                "recommended_fix",
            ],
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "root_cause": {"type": ["string", "null"]},
                "severity": {"type": "string"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
                "recommended_fix": {"type": ["string", "null"]},
                "missing_evidence": {"type": "array", "items": {"type": "string"}},
            },
        },
    }


def _chain_ai_judge_result(
    *,
    normalized: dict[str, Any],
    judge_client: DataFlywheelJudgeClient,
    chain_id: str,
    evidence_status_value: str,
) -> dict[str, Any]:
    labels = [str(label) for label in normalized.get("labels") or []]
    return {
        "judge_id": f"chain-judge:{chain_id}",
        "chain_id": chain_id,
        "bad_prob": normalized.get("confidence", 0.0),
        "confidence": normalized.get("confidence", 0.0),
        "severity": normalized.get("severity"),
        "issue_type": labels[0] if labels else "not_actionable",
        "suggested_label": labels[0] if labels else "not_actionable",
        "suggested_labels": labels,
        "root_cause": normalized.get("root_cause") or None,
        "reason": normalized.get("reason"),
        "recommended_fix": normalized.get("recommended_fix") or None,
        "missing_evidence": normalized.get("missing_evidence") or [],
        "evidence_status": evidence_status_value,
        "judge_model": judge_client.judge_model,
        "prompt_version": judge_client.prompt_version,
    }


def _chain_id(turn: AgentTurn) -> str:
    return f"chain:{turn.farm_id}:{turn.session_id}:{turn.id}"


def _patchable_events_for_turn(trigger: AgentTurn) -> list[dict[str, Any]]:
    service = sys.modules.get("app.platforms.data_flywheel.review_issue_chain.service")
    events_for_turn = getattr(service, "_events_for_turn", _events_for_turn)
    return events_for_turn(trigger)
