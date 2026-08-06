"""DataFlywheel 问题仓投影与规则候选包。"""

from typing import Any

from app.platforms.data_flywheel.models import AgentReviewIssueChain


DEFAULT_CROP_INVENTORY_POSITIVE_CASES = [
    "我的作物",
    "我家有哪些作物栽种",
    "当前种了哪些作物",
    "我有哪些茬口",
    "现在地里都种着什么",
]
DEFAULT_CROP_INVENTORY_NEGATIVE_CASES = [
    "今日天气对作物有什么影响",
    "农场整体状态怎么样",
    "作物最近要不要浇水",
    "今天适合给作物打药吗",
    "我的作物收益怎么样",
]


def build_issue_repository_entry(
    row: AgentReviewIssueChain,
    *,
    user_input: str | None = None,
    assistant_reply: str | None = None,
    actual_skill: str | None = None,
    expected_skill: str | None = None,
    actual_params: dict[str, Any] | None = None,
    expected_params: dict[str, Any] | None = None,
    source: str = "manual_test",
) -> dict[str, Any]:
    """把已保存的问题链投影为问题仓条目。"""
    related_turn_ids = _related_turn_ids(row)
    return {
        "issue_entry_id": f"issue:{row.chain_id}",
        "chain_id": row.chain_id,
        "session_id": row.session_id,
        "trigger_turn_id": row.trigger_turn_id,
        "related_turn_ids": related_turn_ids,
        "source": source,
        "status": row.status,
        "severity": row.severity,
        "dominant_signal": row.dominant_signal,
        "user_input": _clean_text(user_input),
        "assistant_reply": _clean_text(assistant_reply),
        "actual_skill": _clean_text(actual_skill),
        "expected_skill": _clean_text(expected_skill),
        "actual_params": actual_params or {},
        "expected_params": expected_params or {},
        "expected_behavior": row.expected_behavior,
        "root_cause": row.root_cause,
        "final_labels": list(row.final_labels or []),
        "fix_target": row.fix_target,
        "closure_state": _closure_state(row),
        "rule_candidate_ids": [],
        "regression_case_ids": [],
        "reviewer_comment": row.reviewer_comment,
        "reviewer_id": row.reviewer_id,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def build_rule_candidate_package(entry: dict[str, Any]) -> dict[str, Any]:
    """从问题仓条目生成规则候选包。"""
    if _is_crop_inventory_route_issue(entry):
        return _crop_inventory_route_candidate(entry)
    return _generic_rule_candidate(entry)


def _crop_inventory_route_candidate(entry: dict[str, Any]) -> dict[str, Any]:
    positive_cases = _merge_cases(
        [entry.get("user_input")],
        DEFAULT_CROP_INVENTORY_POSITIVE_CASES,
    )
    return {
        "candidate_id": "crop_inventory_query_should_route_to_crop_cycles",
        "source_issue_ids": [entry["issue_entry_id"]],
        "failure_mode": "broad_status_tool_overmatched_specific_crop_query",
        "target_layer": ["router_classifier", "skill_catalog"],
        "trigger_phrases": [
            "我的作物",
            "有哪些作物栽种",
            "当前种了哪些作物",
            "地里都种着什么",
        ],
        "anti_phrases": ["天气影响", "农场整体状态", "浇水建议", "收益分析"],
        "expected_skill": "get_crop_cycles",
        "wrong_skill": "get_farm_status",
        "expected_params": {},
        "positive_cases": positive_cases,
        "negative_cases": list(DEFAULT_CROP_INVENTORY_NEGATIVE_CASES),
        "promotion_gate": _promotion_gate(),
        "status": "draft",
        "owner": None,
    }


def _generic_rule_candidate(entry: dict[str, Any]) -> dict[str, Any]:
    candidate_id = _generic_candidate_id(entry)
    return {
        "candidate_id": candidate_id,
        "source_issue_ids": [entry["issue_entry_id"]],
        "failure_mode": _generic_failure_mode(entry),
        "target_layer": [_target_layer(entry)],
        "trigger_phrases": _compact([entry.get("user_input")]),
        "anti_phrases": [],
        "expected_skill": entry.get("expected_skill"),
        "wrong_skill": entry.get("actual_skill"),
        "expected_params": entry.get("expected_params") or {},
        "positive_cases": _compact([entry.get("user_input")]),
        "negative_cases": [],
        "promotion_gate": _promotion_gate(),
        "status": "draft",
        "owner": None,
    }


def _is_crop_inventory_route_issue(entry: dict[str, Any]) -> bool:
    return (
        entry.get("expected_skill") == "get_crop_cycles"
        and entry.get("actual_skill") == "get_farm_status"
        and "wrong_tool_selection" in set(entry.get("final_labels") or [])
    )


def _related_turn_ids(row: AgentReviewIssueChain) -> list[int]:
    return _unique_ints(
        list(row.context_turn_ids or [])
        + [row.trigger_turn_id]
        + list(row.result_turn_ids or [])
    )


def _closure_state(row: AgentReviewIssueChain) -> str:
    if row.status == "accepted":
        return "triaged"
    if row.status == "needs_evidence":
        return "needs_evidence"
    if row.status == "rejected":
        return "rejected"
    if row.status == "not_actionable":
        return "not_actionable"
    return "candidate"


def _promotion_gate() -> dict[str, bool]:
    return {
        "positive_cases_must_pass": True,
        "negative_cases_must_not_match": True,
        "existing_regression_must_pass": True,
        "skill_boundary_must_be_updated": True,
        "human_reviewer_required": True,
    }


def _generic_candidate_id(entry: dict[str, Any]) -> str:
    expected_skill = entry.get("expected_skill") or "unknown_expected_skill"
    wrong_skill = entry.get("actual_skill") or "unknown_actual_skill"
    label = next(iter(entry.get("final_labels") or ["bad_reply"]))
    return f"{label}_should_route_{wrong_skill}_to_{expected_skill}"


def _generic_failure_mode(entry: dict[str, Any]) -> str:
    labels = set(entry.get("final_labels") or [])
    if "wrong_tool_selection" in labels:
        return "wrong_tool_selected_for_user_intent"
    if "tool_parameter_mismatch" in labels:
        return "tool_parameters_mismatched_user_scope"
    return "accepted_issue_requires_candidate_rule"


def _target_layer(entry: dict[str, Any]) -> str:
    fix_target = entry.get("fix_target")
    if fix_target == "router":
        return "router_classifier"
    if fix_target == "skill":
        return "skill_md"
    if fix_target == "prompt":
        return "prompt"
    if fix_target == "pending":
        return "pending"
    return "policy"


def _merge_cases(*case_groups: list[str | None]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in case_groups:
        for case in group:
            text = _clean_text(case)
            if not text or text in seen:
                continue
            merged.append(text)
            seen.add(text)
    return merged


def _compact(values: list[Any]) -> list[str]:
    return [text for text in (_clean_text(value) for value in values) if text]


def _unique_ints(values: list[Any]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number in seen:
            continue
        result.append(number)
        seen.add(number)
    return result


def _clean_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
