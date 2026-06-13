"""Skill trace 诊断服务。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillDiagnosticReport:
    """单次 Agent 请求诊断报告。"""

    request_id: str
    tool_selection: dict[str, Any] = field(default_factory=dict)
    context_injection: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    pending_actions: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    final_response: str = ""
    pending_lifecycle: list[dict[str, Any]] = field(default_factory=list)
    context_dependencies: list[dict[str, Any]] = field(default_factory=list)
    drilldown_links: dict[str, str] = field(default_factory=dict)
    tool_not_called_reason: str = ""
    pending_action_diagnostic: dict[str, Any] = field(default_factory=dict)
    context_dependency_diagnostic: list[dict[str, Any]] = field(default_factory=list)
    reflection_checks: list[dict[str, Any]] = field(default_factory=list)
    reflection_diagnostic: dict[str, Any] = field(default_factory=dict)


class SkillDiagnosticService:
    """从 trace records 汇总 Skill 执行诊断信息。"""

    def build_report(
        self, request_id: str, records: list[Any]
    ) -> SkillDiagnosticReport:
        report = SkillDiagnosticReport(request_id=request_id)
        ordered_records = sorted(records, key=lambda item: (item.round_index, item.id))
        for record in ordered_records:
            output_data = record.output_data or {}
            input_data = record.input_data or {}
            if record.node_type in {"tool_selection", "tool_selector"}:
                report.tool_selection = {
                    "node_name": record.node_name,
                    "input": input_data,
                    "output": output_data,
                }
            elif record.node_type == "context_build":
                report.context_injection = output_data
                report.context_dependencies = output_data.get(
                    "context_dependency_diagnostics", []
                )
            elif record.node_type == "skill_call":
                report.tool_calls.append(
                    {
                        "name": record.node_name,
                        "input": input_data,
                        "output": output_data,
                        "status": record.status,
                    }
                )
            elif record.node_type == "pending_action":
                event = self._pending_event(record)
                report.pending_actions.append(event)
                report.pending_lifecycle.append(event)
            elif record.node_type == "reflection_check":
                report.reflection_checks.append(self._reflection_event(record))
            elif record.node_type in {"final_response", "assistant_response"}:
                report.final_response = str(
                    output_data.get("reply")
                    or output_data.get("content")
                    or output_data
                    or ""
                )

            if record.status == "error" or record.error_message:
                report.errors.append(
                    {
                        "node_type": record.node_type,
                        "node_name": record.node_name,
                        "message": record.error_message or output_data.get("error"),
                    }
                )

        report.drilldown_links = self._build_drilldown_links(
            request_id, ordered_records
        )
        report.tool_not_called_reason = self._diagnose_tool_not_called(report)
        report.pending_action_diagnostic = self._diagnose_pending_action(report)
        report.context_dependency_diagnostic = self._diagnose_context_dependencies(
            report
        )
        report.reflection_diagnostic = self._diagnose_reflection(report)
        return report

    @staticmethod
    def _pending_event(record: Any) -> dict[str, Any]:
        output_data = record.output_data or {}
        input_data = record.input_data or {}
        status = output_data.get("status") or input_data.get("status") or record.status
        return {
            "node_name": record.node_name,
            "status": status,
            "input": input_data,
            "output": output_data,
            "structured_context": output_data.get("confirmation_context")
            or input_data.get("confirmation_context")
            or {},
        }

    @staticmethod
    def _reflection_event(record: Any) -> dict[str, Any]:
        output_data = record.output_data or {}
        input_data = record.input_data or {}
        return {
            "trigger": output_data.get("trigger") or record.node_name,
            "decision": output_data.get("decision", ""),
            "reason": output_data.get("reason", ""),
            "checks": output_data.get("checks") or [],
            "issues": output_data.get("issues") or [],
            "input": input_data,
        }

    @staticmethod
    def _build_drilldown_links(request_id: str, records: list[Any]) -> dict[str, str]:
        links = {"timeline": f"/admin/traces/{request_id}/timeline"}
        for record in records:
            key = f"{record.node_type}:{record.node_name}"
            links[key] = f"/admin/traces/{request_id}/nodes/{record.id}"
        return links

    @staticmethod
    def _diagnose_tool_not_called(report: SkillDiagnosticReport) -> str:
        """解释没有 skill_call 的常见原因。"""
        if report.tool_calls:
            return ""
        if not report.tool_selection:
            return "request_bypassed_agent_or_tool_selection_missing"

        output = report.tool_selection.get("output") or {}
        selected = output.get("selected_tools") or output.get("tools") or []
        excluded = output.get("excluded_tools") or output.get("filtered_out") or []
        if excluded:
            return "tool_selection_excluded_skill"
        if not selected:
            return "tool_selection_selected_no_skill"

        for error in report.errors:
            if "validation" in str(error.get("message", "")).lower():
                return "schema_validation_failed"
        return "llm_chose_not_to_call_tool"

    @staticmethod
    def _diagnose_pending_action(report: SkillDiagnosticReport) -> dict[str, Any]:
        """汇总 pending action 生命周期，并解释 pending 丢失的可能原因。"""
        statuses = [event.get("status") for event in report.pending_lifecycle]
        known_statuses = {
            "created",
            "replaced",
            "confirmed",
            "corrected",
            "canceled",
            "cancelled",
            "timed_out",
            "executed",
            "failed",
        }
        normalized = [status for status in statuses if status]
        missing = sorted(known_statuses - set(normalized))
        lost_reason = ""
        if any(status in {"timed_out", "timeout"} for status in normalized):
            lost_reason = "timed_out"
        elif any(status in {"replaced", "overwritten"} for status in normalized):
            lost_reason = "overwritten"
        elif any(status in {"canceled", "cancelled"} for status in normalized):
            lost_reason = "cancelled"
        elif not normalized and report.final_response:
            lowered = report.final_response.lower()
            if "没有待确认" in report.final_response or "no pending" in lowered:
                lost_reason = "backend_restarted_or_no_pending_action"

        return {
            "statuses": normalized,
            "missing_statuses": missing,
            "lost_reason": lost_reason,
            "cache_invalidation": SkillDiagnosticService._diagnose_cache_invalidation(
                report
            ),
        }

    @staticmethod
    def _diagnose_cache_invalidation(report: SkillDiagnosticReport) -> dict[str, Any]:
        """提取 pending action 执行后的缓存失效记录。"""
        groups: list[str] = []
        for event in report.pending_lifecycle:
            output = event.get("output") or {}
            metadata = output.get("metadata") or {}
            candidates = [
                output.get("cache_groups_cleared"),
                output.get("cache_invalidation"),
                metadata.get("cache_groups_cleared"),
                metadata.get("cache_invalidation"),
            ]
            for candidate in candidates:
                if isinstance(candidate, list):
                    groups.extend(str(group) for group in candidate if group)
                elif isinstance(candidate, str) and candidate:
                    groups.append(candidate)

        unique_groups = sorted(set(groups))
        return {
            "status": "recorded" if unique_groups else "not_recorded",
            "groups": unique_groups,
        }

    @staticmethod
    def _diagnose_reflection(report: SkillDiagnosticReport) -> dict[str, Any]:
        """汇总 reflection check 的阻断决策和 issue code。"""
        blocking_decisions = {
            "ask_clarification",
            "block_write",
            "require_tool",
        }
        decisions = sorted(
            {
                str(event.get("decision"))
                for event in report.reflection_checks
                if event.get("decision")
            }
        )
        issue_codes = sorted(
            {
                str(issue.get("code"))
                for event in report.reflection_checks
                for issue in event.get("issues", [])
                if isinstance(issue, dict) and issue.get("code")
            }
        )
        return {
            "blocked": any(decision in blocking_decisions for decision in decisions),
            "decisions": decisions,
            "issue_codes": issue_codes,
        }

    @staticmethod
    def _diagnose_context_dependencies(
        report: SkillDiagnosticReport,
    ) -> list[dict[str, Any]]:
        """把 ContextBundle 依赖状态转换为可读诊断。"""
        diagnostics = []
        seen_block_keys = set()
        for item in report.context_dependencies:
            status = item.get("status")
            if status == "selected":
                reason = "selected_by_skill_metadata"
            elif status == "compressed":
                reason = "selected_but_compressed_by_budget"
            elif status == "dropped":
                reason = "selected_but_dropped_by_budget"
            elif status == "unavailable":
                reason = "unavailable_in_database_or_selector"
            else:
                reason = "not_selected_by_context_policy"
            block_key = item.get("block_key")
            if block_key:
                seen_block_keys.add(block_key)
            diagnostics.append({**item, "diagnosis": reason})

        policy = report.context_injection.get("policy") or {}
        dependency_map = policy.get("context_dependency_map") or {}
        for block_key, dependencies in dependency_map.items():
            if block_key in seen_block_keys:
                continue
            diagnostics.append(
                {
                    "block_key": block_key,
                    "dependencies": dependencies,
                    "status": "not_selected",
                    "diagnosis": "not_selected_by_context_policy",
                }
            )
        return diagnostics


__all__ = ["SkillDiagnosticReport", "SkillDiagnosticService"]
