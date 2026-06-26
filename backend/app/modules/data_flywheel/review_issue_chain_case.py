"""ReviewIssueChain 生成回归用例草稿。"""

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.infra.repository_runtime import (
    get_data_flywheel_repository,
    run_maybe_awaitable,
)
from app.models.data_flywheel import AgentCaseDraft
from app.modules.data_flywheel.review_issue_chain_service import (
    get_review_issue_chain_detail,
)
from app.modules.data_flywheel.service import _ALLOWED_TARGET_TYPES


def build_case_draft_from_review_issue_chain(
    db: Session,
    *,
    farm_id: int,
    chain_id: str,
    target_type: str,
    created_by: str | None = None,
    chain_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从已审核问题链或虚拟链 payload 生成评测回放草稿。"""
    if target_type not in _ALLOWED_TARGET_TYPES:
        raise ValueError("INVALID_TARGET_TYPE")
    detail = chain_payload or get_review_issue_chain_detail(
        db, farm_id=farm_id, chain_id=chain_id
    )
    chain = detail.get("chain") or {}
    expected_behavior = _expected_behavior(chain)
    if not expected_behavior:
        raise ValueError("CHAIN_EXPECTED_BEHAVIOR_REQUIRED")

    trigger_sample_id = _trigger_sample_id(farm_id=farm_id, chain=chain)
    case_json = build_chain_case_json(chain_id=chain_id, detail=detail)
    draft = AgentCaseDraft(
        farm_id=farm_id,
        draft_id=f"draft-{uuid.uuid4().hex[:12]}",
        source_sample_id=trigger_sample_id,
        target_type=target_type,
        status="draft",
        case_json=case_json,
        created_by=created_by,
    )
    draft = _repo_call(_case_draft_repo(db).create, draft)
    return _draft_to_dict(draft)


def build_chain_case_json(*, chain_id: str, detail: dict[str, Any]) -> dict[str, Any]:
    """构造携带 chain metadata 的 evaluation replay case。"""
    chain = detail.get("chain") or {}
    expected_behavior = _expected_behavior(chain)
    if not expected_behavior:
        raise ValueError("CHAIN_EXPECTED_BEHAVIOR_REQUIRED")
    related_turns = _related_turns(detail)
    trigger = detail.get("trigger_turn") or {}
    quality_labels = _quality_labels(chain)
    return {
        "case_id": f"regression-{_safe_id(chain_id)}",
        "description": f"Data flywheel review issue chain {chain_id}",
        "user_input": _message_content(trigger, "user")
        or str(trigger.get("user_input_preview") or ""),
        "category": quality_labels[0] if quality_labels else "data_flywheel_chain",
        "expected_skills": [
            {"name": tool_name}
            for tool_name in _selected_tools_for_trigger(detail, chain)
        ],
        "expected_parameters": {},
        "expected_pending_action": _expected_pending_action(detail, chain),
        "confirmation_flow": [],
        "expected_database_diff": [],
        "reply_assertions": [{"contains": expected_behavior}],
        "issue_assertions": _issue_assertions(chain, expected_behavior),
        "context": {"related_turns": related_turns},
        "metadata": {
            "source": "data_flywheel_review_issue_chain",
            "chain_id": chain.get("chain_id") or chain_id,
            "session_id": chain.get("session_id"),
            "trigger_turn_id": chain.get("trigger_turn_id"),
            "context_turn_ids": chain.get("context_turn_ids") or [],
            "result_turn_ids": chain.get("result_turn_ids") or [],
            "related_turn_ids": [turn["turn_id"] for turn in related_turns],
            "source_sample_id": _trigger_sample_id_from_chain(chain),
            "expected_behavior": expected_behavior,
            "quality_labels": quality_labels,
            "root_cause": _root_cause(chain),
            "diagnosis": chain.get("diagnosis") or {},
        },
    }


def _related_turns(detail: dict[str, Any]) -> list[dict[str, Any]]:
    chain = detail.get("chain") or {}
    roles = {
        **{turn_id: "context" for turn_id in chain.get("context_turn_ids") or []},
        chain.get("trigger_turn_id"): "trigger",
        **{turn_id: "result" for turn_id in chain.get("result_turn_ids") or []},
    }
    timeline = detail.get("timeline") or []
    by_id = {item.get("turn_id"): item for item in timeline if isinstance(item, dict)}
    ordered_ids = (
        list(chain.get("context_turn_ids") or [])
        + [chain.get("trigger_turn_id")]
        + list(chain.get("result_turn_ids") or [])
    )
    turns: list[dict[str, Any]] = []
    for turn_id in ordered_ids:
        if turn_id is None or turn_id not in by_id:
            continue
        item = by_id[turn_id]
        turns.append(
            {
                "turn_id": turn_id,
                "role": roles.get(turn_id, "related"),
                "request_id": item.get("request_id"),
                "messages": item.get("messages") or [],
                "selected_tools": item.get("selected_tools") or [],
                "tool_events": item.get("tool_events") or [],
                "pending_lifecycle": item.get("pending_lifecycle") or [],
            }
        )
    return turns


def _issue_assertions(
    chain: dict[str, Any], expected_behavior: str
) -> list[dict[str, str]]:
    diagnosis = chain.get("diagnosis") or {}
    candidate_type = diagnosis.get("candidate_type") or diagnosis.get("title")
    if not candidate_type:
        return []
    return [
        {
            "type": str(candidate_type),
            "expected": expected_behavior,
            "evidence": str(diagnosis.get("summary") or ""),
        }
    ]


def _selected_tools_for_trigger(
    detail: dict[str, Any], chain: dict[str, Any]
) -> list[str]:
    trigger_turn_id = chain.get("trigger_turn_id")
    for item in detail.get("timeline") or []:
        if isinstance(item, dict) and item.get("turn_id") == trigger_turn_id:
            return [str(tool) for tool in item.get("selected_tools") or [] if tool]
    trigger = detail.get("trigger_turn") or {}
    return [str(tool) for tool in trigger.get("selected_tools") or [] if tool]


def _expected_pending_action(
    detail: dict[str, Any], chain: dict[str, Any]
) -> dict[str, Any] | None:
    trigger_turn_id = chain.get("trigger_turn_id")
    trigger = None
    for item in detail.get("timeline") or []:
        if isinstance(item, dict) and item.get("turn_id") == trigger_turn_id:
            trigger = item
            break
    trigger = trigger or detail.get("trigger_turn") or {}
    pending = trigger.get("pending_lifecycle") or []
    for event in pending:
        payload = event.get("payload") if isinstance(event, dict) else None
        steps = payload.get("steps") if isinstance(payload, dict) else None
        if isinstance(steps, list) and steps:
            skill_name = steps[0].get("skill_name")
            if skill_name:
                return {
                    "skill_name": str(skill_name),
                    "params": {},
                    "status": "created",
                    "confirmation_required": True,
                }
    return None


def _quality_labels(chain: dict[str, Any]) -> list[str]:
    human = chain.get("human_review") or {}
    labels = human.get("quality_labels") or human.get("final_labels") or []
    return [str(label) for label in labels if label]


def _expected_behavior(chain: dict[str, Any]) -> str | None:
    human = chain.get("human_review") or {}
    value = human.get("expected_behavior") or (chain.get("regression") or {}).get(
        "expected_behavior"
    )
    if isinstance(value, str):
        value = value.strip()
    return value or None


def _root_cause(chain: dict[str, Any]) -> str | None:
    human = chain.get("human_review") or {}
    value = human.get("root_cause")
    if isinstance(value, str):
        value = value.strip()
    return value or None


def _message_content(turn: dict[str, Any], role: str) -> str | None:
    for message in turn.get("messages") or []:
        if isinstance(message, dict) and message.get("role") == role:
            return message.get("content")
    return None


def _trigger_sample_id(*, farm_id: int, chain: dict[str, Any]) -> str:
    expected = _trigger_sample_id_from_chain(chain)
    if expected.startswith(f"turn:{farm_id}:"):
        return expected
    raise ValueError("CHAIN_NOT_FOUND")


def _trigger_sample_id_from_chain(chain: dict[str, Any]) -> str:
    parts = str(chain.get("chain_id") or "").split(":", 3)
    farm_id = parts[1] if len(parts) >= 4 else ""
    return f"turn:{farm_id}:{chain.get('session_id')}:{chain.get('trigger_turn_id')}"


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9-]+", "-", value).strip("-")
    return safe or "chain"


def _draft_to_dict(draft: AgentCaseDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "draft_id": draft.draft_id,
        "source_sample_id": draft.source_sample_id,
        "target_type": draft.target_type,
        "status": draft.status,
        "case_json": draft.case_json,
        "created_by": draft.created_by,
    }


def _case_draft_repo(db: Session):
    return get_data_flywheel_repository(db, "case_drafts")


def _repo_call(method, *args, **kwargs):
    return run_maybe_awaitable(method(*args, **kwargs))
