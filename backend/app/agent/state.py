"""Agent 状态定义。"""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """LangGraph 状态。"""

    messages: Annotated[list[BaseMessage], add_messages]
    farm_id: int
    intent: str  # "greeting" | "query" | "write" | "agent"
