"""建议 Agent 封装，提供每日建议和用户问答接口。"""

from langchain_core.messages import HumanMessage

from app.agents.graph import compile_advisor_graph


_ADVISOR_GRAPH = None


def _get_advisor_graph():
    """获取全局 Advisor 图实例（单例）。"""
    global _ADVISOR_GRAPH
    if _ADVISOR_GRAPH is None:
        _ADVISOR_GRAPH = compile_advisor_graph()
    return _ADVISOR_GRAPH


def build_advisor_agent():
    """构建并返回建议 Agent 图（主要用于测试）。"""
    return compile_advisor_graph()


def invoke_advisor(user_input: str) -> str:
    """调用建议 Agent 回答用户问题。

    Args:
        user_input: 用户输入的问题或请求。

    Returns:
        Agent 生成的建议文本。
    """
    graph = _get_advisor_graph()
    result = graph.invoke({"messages": [HumanMessage(content=user_input)]})
    return result["messages"][-1].content


__all__ = ["build_advisor_agent", "invoke_advisor"]
