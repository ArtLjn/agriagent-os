"""意图识别与工具候选选择入口。"""

from app.agent.tool_selector import expand_by_chain, select_tools
from app.agent.intent_router import classify_intent
from app.agent.planner.models import ToolCandidatePlan


def plan_tool_candidates(
    user_message: str,
    all_tools: list,
    top_k: int = 3,
) -> ToolCandidatePlan:
    """生成意图和工具候选计划。"""
    intent = classify_intent(user_message).value
    selection = select_tools(user_message, all_tools, top_k)
    selected = list(selection.tools)
    expanded = list(expand_by_chain(set(selected), max_tools=max(top_k, len(selected))))
    return ToolCandidatePlan(
        intent=intent,
        selected_tools=selected,
        expanded_tools=expanded,
        reason="rule_keyword_llm_fallback",
    )


__all__ = [
    "ToolCandidatePlan",
    "expand_by_chain",
    "plan_tool_candidates",
    "select_tools",
]
