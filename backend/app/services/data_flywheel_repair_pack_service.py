from __future__ import annotations

import re
import hashlib
from collections import defaultdict
from typing import Any

REDACTED_SECRET = "[REDACTED_SECRET]"
_LABEL_ROUTES: dict[str, dict[str, Any]] = {
    "sensitive_info_leak": {
        "fix_target": "guardrail",
        "priority": 100,
        "suggested_action": "修复敏感信息输出拦截、回复审查和安全边界测试。",
    },
    "pending_missed": {
        "fix_target": "pending_plan",
        "priority": 90,
        "suggested_action": "修复写操作确认计划和多步骤 pending lifecycle。",
    },
    "disabled_worker_used": {
        "fix_target": "tool_guardrail",
        "priority": 85,
        "suggested_action": "修复工具执行前后的停用工人校验和阻断规则。",
    },
    "missing_wage": {
        "fix_target": "domain_policy",
        "priority": 80,
        "suggested_action": "补齐农事用工工资、已付、不计薪或欠款策略。",
    },
    "tool_error_ignored": {
        "fix_target": "tool_result_state",
        "priority": 78,
        "suggested_action": "修复工具失败状态传播，禁止失败后伪装成功。",
    },
    "hallucinated_execution": {
        "fix_target": "tool_result_state",
        "priority": 78,
        "suggested_action": "修复未成功执行工具时的回复状态和完成声明。",
    },
    "wrong_tool_selection": {
        "fix_target": "router",
        "priority": 75,
        "suggested_action": "修复意图识别、工具路由和候选 skill 选择规则。",
    },
    "bad_reply": {
        "fix_target": "prompt_or_sft",
        "priority": 50,
        "suggested_action": "修复回复提示词、拒答边界或后续 SFT 候选，不直接入训。",
    },
    "off_topic": {
        "fix_target": "prompt_or_sft",
        "priority": 50,
        "suggested_action": "修复回复聚焦度、提示词约束或后续 SFT 候选，不直接入训。",
    },
}
_DEFAULT_ROUTE = {
    "fix_target": "manual_triage",
    "priority": 10,
    "suggested_action": "人工分诊该标签，导出前确认或覆盖修复目标。",
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
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
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
    """从 sample detail 派生修复候选。"""
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
    """递归脱敏 debug evidence，同时保留原字段名。"""
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
    """按主修复目标分组，供混合目标拒绝时给出建议。"""
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
    """构建内存 repair pack payload，不负责写入磁盘。"""
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
                "source_debug_json": debug_path,
                "regression_draft": draft_path,
                "source": source,
            }
        )

    labels = sorted({label for candidate in candidates for label in candidate["labels"]})
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
        "readme": _build_readme(manifest),
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
        if isinstance(row, dict) and row.get("status") in {"pending", "accepted", "open"}:
            labels.extend(str(label) for label in row.get("labels") or [])
    for item in detail.get("issue_candidates") or []:
        if isinstance(item, dict):
            label = item.get("suggested_label") or item.get("type")
            if label:
                labels.append(str(label))
    return list(dict.fromkeys(labels)) or ["manual_triage"]


def _route_for_label(label: str) -> dict[str, Any]:
    route = _LABEL_ROUTES.get(label, _DEFAULT_ROUTE)
    return {"label": label, **route}


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
    updated["suggested_action"] = (
        f"按人工覆盖的 {fix_target} 修复目标处理该失败样本。"
    )
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
    candidates = detail.get("issue_candidates") or []
    reasons = [
        str(item.get("reason"))
        for item in candidates
        if isinstance(item, dict) and item.get("reason")
    ]
    if reasons:
        return "; ".join(reasons)
    sample = detail.get("sample") or {}
    return str(sample.get("assistant_reply_preview") or "未提供失败描述")


def _expected_behavior(detail: dict[str, Any], candidate: dict[str, Any]) -> str:
    case_json = _case_json(detail)
    assertions = case_json.get("issue_assertions") or []
    if assertions:
        expected = assertions[0].get("expected") if isinstance(assertions[0], dict) else None
        if expected:
            return str(expected)
    return str(candidate["suggested_action"])


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


def _build_readme(manifest: dict[str, Any]) -> str:
    commands = "\n".join(
        f"- `{command}`" for command in manifest["verification_commands"]
    )
    return f"""# Repair Pack {manifest["pack_id"]}

面向 vibecoding 的读取顺序：
1. 先读 `manifest.json`，确认 fix_target={manifest["fix_target"]} 和样本范围。
2. 再读 `cases.jsonl`，理解 observed_failure、expected_behavior 和回归准备状态。
3. 按需读取 `debug/` 中脱敏证据和 `regression-drafts/` 中草稿断言。

修复步骤：
1. 先复现或补回归测试，优先使用 regression draft 中的断言。
2. 只围绕当前 fix_target 做最小范围修复，不修改无关 API、模型、迁移或前端。
3. 禁止把 bad reply 直接作为训练数据使用；如需 SFT，只能作为候选并经人工审核。
4. 运行 manifest 中的验证命令。

验证命令：
{commands}

完成回报格式：
- 修复目标
- 改动文件
- 新增或更新的回归测试
- 验证命令和结果
- 剩余风险或需要人工确认的样本
"""


def _group_summary(samples: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        target: [_sample_id(detail) for detail in grouped]
        for target, grouped in group_samples_by_fix_target(samples).items()
    }


def _is_secret_field(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key)) or ".env" in key.lower()


def _sanitize_text(value: str) -> str:
    text = _ASSIGNMENT_SECRET_RE.sub(
        lambda match: f"{match.group('key')}={_redacted_secret(match.group('value'))}", value
    )
    text = _INLINE_SECRET_RE.sub(
        lambda match: f"{match.group('key')}={_redacted_secret(match.group('value'))}", text
    )
    text = _PHONE_RE.sub(lambda match: _mask_phone(match.group(0)), text)
    text = _ADDRESS_RE.sub(lambda match: _redacted_address(match.group(0)), text)
    return text


def _redacted_secret(value: Any) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"{REDACTED_SECRET}:{digest}"


def _redacted_address(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"[REDACTED_ADDRESS:{digest}]"


def _mask_phone(value: str) -> str:
    return f"{value[:3]}****{value[-4:]}"
