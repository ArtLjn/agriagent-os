"""Agent Reflection 服务入口。"""

import time
from typing import Any
import logging

from langchain_core.messages import ToolMessage

from app.agent.reflector.checks import (
    check_no_tool_write_success_claim,
    check_pending_plan_consistency,
    check_required_tool_missing,
    check_tool_failure_success_reply,
    check_tool_failure_write_plan_reply,
    check_tool_result_final_contradiction,
    check_write_plan_consistency,
)
from app.agent.reflector.models import ReflectionDecision, ReflectionResult
from app.agent.reflector.models import (
    ReflectionIssue,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.agent.reflector.policy import ReflectionPolicy
from app.infra.pending_actions import PendingPlanStep
from app.infra.trace_collector import get_collector

logger = logging.getLogger(__name__)


class ReflectorService:
    """组合反思策略、规则检查和 trace 记录。"""

    def __init__(self, policy: ReflectionPolicy | None = None) -> None:
        from app.shared.config import settings

        config = settings.reflection
        self.policy = policy or ReflectionPolicy(
            enabled=config.enabled,
            pre_write_plan=config.pre_write_plan,
            pre_execution=config.pre_execution,
            post_tool_result=config.post_tool_result,
            fallback_guard=config.fallback_guard,
        )

    def check_write_plan(
        self,
        *,
        trigger: ReflectionTrigger,
        skill_name: str,
        params: dict[str, Any],
        confirmation_text: str,
        trace_metadata: dict[str, Any] | None = None,
    ) -> ReflectionResult:
        try:
            if not self.policy.should_run(
                trigger=trigger,
                selected_tools=[skill_name],
                tool_messages=[],
            ):
                return ReflectionResult.passed(
                    trigger,
                    reason="反思策略跳过。",
                    checks=["write_plan_consistency"],
                )
            return self._record(
                check_write_plan_consistency(
                    trigger=trigger,
                    skill_name=skill_name,
                    params=params,
                    confirmation_text=confirmation_text,
                ),
                trace_metadata=trace_metadata,
            )
        except Exception as exc:
            return self._record(
                self._fail_closed_result(
                    trigger=trigger,
                    check_name="write_plan_consistency",
                    error=exc,
                ),
                trace_metadata=trace_metadata,
            )

    def check_pending_plan(
        self,
        *,
        trigger: ReflectionTrigger,
        steps: list[PendingPlanStep],
        confirmation_text: str,
        trace_metadata: dict[str, Any] | None = None,
    ) -> ReflectionResult:
        try:
            if not self.policy.should_run(
                trigger=trigger,
                selected_tools=[step.tool_name for step in steps],
                tool_messages=[],
            ):
                return ReflectionResult.passed(
                    trigger,
                    reason="反思策略跳过。",
                    checks=["pending_plan_consistency"],
                )
            return self._record(
                check_pending_plan_consistency(
                    trigger=trigger,
                    steps=steps,
                    confirmation_text=confirmation_text,
                ),
                trace_metadata=trace_metadata,
            )
        except Exception as exc:
            return self._record(
                self._fail_closed_result(
                    trigger=trigger,
                    check_name="pending_plan_consistency",
                    error=exc,
                ),
                trace_metadata=trace_metadata,
            )

    @staticmethod
    def requires_tool_for_final_text(
        *,
        selected_tools: list[str],
        final_text: str,
    ) -> bool:
        result = check_required_tool_missing(
            selected_tools=selected_tools,
            tool_calls=[],
            final_text=final_text,
        )
        return result.decision == ReflectionDecision.REQUIRE_TOOL

    def check_tool_response(
        self,
        *,
        tool_messages: list[ToolMessage],
        final_text: str,
        selected_tools: list[str] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> ReflectionResult:
        try:
            result = self._run_tool_response_checks(
                tool_messages=tool_messages,
                final_text=final_text,
                selected_tools=selected_tools or [],
                tool_calls=tool_calls or [],
                trace_metadata=trace_metadata or {},
            )
            return self._record(result, trace_metadata=trace_metadata)
        except Exception as exc:
            result = self._tool_response_exception_result(exc)
            return self._record(result, trace_metadata=trace_metadata)

    def _run_tool_response_checks(
        self,
        *,
        tool_messages: list[ToolMessage],
        final_text: str,
        selected_tools: list[str],
        tool_calls: list[dict[str, Any]],
        trace_metadata: dict[str, Any],
    ) -> ReflectionResult:
        no_tool_result = check_no_tool_write_success_claim(
            user_message=str(trace_metadata.get("user_message") or ""),
            final_text=final_text,
            selected_tools=selected_tools,
            tool_messages=tool_messages,
            tool_calls=tool_calls,
            plan_draft=trace_metadata.get("plan_draft"),
            pending_created=trace_metadata.get("pending_created"),
        )
        if no_tool_result.decision != ReflectionDecision.PASS:
            return no_tool_result
        if not self.policy.should_run(
            trigger=ReflectionTrigger.POST_TOOL_RESULT,
            selected_tools=selected_tools,
            tool_messages=tool_messages,
        ):
            return ReflectionResult.passed(
                ReflectionTrigger.POST_TOOL_RESULT,
                reason="反思策略跳过。",
                checks=["tool_response_consistency"],
            )
        return _first_non_pass(
            check_tool_failure_success_reply(
                tool_messages=tool_messages,
                final_text=final_text,
            ),
            check_tool_failure_write_plan_reply(
                tool_messages=tool_messages,
                final_text=final_text,
                plan_draft=trace_metadata.get("plan_draft"),
                pending_created=trace_metadata.get("pending_created"),
            ),
            check_tool_result_final_contradiction(
                tool_messages=tool_messages,
                final_text=final_text,
            ),
            check_required_tool_missing(
                selected_tools=selected_tools,
                tool_calls=tool_calls,
                final_text=final_text,
            ),
        )

    def _record(
        self,
        result: ReflectionResult,
        *,
        trace_metadata: dict[str, Any] | None = None,
    ) -> ReflectionResult:
        if trace_metadata:
            result.metadata.update(trace_metadata)
        start = time.time()
        try:
            get_collector().record(
                node_type="reflection_check",
                node_name=result.trigger.value,
                input_data=result.metadata,
                output_data=result.to_trace_payload(),
                start_time=start,
                end_time=time.time(),
            )
        except Exception as exc:
            logger.warning("Reflection trace 记录失败 | error=%s", exc)
        return result

    @staticmethod
    def _fail_closed_result(
        *,
        trigger: ReflectionTrigger,
        check_name: str,
        error: Exception,
    ) -> ReflectionResult:
        message = "Reflection 检查异常，已按写操作 fail-closed 处理。"
        return ReflectionResult(
            trigger=trigger,
            decision=ReflectionDecision.BLOCK_WRITE,
            checks=[check_name],
            reason=message,
            issues=[
                ReflectionIssue(
                    code="reflection_check_failed",
                    severity=ReflectionSeverity.BLOCKER,
                    message=message,
                    evidence={"error": str(error)[:200]},
                    suggested_decision=ReflectionDecision.BLOCK_WRITE,
                )
            ],
        )

    @staticmethod
    def _tool_response_exception_result(exc: Exception) -> ReflectionResult:
        message = "Reflection 检查异常，只读/回复路径已降级放行。"
        return ReflectionResult(
            trigger=ReflectionTrigger.POST_TOOL_RESULT,
            decision=ReflectionDecision.PASS,
            reason=message,
            checks=["tool_response_consistency"],
            issues=[
                ReflectionIssue(
                    code="reflection_check_failed",
                    severity=ReflectionSeverity.WARNING,
                    message=message,
                    evidence={"error": str(exc)[:200]},
                    suggested_decision=ReflectionDecision.PASS,
                )
            ],
            metadata={"reflection_error": str(exc)[:200]},
        )


def _first_non_pass(*results: ReflectionResult) -> ReflectionResult:
    for result in results:
        if result.decision != ReflectionDecision.PASS:
            return result
    return results[-1]
