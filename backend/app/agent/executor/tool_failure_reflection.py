"""工具失败后的确定性修参反思。"""

from dataclasses import dataclass, field
from typing import Any, Literal

from app.agent.executor.pending_aliases import pending_alias_metadata
from app.infra.pending_action_presenter import build_confirm_message
from app.infra.trace_collector import get_collector
from app.skills.candidates import load_skill_candidates

ToolFailureRepairAction = Literal["no_repair", "ask_repaired_confirmation"]

_MAX_REPAIR_ATTEMPTS = 1
_CATEGORY_CONSOLIDATION_RULES = (
    (
        ("大棚膜", "地膜", "棚膜", "薄膜", "防虫网", "遮阳网", "滴灌带", "水管"),
        ("农资", "设施耗材", "农用耗材", "耗材", "其他农资", "材料"),
    ),
    (
        ("化肥", "肥料", "复合肥", "有机肥", "尿素"),
        ("化肥", "肥料"),
    ),
    (
        ("种子", "种苗", "瓜苗", "苗盘"),
        ("种子", "种苗"),
    ),
    (
        ("农药", "杀虫剂", "杀菌剂", "除草剂"),
        ("农药",),
    ),
)


@dataclass(frozen=True)
class ToolFailureRepairDecision:
    """工具失败反思的修复决策。"""

    action: ToolFailureRepairAction
    reason: str
    reply: str = ""
    repaired_params: dict[str, Any] | None = None
    confirmation_text: str = ""
    repair_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def trace_payload(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "repair_attempts": self.repair_attempts,
            "repaired_params": self.repaired_params or {},
            **self.metadata,
        }


def reflect_tool_failure(
    *,
    farm_id: int,
    skill_name: str,
    params: dict[str, Any],
    result,
    repair_attempts: int = 0,
    original_input: str = "",
    session_id: str | None = None,
) -> ToolFailureRepairDecision:
    """识别无副作用失败并生成需要用户确认的修复 pending。"""
    reply = str(getattr(result, "reply", "") or result or "")
    alias_metadata = _safe_alias_metadata(skill_name, params)
    if repair_attempts >= _MAX_REPAIR_ATTEMPTS:
        decision = ToolFailureRepairDecision(
            action="no_repair",
            reason="repair_attempt_limit_reached",
            repair_attempts=repair_attempts,
            metadata=alias_metadata,
        )
        _record_trace(farm_id, skill_name, params, reply, decision, session_id)
        return decision

    if _is_manage_cost_missing_category(skill_name, params, reply, alias_metadata):
        repaired_params = dict(params)
        category, category_strategy = _infer_category(
            farm_id=farm_id,
            params=repaired_params,
            original_input=original_input,
        )
        repaired_params["category"] = category
        next_attempts = repair_attempts + 1
        confirmation_text = build_confirm_message(
            skill_name,
            repaired_params,
            original_input=original_input,
        )
        decision = ToolFailureRepairDecision(
            action="ask_repaired_confirmation",
            reason="manage_cost_missing_category_repaired",
            reply=reply,
            repaired_params=repaired_params,
            confirmation_text=confirmation_text,
            repair_attempts=next_attempts,
            metadata={
                **alias_metadata,
                "tool_failure_repair": {
                    "field": "category",
                    "value": repaired_params["category"],
                    "strategy": category_strategy,
                },
            },
        )
        _record_trace(farm_id, skill_name, params, reply, decision, session_id)
        return decision

    decision = ToolFailureRepairDecision(
        action="no_repair",
        reason="no_matching_repair_rule",
        repair_attempts=repair_attempts,
        metadata=alias_metadata,
    )
    _record_trace(farm_id, skill_name, params, reply, decision, session_id)
    return decision


def _is_manage_cost_missing_category(
    skill_name: str,
    params: dict[str, Any],
    reply: str,
    alias_metadata: dict[str, Any],
) -> bool:
    capability = alias_metadata.get("resolved_capability") or skill_name
    operation = params.get("operation") or alias_metadata.get("resolved_operation")
    return (
        capability == "manage_cost"
        and operation == "create_record"
        and "分类不能为空" in reply
        and params.get("amount") not in (None, "")
        and params.get("record_type") not in (None, "")
    )


def _infer_category(
    *,
    farm_id: int,
    params: dict[str, Any],
    original_input: str,
) -> tuple[str, str]:
    text = " ".join(
        str(value)
        for value in (
            params.get("note"),
            params.get("description"),
            original_input,
        )
        if value not in (None, "")
    )
    categories = _load_category_candidates(farm_id)
    for category in _matched_categories(categories, text):
        return category, "dynamic_exact_match"
    for category in _consolidated_categories(categories, text):
        return category, "dynamic_consolidation"
    return "其他", "fallback_other"


def _load_category_candidates(farm_id: int) -> list[str]:
    try:
        categories = load_skill_candidates(farm_id).values.get("category") or []
    except Exception:
        return []
    return [str(category).strip() for category in categories if category]


def _matched_categories(categories: list[str], text: str) -> list[str]:
    if not text:
        return []
    candidates = [
        category for category in categories if category and category != "其他"
    ]
    return sorted(
        (category for category in candidates if category in text),
        key=len,
        reverse=True,
    )


def _consolidated_categories(categories: list[str], text: str) -> list[str]:
    if not text:
        return []
    available = {category for category in categories if category and category != "其他"}
    matches: list[str] = []
    for item_terms, category_terms in _CATEGORY_CONSOLIDATION_RULES:
        if not any(term in text for term in item_terms):
            continue
        for category in category_terms:
            if category in available and category not in matches:
                matches.append(category)
    return matches


def _safe_alias_metadata(skill_name: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        return pending_alias_metadata(skill_name, params)
    except ValueError:
        return {
            "legacy_tool_name": skill_name,
            "alias_resolution": "missing",
        }


def _record_trace(
    farm_id: int,
    skill_name: str,
    params: dict[str, Any],
    reply: str,
    decision: ToolFailureRepairDecision,
    session_id: str | None,
) -> None:
    get_collector().record(
        node_type="reflection_check",
        node_name="tool_failure_repair",
        input_data={
            "farm_id": farm_id,
            "session_id": session_id,
            "skill_name": skill_name,
            "params": params,
            "failure_reply": reply[:500],
        },
        output_data=decision.trace_payload(),
        duration_ms=0,
    )
