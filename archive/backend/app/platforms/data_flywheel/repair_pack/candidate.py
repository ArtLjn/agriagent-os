"""Repair pack 候选路由与 payload 构建。"""

import re
from collections import defaultdict
from typing import Any

from app.platforms.data_flywheel.repair_pack.constants import (
    _DEFAULT_ROUTE,
    _ISSUE_TYPE_META,
    _LABEL_TO_ISSUE_TYPE,
    _VERIFY_BY_TARGET,
)
from app.platforms.data_flywheel.repair_pack.readme import build_repair_pack_readme
from app.platforms.data_flywheel.repair_pack.redaction import sanitize_debug_evidence


def derive_repair_candidate(detail: dict[str, Any]) -> dict[str, Any]:
    labels = _collect_labels(detail)
    routed = sorted(
        (_route_for_label(label) for label in labels),
        key=lambda item: (-int(item["priority"]), item["label"]),
    )
    primary = routed[0] if routed else _route_for_label("manual_triage")
    regression_ready = _is_regression_ready(detail)
    sample = detail.get("sample") or {}
    return {
        "sample_id": _sample_id(detail),
        "session_id": sample.get("session_id"),
        "turn_id": sample.get("turn_id"),
        "request_id": sample.get("request_id"),
        "labels": labels,
        "fix_target": primary["fix_target"],
        "priority": primary["priority"],
        "suggested_action": primary["suggested_action"],
        "regression_ready": regression_ready,
        "verification_commands": _verification_commands(primary["fix_target"]),
        "secondary_targets": [
            {
                "label": item["label"],
                "fix_target": item["fix_target"],
                "priority": item["priority"],
            }
            for item in routed[1:]
        ],
    }


def group_samples_by_fix_target(
    samples: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for detail in samples:
        candidate = derive_repair_candidate(detail)
        groups[str(candidate["fix_target"])].append(detail)
    return dict(groups)


def build_repair_pack_payload(
    samples: list[dict[str, Any]],
    *,
    pack_id: str,
    export_path: str,
    created_by: str | None = None,
    fix_target_override: str | None = None,
) -> dict[str, Any]:
    if not samples:
        raise ValueError("EMPTY_REPAIR_PACK")

    candidates = [derive_repair_candidate(detail) for detail in samples]
    override_target = fix_target_override.strip() if fix_target_override else None
    if override_target:
        candidates = [
            _override_candidate_fix_target(candidate, override_target)
            for candidate in candidates
        ]
    fix_targets = {str(candidate["fix_target"]) for candidate in candidates}
    if len(fix_targets) > 1:
        error = ValueError("MIXED_FIX_TARGETS")
        error.args = ("MIXED_FIX_TARGETS", _group_summary(samples))
        raise error

    fix_target = next(iter(fix_targets))
    cases: list[dict[str, Any]] = []
    debug_files: dict[str, Any] = {}
    regression_drafts: dict[str, Any] = {}
    warnings: list[dict[str, Any]] = []

    for detail, candidate in zip(samples, candidates, strict=True):
        sample = detail.get("sample") or {}
        sample_id = str(candidate["sample_id"])
        debug_path = f"debug/{_safe_sample_stem(sample_id)}.json"
        draft = _case_json(detail)
        draft_id = str(draft.get("case_id") or f"case-{_safe_sample_stem(sample_id)}")
        draft_path = f"regression-drafts/{_safe_case_stem(draft_id)}.json"
        source = detail.get("source") or {}
        regression_ready = bool(candidate["regression_ready"])
        if source.get("event_log_status") not in (None, "available"):
            regression_ready = False
            warnings.append(
                {
                    "sample_id": sample_id,
                    "reason": "EVENT_SEGMENT_UNAVAILABLE",
                    "source": source,
                }
            )

        debug_files[debug_path] = sanitize_debug_evidence(
            detail.get("debug_export")
            or {
                "source": source,
                "issue_candidates": detail.get("issue_candidates", []),
            }
        )
        regression_drafts[draft_path] = draft
        cases.append(
            {
                "sample_id": sample_id,
                "session_id": sample.get("session_id"),
                "turn_id": sample.get("turn_id"),
                "request_id": sample.get("request_id"),
                "labels": candidate["labels"],
                "fix_target": candidate["fix_target"],
                "priority": candidate["priority"],
                "suggested_action": candidate["suggested_action"],
                "regression_ready": regression_ready,
                "secondary_targets": candidate["secondary_targets"],
                "observed_failure": _observed_failure(detail),
                "expected_behavior": _expected_behavior(detail, candidate),
                "evidence": _collect_evidence(detail),
                "source_debug_json": debug_path,
                "regression_draft": draft_path,
                "source": source,
            }
        )

    labels = sorted(
        {label for candidate in candidates for label in candidate["labels"]}
    )
    verification_commands = _merge_commands(
        candidate["verification_commands"] for candidate in candidates
    )
    manifest = {
        "pack_id": pack_id,
        "export_path": export_path,
        "created_by": created_by,
        "fix_target": fix_target,
        "goal": _goal_for_target(fix_target),
        "labels": labels,
        "source_sample_ids": [str(candidate["sample_id"]) for candidate in candidates],
        "case_count": len(cases),
        "verification_commands": verification_commands,
        "warnings": warnings,
    }
    return {
        "manifest": manifest,
        "cases_jsonl": cases,
        "readme": build_repair_pack_readme(manifest),
        "debug_files": debug_files,
        "regression_drafts": regression_drafts,
    }


def _collect_labels(detail: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for label in detail.get("quality_labels") or []:
        labels.append(str(label))
    for row in detail.get("labels") or []:
        if isinstance(row, dict) and row.get("status", "open") != "resolved":
            label = row.get("label") or row.get("quality_label")
            if label:
                labels.append(str(label))
    for row in detail.get("prelabels") or []:
        if isinstance(row, dict) and row.get("status") in {
            "pending",
            "accepted",
            "open",
        }:
            labels.extend(str(label) for label in row.get("labels") or [])
    for item in detail.get("issue_candidates") or []:
        if isinstance(item, dict):
            label = item.get("suggested_label") or item.get("type")
            if label:
                labels.append(str(label))
    return list(dict.fromkeys(labels)) or ["manual_triage"]


def _route_for_label(label: str) -> dict[str, Any]:
    issue_type = _LABEL_TO_ISSUE_TYPE.get(label, label)
    meta = _ISSUE_TYPE_META.get(issue_type, _DEFAULT_ROUTE)
    return {"label": label, **meta}


def _override_candidate_fix_target(
    candidate: dict[str, Any], fix_target: str
) -> dict[str, Any]:
    original_target = str(candidate["fix_target"])
    updated = dict(candidate)
    secondary_targets = list(candidate.get("secondary_targets") or [])
    if original_target != fix_target:
        secondary_targets.insert(
            0,
            {
                "label": "manual_override_source",
                "fix_target": original_target,
                "priority": candidate["priority"],
            },
        )
    updated["fix_target"] = fix_target
    updated["suggested_action"] = f"按人工覆盖的 {fix_target} 修复目标处理该失败样本。"
    updated["verification_commands"] = _verification_commands(fix_target)
    updated["secondary_targets"] = secondary_targets
    return updated


def _is_regression_ready(detail: dict[str, Any]) -> bool:
    case_json = _explicit_case_json(detail)
    if not case_json:
        if _has_actionable_generated_assertions(detail):
            return True
        return False
    if case_json.get("expected_pending_action"):
        return True
    assertions = case_json.get("issue_assertions") or case_json.get("reply_assertions")
    return bool(assertions)


def _explicit_case_json(detail: dict[str, Any]) -> dict[str, Any] | None:
    draft = detail.get("case_draft") or {}
    if isinstance(draft, dict) and isinstance(draft.get("case_json"), dict):
        return draft["case_json"]
    if isinstance(detail.get("case_json"), dict):
        return detail["case_json"]
    return None


def _case_json(detail: dict[str, Any]) -> dict[str, Any]:
    explicit = _explicit_case_json(detail)
    if explicit is not None:
        return explicit
    return {
        "case_id": f"case-{_safe_sample_stem(_sample_id(detail))}",
        "metadata": {
            "source": "data_flywheel",
            "source_sample_id": _sample_id(detail),
            "quality_labels": _collect_labels(detail),
            "regression_stage": _regression_stage(detail),
        },
        "reply_assertions": _reply_assertions(detail),
        "issue_assertions": _issue_assertions(detail),
    }


def _issue_assertions(detail: dict[str, Any]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    for candidate in detail.get("issue_candidates") or []:
        if isinstance(candidate, dict) and candidate.get("type"):
            assertions.append(
                {
                    "type": candidate.get("type"),
                    "expected": _expected_for_issue(str(candidate.get("type")))
                    or candidate.get("reason")
                    or "",
                    "evidence": candidate.get("evidence") or "",
                    "stage": "assertion_generated",
                }
            )
    return assertions


def _has_actionable_generated_assertions(detail: dict[str, Any]) -> bool:
    issue_types = {
        str(candidate.get("type"))
        for candidate in detail.get("issue_candidates") or []
        if isinstance(candidate, dict) and candidate.get("type")
    }
    return bool(
        issue_types.intersection({"hallucinated_execution", "tool_error_ignored"})
        and _issue_assertions(detail)
    )


def _reply_assertions(detail: dict[str, Any]) -> list[dict[str, Any]]:
    issue_types = {
        str(candidate.get("type"))
        for candidate in detail.get("issue_candidates") or []
        if isinstance(candidate, dict) and candidate.get("type")
    }
    if not issue_types.intersection({"hallucinated_execution", "tool_error_ignored"}):
        return []
    return [
        {
            "not_contains_any": [
                "已为您记录",
                "已记录",
                "已创建",
                "已保存",
                "已执行",
            ],
            "stage": "pending_fix",
        }
    ]


def _regression_stage(detail: dict[str, Any]) -> str:
    if _issue_assertions(detail):
        return "assertion_generated"
    if _collect_labels(detail):
        return "issue_found"
    return "pending_fix"


def _expected_for_issue(issue_type: str | None) -> str | None:
    expected_by_type = {
        "disabled_worker_used": "停用或离职工人不得被安排到作业或工资记录中",
        "missing_wage": "包含工人的作业必须明确工资、已付金额、不计工资或欠款策略",
        "pending_missed": "写操作必须先创建 pending plan，用户确认后才能执行",
        "hallucinated_execution": "没有成功写工具调用时，回复不得声称已完成写入",
        "tool_error_ignored": "工具失败时回复必须说明失败或要求补充信息，不得伪装成功",
        "wrong_tool_selection": "router 必须选择与用户意图匹配的 skill",
    }
    return expected_by_type.get(issue_type)


def _verification_commands(fix_target: str) -> list[str]:
    return list(_VERIFY_BY_TARGET.get(fix_target, _VERIFY_BY_TARGET["manual_triage"]))


def _merge_commands(command_groups: Any) -> list[str]:
    commands: list[str] = []
    for group in command_groups:
        for command in group:
            if command not in commands:
                commands.append(command)
    return commands


def _sample_id(detail: dict[str, Any]) -> str:
    sample = detail.get("sample") or {}
    return str(sample.get("sample_id") or detail.get("sample_id") or "unknown")


def _safe_sample_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return stem or "unknown"


def _safe_case_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9-]+", "_", value).strip("_")
    return stem or "unknown"


def _observed_failure(detail: dict[str, Any]) -> str:
    """模板 reason + 具体证据（evidence 有区分度）。"""
    candidates = detail.get("issue_candidates") or []
    if not candidates:
        sample = detail.get("sample") or {}
        return str(sample.get("assistant_reply_preview") or "未提供失败描述")
    parts: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("reason") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if reason and evidence and evidence != reason:
            parts.append(f"{reason} | 证据：{evidence}")
        elif reason:
            parts.append(reason)
        elif evidence:
            parts.append(evidence)
    return "; ".join(parts) if parts else "未提供失败描述"


def _expected_behavior(detail: dict[str, Any], candidate: dict[str, Any]) -> str:
    """按 issue_type 的期望行为模板，避免与 observed_failure 复用同一段文字。"""
    candidates = detail.get("issue_candidates") or []
    mapped: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        issue_type = str(item.get("type") or "").strip()
        if issue_type and issue_type in _ISSUE_TYPE_META:
            mapped.append(str(_ISSUE_TYPE_META[issue_type]["expected_behavior"]))
    if mapped:
        # 去重保留顺序
        seen: set[str] = set()
        unique: list[str] = []
        for text in mapped:
            if text not in seen:
                seen.add(text)
                unique.append(text)
        return " ".join(unique)
    fix_target = str(candidate.get("fix_target") or "").strip()
    for meta in _ISSUE_TYPE_META.values():
        if meta.get("fix_target") == fix_target:
            return str(meta["expected_behavior"])
    return str(_DEFAULT_ROUTE["expected_behavior"])


def _collect_evidence(detail: dict[str, Any]) -> str:
    """收集所有候选的具体证据文本。"""
    candidates = detail.get("issue_candidates") or []
    evidence_list = [
        str(item.get("evidence")).strip()
        for item in candidates
        if isinstance(item, dict) and item.get("evidence")
    ]
    return " | ".join(evidence_list) if evidence_list else ""


def _goal_for_target(fix_target: str) -> str:
    goals = {
        "guardrail": "修复敏感信息泄露防护并补回归验证。",
        "pending_plan": "修复写操作确认计划和 pending lifecycle。",
        "tool_guardrail": "修复工具调用前后的业务 guardrail。",
        "domain_policy": "修复农事领域策略和数据完整性规则。",
        "tool_result_state": "修复工具结果状态传播和失败回复。",
        "router": "修复工具路由与意图识别。",
        "prompt_or_sft": "修复回复质量提示词或沉淀 SFT 候选。",
        "manual_triage": "人工分诊样本并确认修复目标。",
    }
    return goals.get(fix_target, goals["manual_triage"])


def _group_summary(samples: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        target: [_sample_id(detail) for detail in grouped]
        for target, grouped in group_samples_by_fix_target(samples).items()
    }
