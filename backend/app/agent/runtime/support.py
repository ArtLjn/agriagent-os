"""Agent runtime shared support primitives."""

from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.core.database import SessionLocal
from app.services.quota_service import QuotaCheckResult, check_user_quota


class AgentRuntimeError(RuntimeError):
    """Agent Runtime 基础错误。"""


QUOTA_REJECT_MESSAGES = {
    "month": "本月用量已达上限，配额将在下月重置。",
    "week": "本周用量已达上限，配额将在下周一重置。",
    "identity": "缺少可信用户上下文，无法继续处理。",
}


def check_quota(user_id: str | None) -> QuotaCheckResult:
    db = SessionLocal()
    try:
        return check_user_quota(user_id, db)
    finally:
        db.close()


def compile_advisor_graph():
    """编译建议 Agent 的 StateGraph（支持并行 Skill 执行，最大 15 步）。"""
    from app.agent.runtime.nodes import _llm_node, _parallel_tool_node, _should_continue

    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", _parallel_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


__all__ = [
    "AgentRuntimeError",
    "QUOTA_REJECT_MESSAGES",
    "check_quota",
    "compile_advisor_graph",
]
