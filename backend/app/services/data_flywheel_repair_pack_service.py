from __future__ import annotations

import re
import hashlib
from typing import Any
from collections import defaultdict

from app.services.data_flywheel_repair_pack_readme import build_repair_pack_readme

REDACTED_SECRET = "[REDACTED_SECRET]"

# 按 issue_type 统一管理的元数据：fix_target / priority / suggested_action / expected_behavior
# 这里 key 既是 issue_type（来自 issue_detector），也覆盖可直接作为 label 的同名项。
_ISSUE_TYPE_META: dict[str, dict[str, Any]] = {
    "sensitive_info_leak": {
        "fix_target": "guardrail",
        "priority": 100,
        "suggested_action": "修复敏感信息输出拦截、回复审查和安全边界测试。",
        "expected_behavior": "回复不应包含模型参数、系统提示、密钥、token 等内部信息。",
    },
    "pending_missed": {
        "fix_target": "pending_plan",
        "priority": 90,
        "suggested_action": "修复写操作确认计划和多步骤 pending lifecycle。",
        "expected_behavior": "router 选择写操作工具时，应同步生成 pending plan，等待用户确认后再执行。",
    },
    "disabled_worker_used": {
        "fix_target": "tool_guardrail",
        "priority": 85,
        "suggested_action": "修复工具执行前后的停用工人校验和阻断规则。",
        "expected_behavior": "应跳过已停用工人，或主动提示用户「该工人已停用，是否继续」。",
    },
    "missing_wage": {
        "fix_target": "domain_policy",
        "priority": 80,
        "suggested_action": "补齐农事用工工资、已付、不计薪或欠款策略。",
        "expected_behavior": "安排作业时应同时确认工资策略（计薪金额/已付/不计薪/欠款），不应留下空白工资字段。",
    },
    "tool_error_ignored": {
        "fix_target": "tool_result_state",
        "priority": 78,
        "suggested_action": "修复工具失败状态传播，禁止失败后伪装成功。",
        "expected_behavior": "工具调用失败时，回复应明确反映失败状态，并给出后续建议，不应伪装为成功。",
    },
    "hallucinated_execution": {
        "fix_target": "tool_result_state",
        "priority": 78,
        "suggested_action": "修复未成功执行工具时的回复状态和完成声明。",
        "expected_behavior": "回复应基于工具实际返回结果，未调用成功写工具前不得声称已执行/已创建/已安排。",
    },
    "wrong_tool_selection": {
        "fix_target": "router",
        "priority": 75,
        "suggested_action": "修复意图识别、工具路由和候选 skill 选择规则。",
        "expected_behavior": "router 应正确识别用户意图，并选择匹配的查询/计算类工具（如 weather.query、worker.search、wage.list）。",
    },
    "unsafe_write_on_question": {
        "fix_target": "pending_plan",
        "priority": 88,
        "suggested_action": "修复查询/确认类问题下的写工具选择，应走 pending plan。",
        "expected_behavior": "查询/确认类问题应走查询链路，不应直接调用写操作工具；若需写入应先生成 pending plan 由用户确认。",
    },
    "bad_reply": {
        "fix_target": "prompt_or_sft",
        "priority": 50,
        "suggested_action": "修复回复提示词、拒答边界或后续 SFT 候选，不直接入训。",
        "expected_behavior": "回复应符合用户意图、信息准确、表述清晰，无幻觉、无拒答失衡。",
    },
    "off_topic": {
        "fix_target": "prompt_or_sft",
        "priority": 50,
        "suggested_action": "修复回复聚焦度、提示词约束或后续 SFT 候选，不直接入训。",
        "expected_behavior": "回复应聚焦于农场业务相关话题，对超范围请求应礼貌拒答或引导。",
    },
    "unclear_intent": {
        "fix_target": "prompt_or_sft",
        "priority": 40,
        "suggested_action": "优化意图澄清话术或补充 slot 追问逻辑。",
        "expected_behavior": "意图不明时应主动追问关键信息（人物/时间/对象/数量），不应直接执行或拒答。",
    },
    "needs_regression": {
        "fix_target": "manual_triage",
        "priority": 30,
        "suggested_action": "补齐回归用例并锁定预期行为。",
        "expected_behavior": "应有可复现的回归用例覆盖该路径，防止后续回归。",
    },
    "not_actionable": {
        "fix_target": "manual_triage",
        "priority": 20,
        "suggested_action": "人工确认是否需要进一步处理或归档。",
        "expected_behavior": "由人工确认归类，无自动修复预期。",
    },
}
_DEFAULT_ROUTE = {
    "fix_target": "manual_triage",
    "priority": 10,
    "suggested_action": "人工分诊该标签，导出前确认或覆盖修复目标。",
    "expected_behavior": "回复应符合业务规则、用户意图，且不暴露内部信息。",
}

# label → issue_type 路由：同名直接复用 meta；非 detector 产出的 label 也映射到合适的 issue_type。
# 留空（不在字典里）的 label 走 _DEFAULT_ROUTE。
_LABEL_TO_ISSUE_TYPE: dict[str, str] = {
    label: label for label in _ISSUE_TYPE_META
}

_VERIFY_BY_TARGET = {
    "guardrail": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "pending_plan": [
        "pytest tests/services/test_pending_plan_service.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "tool_guardrail": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "domain_policy": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "tool_result_state": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "router": [
        "pytest tests/services/test_data_flywheel_service.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "prompt_or_sft": [
        "pytest tests/services/test_data_flywheel_judge_service.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "manual_triage": [
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q"
    ],
}

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|access[_-]?key|token|secret|password|passwd|credential|"
    r"authorization|auth[_-]?token)",
    re.IGNORECASE,
)
_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?P<key>(?:[A-Z0-9_]*API[_-]?KEY|[A-Z0-9_]*TOKEN|SECRET|PASSWORD|"
    r"AUTHORIZATION|ACCESS[_-]?KEY))\s*=\s*(?P<value>[A-Za-z0-9._~:/+=-]+)",
    re.IGNORECASE,
)
_INLINE_SECRET_RE = re.compile(
    r"(?P<key>(?:api[_-]?key|token|secret|password|passwd|credential))"
    r"\s*[:=]\s*(?P<value>[A-Za-z0-9._~:/+=-]+)",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ADDRESS_RE = re.compile(
    r"[\u4e00-\u9fa5]{2,}(?:省|市|区|县|镇|乡|村|路|街|巷)"
    r"[\u4e00-\u9fa5A-Za-z0-9\-]{0,24}(?:号|栋|单元|室)?"
)


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


def sanitize_debug_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                _redacted_secret(item)
                if _is_secret_field(str(key))
                else sanitize_debug_evidence(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_debug_evidence(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


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
        },
        "issue_assertions": _issue_assertions(detail),
    }


def _issue_assertions(detail: dict[str, Any]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    for candidate in detail.get("issue_candidates") or []:
        if isinstance(candidate, dict) and candidate.get("type"):
            assertions.append(
                {
                    "type": candidate.get("type"),
                    "expected": candidate.get("reason") or "",
                    "evidence": candidate.get("evidence") or "",
                }
            )
    return assertions


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


def _is_secret_field(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key)) or ".env" in key.lower()


def _sanitize_text(value: str) -> str:
    text = _ASSIGNMENT_SECRET_RE.sub(_redact_match_secret, value)
    text = _INLINE_SECRET_RE.sub(_redact_match_secret, text)
    text = _PHONE_RE.sub(lambda match: _mask_phone(match.group(0)), text)
    return _ADDRESS_RE.sub(lambda match: _redacted_address(match.group(0)), text)


def _redact_match_secret(match: re.Match[str]) -> str:
    return f"{match.group('key')}={_redacted_secret(match.group('value'))}"


def _redacted_secret(value: Any) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"{REDACTED_SECRET}:{digest}"


def _redacted_address(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"[REDACTED_ADDRESS:{digest}]"


def _mask_phone(value: str) -> str:
    return f"{value[:3]}****{value[-4:]}"
