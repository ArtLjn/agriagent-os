"""Tool 预筛选模块 — 三层过滤器（regex + keyword + LLM intent）缩小 LLM 候选工具集。"""

import logging
import time

from langchain_core.tools import BaseTool
from openai import OpenAI

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


def select_tools(
    user_message: str,
    all_tools: list[BaseTool],
    top_k: int = 3,
    intent_classifier: LLMIntentClassifier | None = None,
) -> list[str]:
    # 过滤掉禁用的 skill
    all_tools = [t for t in all_tools if _tool_enabled(t)]
    enabled_tool_names = {t.name for t in all_tools}
    candidates: set[str] = set()
    is_planting_advice = any(hint in user_message for hint in PLANTING_ADVICE_HINTS)
    has_write_intent = any(hint in user_message for hint in WRITE_INTENT_HINTS)
    has_query_intent = any(hint in user_message for hint in QUERY_INTENT_HINTS)

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

    if "manage_user_settings" in candidates:
        candidates.discard("get_user_settings")

    if "get_labor_payables" in candidates:
        candidates.difference_update({"get_cost_summary"})

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
        candidates.difference_update({"settle_debt", "create_cost_record"})

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
                    return []
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
                return result

        tool_names = [t.name for t in all_tools]
        logger.info(
            "tool_select | layer=fallback_all | input=%r | returned=%s | total=%d",
            user_message[:80],
            tool_names,
            len(tool_names),
        )
        return tool_names

    ordered = [t.name for t in all_tools if t.name in candidates]
    result = ordered[:top_k]

    logger.info(
        "tool_select | layer=rule | input=%r | candidates=%s | returned=%s | total=%d",
        user_message[:80],
        ordered,
        result,
        len(all_tools),
    )
    return result


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
