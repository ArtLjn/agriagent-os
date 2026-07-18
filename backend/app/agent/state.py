"""Agent 状态定义。"""

from app.agent.router import RouterDecision
from app.context.models import ContextBundle
from langchain_core.messages import BaseMessage
from typing_extensions import NotRequired, TypedDict


class AgentState(TypedDict):
    """Agent runtime 状态。"""

    messages: list[BaseMessage]
    farm_id: int
    farm_uid: str | None
    intent: str  # "greeting" | "query" | "write" | "agent"
    user_id: str | None
    session_id: str | None
    user_role: NotRequired[str | None]
    system_prompt: NotRequired[str | None]
    context_bundle: NotRequired[ContextBundle | None]
    selected_tool_names: NotRequired[list[str] | None]
    router_decision: NotRequired[RouterDecision | None]
    plan_draft: NotRequired[dict | None]
    trace_round_index: NotRequired[int | None]
