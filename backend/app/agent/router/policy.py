"""Skill Router stop-loss policy。"""

from dataclasses import replace

from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)
from app.agent.router.policy_selection import (
    SelectionState,
    candidate_frame_map,
    collect_candidate_names,
    dedupe_context_dependencies,
    reject_candidate,
    schema_budget_exceeded,
    select_candidate,
    trim_candidates_by_budget,
    with_violation,
    write_budget_exceeded,
)
from app.agent.router.policy_trace import (
    decision_evidence,
    selected_operations,
    trace_scores,
)


class RouterPolicy:
    """对候选工具应用 stop-loss、读写隔离和 schema 预算。"""

    _no_tool_prefixes = ("你好", "您好", "hello", "hi", "nihao", "ni hao")
    _no_tool_hints = (
        "为什么",
        "如何",
        "检查",
        "排查",
        "审查",
        "随便聊",
        "闲聊",
        "聊聊",
    )
    _write_action_hints = (
        "买",
        "卖",
        "采购",
        "购入",
        "销售",
        "新增",
        "添加",
        "创建",
        "记录",
        "记一笔",
        "删除",
        "删掉",
        "修改",
        "更新",
        "安排",
        "支付",
        "结算",
    )
    _query_hints = (
        "什么",
        "哪些",
        "有哪些",
        "看看",
        "查询",
        "查一下",
        "最近",
        "怎么样",
        "多少",
        "统计",
        "汇总",
        "列表",
        "明细",
    )

    def __init__(self, budget: DisclosureBudget | None = None) -> None:
        self._budget = budget or DisclosureBudget()

    def apply(
        self,
        message: str,
        frames: list[IntentFrame],
        candidates: list[ToolCandidate],
    ) -> RouterDecision:
        candidate_by_name = {candidate.name: candidate for candidate in candidates}

        if self._has_ambiguous_write(frames):
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="clarify_write_intent",
                fallback_reason="ambiguous_write",
                reason="写入意图不明确，需要先澄清",
                clarification="请补充要处理的对象、动作和必要信息。",
                scores=trace_scores(frames, []),
            )

        farm_labor_clarification = self._farm_labor_clarification(frames)
        if farm_labor_clarification is not None:
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="clarify_farm_labor_work",
                fallback_reason="missing_farm_labor_fields",
                reason="农事用工输入缺少关键字段，需要先澄清",
                clarification=farm_labor_clarification,
                scores=trace_scores(frames, []),
            )

        requested_names = collect_candidate_names(frames)
        if not requested_names:
            return self._route_without_requested_tools(
                message,
                frames,
                candidate_by_name,
            )

        return self._route_requested_tools(
            frames,
            candidate_by_name,
            requested_names,
        )

    def _route_without_requested_tools(
        self,
        message: str,
        frames: list[IntentFrame],
        candidate_by_name: dict[str, ToolCandidate],
    ) -> RouterDecision:
        if self._has_write_frame(frames):
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="clarify_write_intent",
                fallback_reason="unknown_write_target",
                reason="写入意图缺少明确 domain 或 capability",
                clarification="请补充要处理的对象、动作和必要信息。",
                scores=trace_scores(frames, []),
            )
        general_read = self._model_choice_read_decision(message, candidate_by_name)
        if general_read is not None:
            return general_read
        return RouterDecision(
            frames=frames,
            selected_tools=[],
            fallback="no_tools",
            fallback_reason="no_candidate_tools",
            reason="未匹配到可用工具",
            scores=trace_scores(frames, []),
        )

    def _route_requested_tools(
        self,
        frames: list[IntentFrame],
        candidate_by_name: dict[str, ToolCandidate],
        requested_names: list[str],
    ) -> RouterDecision:
        max_tools = self._max_tools_for_frames(frames)
        state = SelectionState()
        frame_by_name = candidate_frame_map(frames)

        for name in requested_names:
            decision = self._handle_requested_name(
                name,
                frames,
                candidate_by_name,
                frame_by_name,
                max_tools,
                state,
            )
            if decision is not None:
                return decision

        return self._selected_decision(frames, state)

    def _handle_requested_name(
        self,
        name: str,
        frames: list[IntentFrame],
        candidate_by_name: dict[str, ToolCandidate],
        frame_by_name: dict[str, IntentFrame],
        max_tools: int,
        state: SelectionState,
    ) -> RouterDecision | None:
        candidate = candidate_by_name.get(name)
        if candidate is None:
            reject_candidate(state, name, "candidate_not_found", None)
            return None
        candidate = self._candidate_for_frame(candidate, frame_by_name.get(name))

        reject_reason = self._candidate_reject_reason(
            candidate,
            frame_by_name.get(name),
            max_tools,
            state,
        )
        if reject_reason is not None:
            reason, violation = reject_reason
            reject_candidate(state, candidate.name, reason, candidate, violation)
            if reason == "high_risk_clarify":
                return self._high_risk_decision(frames, state)
            return None

        select_candidate(state, candidate)
        return None

    @staticmethod
    def _candidate_for_frame(
        candidate: ToolCandidate,
        frame: IntentFrame | None,
    ) -> ToolCandidate:
        if frame is None or not frame.operation:
            return candidate
        if candidate.capability and frame.capability != candidate.capability:
            return candidate
        return replace(
            candidate,
            operation=frame.operation,
            operation_risk=frame.risk,
            risk=frame.risk,
        )

    def _candidate_reject_reason(
        self,
        candidate: ToolCandidate,
        frame: IntentFrame | None,
        max_tools: int,
        state: SelectionState,
    ) -> tuple[str, str | None] | None:
        if not candidate.enabled:
            return "disabled", "disabled_candidate_rejected"
        if frame is not None and self._is_read_write_mismatch(frame, candidate):
            return "read_intent_write_operation", "read_write_risk_mismatch"
        if candidate.risk == "write_high":
            return "high_risk_clarify", None
        if len(state.selected) >= max_tools:
            return "tool_budget_exceeded", None
        if write_budget_exceeded(candidate, state, self._budget):
            return "write_tool_budget_exceeded", "write_tool_budget_exceeded"
        if schema_budget_exceeded(candidate, state, self._budget):
            return "schema_token_budget_exceeded", "schema_token_budget_exceeded"
        return None

    def _selected_decision(
        self,
        frames: list[IntentFrame],
        state: SelectionState,
    ) -> RouterDecision:
        context_dependencies = dedupe_context_dependencies(
            state.selected,
            frames,
        )

        return RouterDecision(
            frames=frames,
            selected_tools=[candidate.name for candidate in state.selected],
            selected_operations=selected_operations(state.selected),
            context_dependencies=context_dependencies,
            reason="按意图候选和 stop-loss policy 选择工具",
            rejected_tools=state.rejected_tools,
            rejected_candidates=state.rejected_candidates,
            schema_token_estimate=state.schema_token_estimate,
            policy_violations=state.policy_violations,
            scores=trace_scores(frames, state.selected),
            evidence=decision_evidence(
                frames,
                state.selected,
                state.rejected_candidates,
            ),
        )

    def _high_risk_decision(
        self,
        frames: list[IntentFrame],
        state: SelectionState,
    ) -> RouterDecision:
        return RouterDecision(
            frames=frames,
            selected_tools=[],
            fallback="clarify_high_risk_operation",
            fallback_reason="high_risk_operation",
            reason="高风险写入操作需要先澄清",
            rejected_tools=state.rejected_tools,
            rejected_candidates=state.rejected_candidates,
            policy_violations=with_violation(
                state.policy_violations,
                "high_risk_clarification_required",
            ),
            clarification="这是高风险操作，请补充确认对象、影响范围和执行原因。",
            scores=trace_scores(frames, state.selected),
            evidence=decision_evidence(
                frames,
                state.selected,
                state.rejected_candidates,
            ),
        )

    def _model_choice_read_decision(
        self,
        message: str,
        candidate_by_name: dict[str, ToolCandidate],
    ) -> RouterDecision | None:
        if self._looks_like_no_tool_message(message):
            return None
        selected = [
            candidate
            for candidate in candidate_by_name.values()
            if candidate.risk == "read" and candidate.enabled
        ]
        if not selected:
            return None
        selected = trim_candidates_by_budget(
            selected,
            self._budget,
            self._budget.max_tools_default,
        )
        frame = IntentFrame(
            domain="general",
            intent="model_choice_read",
            risk="read",
            entities=["query"],
            candidate_tools=[],
            confidence=0.55,
            evidence={
                "fallback_reason": "no_explicit_candidate",
                "candidate_count": len(selected),
            },
        )
        return RouterDecision(
            frames=[frame],
            selected_tools=[candidate.name for candidate in selected],
            selected_operations=selected_operations(selected),
            context_dependencies=dedupe_context_dependencies(selected, [frame]),
            fallback="model_choice_read_default",
            fallback_reason="no_explicit_candidate",
            reason="无显式规则候选时交给主模型在只读工具池中选择",
            schema_token_estimate=sum(
                candidate.schema_token_estimate for candidate in selected
            ),
            scores=trace_scores([frame], selected),
            evidence=decision_evidence([frame], selected, []),
        )

    def _max_tools_for_frames(self, frames: list[IntentFrame]) -> int:
        if len(frames) > 1:
            return self._budget.max_tools_complex
        return self._budget.max_tools_default

    @staticmethod
    def _has_ambiguous_write(frames: list[IntentFrame]) -> bool:
        return any(frame.intent == "ambiguous_write" for frame in frames)

    @staticmethod
    def _has_write_frame(frames: list[IntentFrame]) -> bool:
        return any(frame.risk.startswith("write") for frame in frames)

    @staticmethod
    def _farm_labor_clarification(frames: list[IntentFrame]) -> str | None:
        for frame in frames:
            if frame.intent != "clarify_farm_labor_work":
                continue
            if "operation_type" in frame.missing_fields:
                return "请补充要记录的作业类型，例如压瓜、压蔓、采收或授粉。"
        return None

    @staticmethod
    def _is_read_write_mismatch(
        frame: IntentFrame,
        candidate: ToolCandidate,
    ) -> bool:
        return frame.risk == "read" and candidate.risk.startswith("write")

    def _looks_like_no_tool_message(self, message: str) -> bool:
        normalized = message.strip().lower()
        if not normalized:
            return True
        if "怎么" in normalized and "怎么样" not in normalized:
            return True
        if self._has_any(normalized, self._write_action_hints) and not self._has_any(
            normalized, self._query_hints
        ):
            return True
        return normalized.startswith(self._no_tool_prefixes) or self._has_any(
            normalized, self._no_tool_hints
        )

    @staticmethod
    def _has_any(message: str, hints: tuple[str, ...]) -> bool:
        return any(hint in message for hint in hints)
