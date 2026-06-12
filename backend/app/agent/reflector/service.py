"""Agent Reflection 服务入口。"""

import time
from typing import Any
import logging

from langchain_core.messages import ToolMessage

from app.agent.reflector.checks import (
    check_pending_plan_consistency,
    check_required_tool_missing,
    check_tool_failure_success_reply,
    check_write_plan_consistency,
)
from app.agent.reflector.models import ReflectionDecision, ReflectionResult
from app.agent.reflector.models import ReflectionIssue, ReflectionSeverity, ReflectionTrigger
from app.agent.reflector.policy import ReflectionPolicy
from app.infra.pending_actions import PendingPlanStep
from app.infra.trace_collector import get_collector

logger = logging.getLogger(__name__)


class ReflectorService:
    """组合反思策略、规则检查和 trace 记录。"""

    def __init__(self, policy: ReflectionPolicy | None = None) -> None:
        from app.core.config import settings

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
            if not self.policy.should_run(
                trigger=ReflectionTrigger.POST_TOOL_RESULT,
                selected_tools=selected_tools or [],
                tool_messages=tool_messages,
            ):
                return ReflectionResult.passed(
                    ReflectionTrigger.POST_TOOL_RESULT,
                    reason="反思策略跳过。",
                    checks=["tool_response_consistency"],
                )
            failure_result = check_tool_failure_success_reply(
                tool_messages=tool_messages,
                final_text=final_text,
            )
            if failure_result.decision != ReflectionDecision.PASS:
                return self._record(failure_result, trace_metadata=trace_metadata)
            missing_tool_result = check_required_tool_missing(
                selected_tools=selected_tools or [],
                tool_calls=tool_calls or [],
                final_text=final_text,
            )
            return self._record(missing_tool_result, trace_metadata=trace_metadata)
        except Exception as exc:
            return ReflectionResult(
                trigger=ReflectionTrigger.POST_TOOL_RESULT,
                decision=ReflectionDecision.PASS,
                reason="Reflection 检查异常，只读/回复路径已降级放行。",
                checks=["tool_response_consistency"],
                issues=[
                    ReflectionIssue(
                        code="reflection_check_failed",
                        severity=ReflectionSeverity.WARNING,
                        message="Reflection 检查异常，只读/回复路径已降级放行。",
                        evidence={"error": str(exc)[:200]},
                        suggested_decision=ReflectionDecision.PASS,
                    )
                ],
                metadata={"reflection_error": str(exc)[:200]},
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
