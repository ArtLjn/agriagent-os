"""Tool 预筛选模块 — 三层过滤器（regex + keyword + LLM intent）缩小 LLM 候选工具集。"""

import logging
import time
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool
from openai import OpenAI

from app.agent.router.service import SkillRouter
from app.agent.tool_selection_rules import (
    DISABLED_SKILLS,
    PLANTING_ADVICE_HINTS,
    QUERY_INTENT_FORCE_BINDING,
    QUERY_INTENT_HINTS,
    QUERY_TRIGGERS,
    TOOL_CHAIN_MAP,
    WRITE_INTENT_HINTS,
    WRITE_PATTERNS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSelectionResult:
    """select_tools 返回结构。

    `tools` 是候选工具名集合（含强制绑定），按字典序排列。
    `force_binding` 是被 Rule Gate 强制绑定的工具子集，必须被 LLM 调用，
    应在 LLM 调用时设 `tool_choice=required`。

    保留 list 兼容语义（迭代、长度、索引、in、与 list 比较），方便旧调用方平滑迁移。
    """

    tools: list[str] = field(default_factory=list)
    force_binding: frozenset[str] = field(default_factory=frozenset)

    def __iter__(self):
        return iter(self.tools)

    def __len__(self) -> int:
        return len(self.tools)

    def __contains__(self, item) -> bool:
        return item in self.tools

    def __getitem__(self, index):
        return self.tools[index]

    def __eq__(self, other) -> bool:
        if isinstance(other, ToolSelectionResult):
            return (
                self.tools == other.tools
                and self.force_binding == other.force_binding
            )
        if isinstance(other, list):
            return self.tools == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash((tuple(self.tools), self.force_binding))


_DEBT_SUMMARY_QUERY_HINTS = (
    "还欠",
    "欠多少",
    "多少钱",
    "统计",
    "汇总",
    "查询",
    "查看",
    "看看",
    "看一下",
    "明细",
    "列表",
)

_COST_RECORD_DEBT_WRITE_HINTS = (
    "买",
    "采购",
    "购入",
    "卖",
    "销售",
    "花了",
    "收入",
    "支出",
    "记账",
    "记一笔",
    "付了",
    "收了",
)


class LLMIntentClassifier:
    """Layer 3 — LLM 意图分类兜底。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 5.0,
        provider: str = "config.yaml",
        role: str = "tool-selection",
    ):
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=3,
        )
        self._model = model
        self._provider = provider
        self._role = role

    def classify(
        self, user_message: str, all_tools: list[BaseTool]
    ) -> list[str] | None:
        tool_lines = []
        for t in all_tools:
            desc = (getattr(t, "description", "") or "")[:100]
            tool_lines.append(f"- {t.name}: {desc}")
        tool_descriptions = "\n".join(tool_lines)
        tool_names = [t.name for t in all_tools]

        prompt = (
            "You are an intent classifier. Given the user message below, "
            "determine which tool best matches the user's intent.\n"
            "Reply with ONLY the tool name, or 'none' if no tool matches.\n\n"
            f"Available tools:\n{tool_descriptions}\n\n"
            f"Tool names: {', '.join(tool_names)}\n\n"
            f"User message: {user_message}\n"
            "Matched tool name:"
        )

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            content = (response.choices[0].message.content or "").strip().lower()

            if content == "none":
                logger.info(
                    (
                        "tool_select LLM intent | provider=%s | model=%s | role=%s | "
                        "input=%r | raw=%r | matched=[] | latency_ms=%d"
                    ),
                    self._provider,
                    self._model,
                    self._role,
                    user_message[:80],
                    content,
                    latency_ms,
                )
                return []

            matched = None
            for name in tool_names:
                if name == content:
                    matched = [name]
                    break

            logger.info(
                (
                    "tool_select LLM intent | provider=%s | model=%s | role=%s | "
                    "input=%r | raw=%r | matched=%s | latency_ms=%d"
                ),
                self._provider,
                self._model,
                self._role,
                user_message[:80],
                content,
                matched,
                latency_ms,
            )
            return matched
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                (
                    "tool_select LLM intent failed | provider=%s | model=%s | "
                    "role=%s | input=%r | latency_ms=%d | error=%s: %s"
                ),
                self._provider,
                self._model,
                self._role,
                user_message[:80],
                latency_ms,
                type(e).__name__,
                e,
            )
            return None


def _tool_enabled(tool: BaseTool) -> bool:
    metadata = getattr(tool, "skill_metadata", None)
    enabled = getattr(metadata, "enabled", None)
    if isinstance(enabled, bool):
        return enabled
    return tool.name not in DISABLED_SKILLS


def _debt_summary_should_yield_to_cost_record(
    user_message: str,
    *,
    has_write_intent: bool,
    has_query_intent: bool,
) -> bool:
    if has_query_intent or any(
        hint in user_message for hint in _DEBT_SUMMARY_QUERY_HINTS
    ):
        return False
    return has_write_intent or any(
        hint in user_message for hint in _COST_RECORD_DEBT_WRITE_HINTS
    )


def select_tools(
    user_message: str,
    all_tools: list[BaseTool],
    top_k: int = 3,
    intent_classifier: LLMIntentClassifier | None = None,
) -> ToolSelectionResult:
    # 过滤掉禁用的 skill
    all_tools = [t for t in all_tools if _tool_enabled(t)]
    enabled_tool_names = {t.name for t in all_tools}
    candidates: set[str] = set()
    force_binding: set[str] = set()
    is_planting_advice = any(hint in user_message for hint in PLANTING_ADVICE_HINTS)
    has_write_intent = any(hint in user_message for hint in WRITE_INTENT_HINTS)
    has_query_intent = any(hint in user_message for hint in QUERY_INTENT_HINTS)
    has_labor_hint = any(hint in user_message for hint in ("人工", "工钱", "工资"))

    # 强制绑定识别（在所有 difference_update 之前）
    # 见 13_Agent范式规范化设计.md §5.9.3：查询型意图命中时对应 Skill 必须保留并设 tool_choice=required
    for intent, skill_names in QUERY_INTENT_FORCE_BINDING.items():
        if intent in user_message:
            for skill_name in skill_names:
                if skill_name in enabled_tool_names:
                    candidates.add(skill_name)
                    force_binding.add(skill_name)

    for tool_name, patterns in WRITE_PATTERNS.items():
        if tool_name == "create_crop_cycle" and is_planting_advice:
            continue
        for pat in patterns:
            if pat.search(user_message):
                candidates.add(tool_name)
                break

    for tool_name, triggers in QUERY_TRIGGERS.items():
        for trigger in triggers:
            if trigger in user_message:
                candidates.add(tool_name)
                break

    if "update_crop_cycle" in candidates:
        candidates.difference_update({"get_crop_cycle_info", "get_farm_status"})

    if "delete_crop_cycle" in candidates:
        candidates.difference_update(
            {
                "create_crop_cycle",
                "update_crop_cycle",
                "get_crop_cycle_info",
                "get_farm_status",
            }
        )

    if "manage_crop_templates" in candidates:
        candidates.difference_update({"create_crop_template", "get_crop_templates"})

    if "manage_farm_logs" in candidates:
        candidates.difference_update(
            {"get_recent_farm_logs", "log_farm_activity", "get_farm_status"}
        )

    if "manage_planting_units" in candidates:
        candidates.difference_update({"get_planting_units", "get_farm_status"})

    if "manage_cost_categories" in candidates:
        candidates.difference_update(
            {"get_cost_categories", "get_cost_summary", "get_cost_analytics"}
        )

    if "delete_cost_record" in candidates:
        candidates.difference_update(
            {
                "create_cost_record",
                "get_cost_summary",
                "get_cost_analytics",
                "get_recent_farm_logs",
                "settle_debt",
            }
        )

    if "get_cost_categories" in candidates:
        candidates.difference_update({"get_cost_summary", "get_cost_analytics"})

    if "get_crop_cycles" in candidates:
        candidates.difference_update({"get_crop_cycle_info", "get_farm_status"})

    if "manage_user_settings" in candidates:
        candidates.discard("get_user_settings")

    if "get_labor_payables" in candidates:
        candidates.difference_update({"get_cost_summary"})
        if has_labor_hint:
            candidates.discard("get_debt_summary")

    if "get_debt_summary" in candidates:
        candidates.discard("get_cost_summary")
        if "create_cost_record" in candidates:
            if _debt_summary_should_yield_to_cost_record(
                user_message,
                has_write_intent=has_write_intent,
                has_query_intent=has_query_intent,
            ):
                candidates.discard("get_debt_summary")
            else:
                candidates.discard("create_cost_record")

    if (
        "get_operation_work_orders" in candidates
        and "create_operation_work_order" not in candidates
    ):
        candidates.difference_update(
            {"create_operation_work_order", "get_recent_farm_logs", "get_farm_status"}
        )
    elif (
        "get_operation_work_orders" in candidates
        and "create_operation_work_order" in candidates
    ):
        if has_write_intent and not has_query_intent:
            candidates.remove("get_operation_work_orders")
        elif has_query_intent and not has_write_intent:
            candidates.remove("create_operation_work_order")

    if "settle_labor_payment" in candidates:
        candidates.difference_update(
            {"settle_debt", "create_cost_record", "get_labor_payables"}
        )

    if "settle_debt" in candidates:
        candidates.discard("create_cost_record")

    if "create_operation_work_order" in candidates:
        candidates.discard("manage_workers")
        candidates.discard("manage_wages")
        candidates.discard("get_planting_units")

    if "manage_workers" in candidates:
        candidates.difference_update({"get_workers", "get_labor_payables"})

    if "manage_wages" in candidates:
        candidates.difference_update(
            {
                "create_cost_record",
                "get_cost_summary",
                "get_labor_payables",
                "get_recent_farm_logs",
                "manage_workers",
                "settle_labor_payment",
            }
        )

    if "update_operation_work_order" in candidates:
        candidates.difference_update(
            {"create_operation_work_order", "get_recent_farm_logs", "log_farm_activity"}
        )

    candidates.intersection_update(enabled_tool_names)

    # 强制绑定不被 difference_update 吃掉
    candidates |= force_binding

    if not candidates:
        if intent_classifier is not None:
            llm_result = intent_classifier.classify(user_message, all_tools)
            if llm_result is not None:
                if len(llm_result) == 0:
                    logger.info(
                        "tool_select | layer=llm_intent_none | input=%r | total=%d",
                        user_message[:80],
                        len(all_tools),
                    )
                    return ToolSelectionResult(tools=[], force_binding=frozenset())
                ordered = [t.name for t in all_tools if t.name in llm_result]
                result = ordered[:top_k]
                logger.info(
                    (
                        "tool_select | layer=llm_intent | input=%r | returned=%s | "
                        "total=%d"
                    ),
                    user_message[:80],
                    result,
                    len(all_tools),
                )
                return ToolSelectionResult(
                    tools=result, force_binding=frozenset()
                )

        decision = SkillRouter().route(user_message, all_tools)
        result = decision.selected_tools[:top_k]
        logger.info(
            (
                "tool_select | layer=router | input=%r | fallback=%s | reason=%s | "
                "returned=%s | total=%d"
            ),
            user_message[:80],
            decision.fallback,
            decision.reason,
            result,
            len(all_tools),
        )
        return ToolSelectionResult(tools=result, force_binding=frozenset())

    ordered = [t.name for t in all_tools if t.name in candidates]
    # top_k 截断时优先保留 force_binding 工具
    binding_ordered = [n for n in ordered if n in force_binding]
    non_binding_ordered = [n for n in ordered if n not in force_binding]
    result = (binding_ordered + non_binding_ordered)[:top_k]
    # 截断后 force_binding 工具若仍在结果中保留，则保留绑定信号
    result_set = set(result)
    final_force_binding = force_binding & result_set

    logger.info(
        "tool_select | layer=rule | input=%r | candidates=%s | returned=%s | total=%d",
        user_message[:80],
        ordered,
        result,
        len(all_tools),
    )
    return ToolSelectionResult(
        tools=result, force_binding=frozenset(final_force_binding)
    )


def expand_by_chain(selected: set[str], max_tools: int = 5) -> set[str]:
    """根据工具链关联扩展选中工具集。

    当查询类工具被选中时，自动关联 get_farm_status，
    因为查询结果通常需要农场整体上下文来解读。

    max_tools 限制最终返回集合的最大大小（包含原始工具）。
    """
    if max_tools <= 0:
        return set()
    expanded = set(selected)
    if len(expanded) >= max_tools:
        return expanded
    for tool_name in list(selected):
        for related in TOOL_CHAIN_MAP.get(tool_name, []):
            if related not in expanded:
                expanded.add(related)
                if len(expanded) >= max_tools:
                    return expanded
    return expanded
