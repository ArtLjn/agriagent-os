"""ReviewIssueChain repair pack payload 构建。"""

import re
from typing import Any

from app.modules.data_flywheel.repair_pack_readme import build_repair_pack_readme
from app.modules.data_flywheel.repair_pack_service import (
    _merge_commands,
    _verification_commands,
    sanitize_debug_evidence,
)
from app.modules.data_flywheel.review_issue_chain_case import build_chain_case_json

_ROUTER_SCOPE_TYPES = {
    "tool_parameter_mismatch",
    "bulk_intent_narrowed_to_single_entity",
}
_ROUTER_SCOPE_ACTION = (
    "修复 router 的参数抽取、批量作用域保持和 pending 确认策略，避免把多对象意图收窄为单个实体。"
)


def derive_chain_repair_candidate(detail: dict[str, Any]) -> dict[str, Any]:
    """从 ReviewIssueChain 派生 repair candidate。"""
    chain = detail.get("chain") or {}
    labels = _labels(chain)
    candidate_type = _candidate_type(chain)
    fix_target = "router" if candidate_type in _ROUTER_SCOPE_TYPES else "manual_triage"
    regression_ready = bool(
        chain.get("status") == "accepted"
        and _expected_behavior(chain)
        and _related_turn_ids(chain)
    )
    return {
        "chain_id": chain.get("chain_id"),
        "sample_id": _source_sample_id(chain),
        "session_id": chain.get("session_id"),
        "trigger_turn_id": chain.get("trigger_turn_id"),
        "context_turn_ids": chain.get("context_turn_ids") or [],
        "result_turn_ids": chain.get("result_turn_ids") or [],
        "labels": labels,
        "fix_target": fix_target,
        "priority": 75 if fix_target == "router" else 10,
        "suggested_action": (
            _ROUTER_SCOPE_ACTION
            if fix_target == "router"
            else "人工分诊该问题链，导出前确认修复目标。"
        ),
        "regression_ready": regression_ready,
        "verification_commands": _verification_commands(fix_target),
        "secondary_targets": [],
    }


def build_chain_repair_pack_payload(
    detail: dict[str, Any],
    *,
    pack_id: str,
    export_path: str,
    created_by: str | None = None,
) -> dict[str, Any]:
    """构造单条 ReviewIssueChain 的 repair pack 文件 payload。"""
    candidate = derive_chain_repair_candidate(detail)
    chain = detail.get("chain") or {}
    warnings = _evidence_warnings(detail)
    case_json = _case_json(detail)
    chain_id = str(candidate["chain_id"])
    debug_path = f"debug/{_safe_stem(chain_id)}.json"
    draft_path = f"regression-drafts/{_safe_case_stem(str(case_json['case_id']))}.json"
    case = {
        "chain_id": chain_id,
        "sample_id": candidate["sample_id"],
        "session_id": candidate["session_id"],
        "trigger_turn_id": candidate["trigger_turn_id"],
        "context_turn_ids": candidate["context_turn_ids"],
        "result_turn_ids": candidate["result_turn_ids"],
        "labels": candidate["labels"],
        "root_cause": _root_cause(chain),
        "fix_target": candidate["fix_target"],
        "priority": candidate["priority"],
        "suggested_action": candidate["suggested_action"],
        "regression_ready": candidate["regression_ready"],
        "observed_failure": _observed_failure(chain),
        "expected_behavior": _expected_behavior(chain),
        "source_debug_json": debug_path,
        "regression_draft": draft_path,
        "source": "ReviewIssueChain",
    }
    labels = candidate["labels"]
    manifest = {
        "pack_id": pack_id,
        "export_path": export_path,
        "created_by": created_by,
        "fix_target": candidate["fix_target"],
        "goal": _goal(candidate["fix_target"]),
        "labels": labels,
        "source_chain_ids": [chain_id],
        "source_sample_ids": [str(candidate["sample_id"])],
        "root_cause": _root_cause(chain),
        "expected_behavior": _expected_behavior(chain),
        "case_count": 1,
        "verification_commands": _merge_commands([candidate["verification_commands"]]),
        "warnings": warnings,
    }
    return {
        "manifest": manifest,
        "cases_jsonl": [case],
        "readme": build_repair_pack_readme(manifest),
        "debug_files": {debug_path: _debug_evidence(detail)},
        "regression_drafts": {draft_path: case_json},
    }


def validate_chain_repair_export_ready(detail: dict[str, Any]) -> None:
    """导出前校验人工状态和 expected behavior。"""
    chain = detail.get("chain") or {}
    human = chain.get("human_review") or {}
    missing_evidence = human.get("missing_evidence") or []
    if chain.get("status") == "needs_evidence":
        raise ValueError({"code": "CHAIN_NEEDS_EVIDENCE", "missing_evidence": missing_evidence})
    if chain.get("status") != "accepted":
        raise ValueError({"code": "CHAIN_NOT_ACCEPTED", "status": chain.get("status")})
    if not _expected_behavior(chain):
        raise ValueError("CHAIN_EXPECTED_BEHAVIOR_REQUIRED")
    if not derive_chain_repair_candidate(detail)["regression_ready"]:
        raise ValueError("CHAIN_REGRESSION_NOT_READY")


def _case_json(detail: dict[str, Any]) -> dict[str, Any]:
    draft = detail.get("case_draft") or {}
    if isinstance(draft, dict) and isinstance(draft.get("case_json"), dict):
        return draft["case_json"]
    chain = detail.get("chain") or {}
    return build_chain_case_json(chain_id=str(chain.get("chain_id")), detail=detail)


def _debug_evidence(detail: dict[str, Any]) -> dict[str, Any]:
    chain = detail.get("chain") or {}
    related = set(_related_turn_ids(chain))
    timeline = [
        item
        for item in detail.get("timeline") or []
        if isinstance(item, dict) and item.get("turn_id") in related
    ]
    return sanitize_debug_evidence(
        {
            "chain": chain,
            "evidence_checklist": detail.get("evidence_checklist") or [],
            "related_turns": timeline,
        }
    )


def _evidence_warnings(detail: dict[str, Any]) -> list[dict[str, Any]]:
    chain_id = (detail.get("chain") or {}).get("chain_id")
    warnings: list[dict[str, Any]] = []
    for item in detail.get("evidence_checklist") or []:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status in {"missing", "needs_human"}:
            warnings.append(
                {
                    "chain_id": chain_id,
                    "reason": (
                        "EVIDENCE_MISSING"
                        if status == "missing"
                        else "EVIDENCE_NEEDS_HUMAN"
                    ),
                    "evidence_key": item.get("key"),
                }
            )
    return warnings


def _labels(chain: dict[str, Any]) -> list[str]:
    human = chain.get("human_review") or {}
    labels = list(human.get("quality_labels") or human.get("final_labels") or [])
    candidate_type = _candidate_type(chain)
    if candidate_type:
        labels.append(candidate_type)
    return list(dict.fromkeys(str(label) for label in labels if label))


def _candidate_type(chain: dict[str, Any]) -> str | None:
    diagnosis = chain.get("diagnosis") or {}
    value = diagnosis.get("candidate_type") or diagnosis.get("title")
    return str(value) if value else None


def _related_turn_ids(chain: dict[str, Any]) -> list[int]:
    return [
        *list(chain.get("context_turn_ids") or []),
        chain.get("trigger_turn_id"),
        *list(chain.get("result_turn_ids") or []),
    ]


def _source_sample_id(chain: dict[str, Any]) -> str:
    chain_id = str(chain.get("chain_id") or "")
    farm_id = chain_id.split(":")[1] if ":" in chain_id else ""
    return f"turn:{farm_id}:{chain.get('session_id')}:{chain.get('trigger_turn_id')}"


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


def _observed_failure(chain: dict[str, Any]) -> str:
    diagnosis = chain.get("diagnosis") or {}
    return str(diagnosis.get("summary") or diagnosis.get("title") or "问题链待修复")


def _goal(fix_target: str) -> str:
    if fix_target == "router":
        return "修复工具路由、参数抽取和批量作用域保持。"
    return "人工分诊问题链并补充最小回归验证。"


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return stem or "chain"


def _safe_case_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9-]+", "_", value).strip("_")
    return stem or "case"
