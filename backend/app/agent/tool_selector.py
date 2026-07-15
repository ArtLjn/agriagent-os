"""Tool 预筛选模块。

普通读请求由 runtime 暴露只读工具池后交给主模型选择；本模块仅保留
写操作和兼容入口所需的轻量规则。
"""

import logging
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool

from app.agent.router.service import SkillRouter
from app.agent.tool_selection_rules import (
    DISABLED_SKILLS,
    PLANTING_ADVICE_HINTS,
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

    `tools` 是兼容入口返回的候选工具名集合。
    `force_binding` 保留字段兼容旧 trace 和测试结构；普通查询不再强制绑定。

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
                self.tools == other.tools and self.force_binding == other.force_binding
            )
        if isinstance(other, list):
            return self.tools == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash((tuple(self.tools), self.force_binding))


def _tool_enabled(tool: BaseTool) -> bool:
    metadata = getattr(tool, "skill_metadata", None)
    enabled = getattr(metadata, "enabled", None)
    if isinstance(enabled, bool):
        return enabled
    return tool.name not in DISABLED_SKILLS


def select_tools(
    user_message: str,
    all_tools: list[BaseTool],
    top_k: int = 3,
) -> ToolSelectionResult:
    # 过滤掉禁用的 skill
    all_tools = [t for t in all_tools if _tool_enabled(t)]
    enabled_tool_names = {t.name for t in all_tools}
    candidates: set[str] = set()
    is_planting_advice = any(hint in user_message for hint in PLANTING_ADVICE_HINTS)
    has_write_intent = any(hint in user_message for hint in WRITE_INTENT_HINTS)
    has_query_intent = any(hint in user_message for hint in QUERY_INTENT_HINTS)
    has_labor_hint = any(hint in user_message for hint in ("人工", "工钱", "工资"))

    for tool_name, patterns in WRITE_PATTERNS.items():
        if tool_name == "manage_crop_cycle" and is_planting_advice:
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

    if "manage_crop_cycle" in candidates:
        candidates.discard("get_farm_status")

    if "manage_farm_logs" in candidates:
        candidates.discard("get_farm_status")

    if "manage_planting_units" in candidates:
        candidates.discard("get_farm_status")

    if "manage_cost_categories" in candidates:
        candidates.discard("manage_cost")

    if "manage_cost" in candidates:
        candidates.discard("manage_farm_logs")

    if "get_labor_payables" in candidates:
        if has_labor_hint:
            candidates.discard("manage_cost")

    if (
        "get_operation_work_orders" in candidates
        and "create_operation_work_order" not in candidates
    ):
        candidates.difference_update(
            {"create_operation_work_order", "manage_farm_logs", "get_farm_status"}
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
        candidates.difference_update({"manage_cost", "get_labor_payables"})

    if "create_operation_work_order" in candidates:
        candidates.discard("manage_workers")
        candidates.discard("manage_wages")
        candidates.discard("manage_planting_units")

    if "manage_workers" in candidates:
        candidates.difference_update({"get_workers", "get_labor_payables"})

    if "manage_wages" in candidates:
        candidates.difference_update(
            {
                "manage_cost",
                "get_labor_payables",
                "manage_farm_logs",
                "manage_workers",
                "settle_labor_payment",
            }
        )

    if "update_operation_work_order" in candidates:
        candidates.difference_update({"create_operation_work_order", "manage_farm_logs"})

    candidates.intersection_update(enabled_tool_names)

    if not candidates:
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
    result = ordered[:top_k]

    logger.info(
        "tool_select | layer=rule | input=%r | candidates=%s | returned=%s | total=%d",
        user_message[:80],
        ordered,
        result,
        len(all_tools),
    )
    return ToolSelectionResult(tools=result, force_binding=frozenset())


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
