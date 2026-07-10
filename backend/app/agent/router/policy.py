"""Skill Router stop-loss policy。"""

from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)


class RouterPolicy:
    """对候选工具应用 stop-loss、写入和 schema 预算。"""

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
        candidate_by_name = {
            candidate.name: candidate for candidate in candidates if candidate.enabled
        }

        if self._has_ambiguous_write(frames):
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="clarify_write_intent",
                reason="写入意图不明确，需要先澄清",
                clarification="请补充要处理的对象、动作和必要信息。",
            )

        farm_labor_clarification = self._farm_labor_clarification(frames)
        if farm_labor_clarification is not None:
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="clarify_farm_labor_work",
                reason="农事用工输入缺少关键字段，需要先澄清",
                clarification=farm_labor_clarification,
            )

        requested_names = self._collect_candidate_names(frames)
        if not requested_names:
            general_read = self._model_choice_read_decision(message, candidate_by_name)
            if general_read is not None:
                return general_read
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="no_tools",
                reason="未匹配到可用工具",
            )

        max_tools = self._max_tools_for_frames(frames)
        selected: list[ToolCandidate] = []
        rejected_tools: list[str] = []
        policy_violations: list[str] = []
        write_count = 0
        schema_token_estimate = 0

        for name in requested_names:
            candidate = candidate_by_name.get(name)
            if candidate is None:
                rejected_tools.append(name)
                continue

            if len(selected) >= max_tools:
                rejected_tools.append(candidate.name)
                continue

            if candidate.risk.startswith("write"):
                if write_count >= self._budget.max_write_tools:
                    rejected_tools.append(candidate.name)
                    self._append_violation(
                        policy_violations, "write_tool_budget_exceeded"
                    )
                    continue

            next_tokens = schema_token_estimate + candidate.schema_token_estimate
            if next_tokens > self._budget.max_schema_tokens:
                rejected_tools.append(candidate.name)
                self._append_violation(
                    policy_violations, "schema_token_budget_exceeded"
                )
                continue

            selected.append(candidate)
            schema_token_estimate = next_tokens
            if candidate.risk.startswith("write"):
                write_count += 1

        context_dependencies = self._dedupe_context_dependencies(selected, frames)

        return RouterDecision(
            frames=frames,
            selected_tools=[candidate.name for candidate in selected],
            context_dependencies=context_dependencies,
            reason="按意图候选和 stop-loss policy 选择工具",
            rejected_tools=rejected_tools,
            schema_token_estimate=schema_token_estimate,
            policy_violations=policy_violations,
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
            if candidate.risk == "read"
        ]
        if not selected:
            return None
        frame = IntentFrame(
            domain="general",
            intent="model_choice_read",
            risk="read",
            entities=["query"],
            candidate_tools=[],
            confidence=0.55,
        )
        return RouterDecision(
            frames=[frame],
            selected_tools=[candidate.name for candidate in selected],
            context_dependencies=self._dedupe_context_dependencies(selected, [frame]),
            fallback="model_choice_read_default",
            reason="无显式规则候选时交给主模型在只读工具池中选择",
            schema_token_estimate=sum(
                candidate.schema_token_estimate for candidate in selected
            ),
        )

    def _max_tools_for_frames(self, frames: list[IntentFrame]) -> int:
        if len(frames) > 1:
            return self._budget.max_tools_complex
        return self._budget.max_tools_default

    @staticmethod
    def _has_ambiguous_write(frames: list[IntentFrame]) -> bool:
        return any(frame.intent == "ambiguous_write" for frame in frames)

    @staticmethod
    def _farm_labor_clarification(frames: list[IntentFrame]) -> str | None:
        for frame in frames:
            if frame.intent != "clarify_farm_labor_work":
                continue
            if "operation_type" in frame.missing_fields:
                return "请补充要记录的作业类型，例如压瓜、压蔓、采收或授粉。"
        return None

    @staticmethod
    def _collect_candidate_names(frames: list[IntentFrame]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for frame in frames:
            for name in frame.candidate_tools:
                if name in seen:
                    continue
                names.append(name)
                seen.add(name)
        return names

    def _dedupe_context_dependencies(
        self,
        selected: list[ToolCandidate],
        frames: list[IntentFrame],
    ) -> list[str]:
        dependencies: list[str] = []
        for candidate in selected:
            dependencies.extend(candidate.context_dependencies)
        for frame in frames:
            dependencies.extend(frame.depends_on)
        return self._dedupe(dependencies)

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            deduped.append(item)
            seen.add(item)
        return deduped

    @staticmethod
    def _append_violation(violations: list[str], violation: str) -> None:
        if violation not in violations:
            violations.append(violation)

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
