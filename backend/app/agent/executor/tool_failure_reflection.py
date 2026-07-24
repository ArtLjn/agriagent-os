"""工具失败后的确定性修参反思。"""

from dataclasses import dataclass, field
from typing import Any, Literal

from app.agent.executor.pending_aliases import pending_alias_metadata
from app.infra.pending_action_presenter import build_confirm_message
from app.infra.trace_collector import get_collector

ToolFailureRepairAction = Literal["no_repair", "ask_repaired_confirmation"]

_MAX_REPAIR_ATTEMPTS = 1
_CATEGORY_OTHER_HINTS = ("膜", "大棚膜", "农资")


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
        repaired_params["category"] = _infer_category(repaired_params)
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


def _infer_category(params: dict[str, Any]) -> str:
    note = str(params.get("note") or "")
    if any(hint in note for hint in _CATEGORY_OTHER_HINTS):
        return "其他"
    return "其他"


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
