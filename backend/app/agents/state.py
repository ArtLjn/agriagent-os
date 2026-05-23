"""Agent 状态定义。"""

from typing import Annotated

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Agent 状态类型，包含消息历史。

    Attributes:
        messages: 消息列表，使用 add_messages reducer 自动追加。
    """

    messages: Annotated[list[BaseMessage], "add_messages"]
