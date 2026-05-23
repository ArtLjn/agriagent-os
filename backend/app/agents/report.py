"""报告 Agent 封装，生成种植周期周报/月报。"""

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from app.agents.graph import TOOLS
from app.core.llm import get_llm


REPORT_SYSTEM_PROMPT = (
    "你是一位农业数据分析师，擅长整理种植周期的各项数据并生成清晰报告。"
    "你可以查询天气、茬口信息、农事记录和成本收支。报告要求数据准确、"
    "条理清晰，包含关键指标（成本、收入、农事进度）和下一步建议。"
    "使用中文输出。"
)

_REPORT_GRAPH = None


def _get_report_graph():
    """获取全局 Report 图实例（单例）。"""
    global _REPORT_GRAPH
    if _REPORT_GRAPH is None:
        llm = get_llm()
        _REPORT_GRAPH = create_react_agent(llm, TOOLS, prompt=REPORT_SYSTEM_PROMPT)
    return _REPORT_GRAPH


def build_report_agent():
    """构建并返回报告 Agent 图（主要用于测试）。"""
    llm = get_llm()
    return create_react_agent(llm, TOOLS, prompt=REPORT_SYSTEM_PROMPT)


def generate_cycle_report(cycle_id: int) -> str:
    """生成指定种植周期的综合报告。

    Args:
        cycle_id: 种植周期 ID。

    Returns:
        报告文本。
    """
    graph = _get_report_graph()
    prompt = (
        f"请为 ID={cycle_id} 的种植周期生成一份综合报告。"
        "请查询该周期的基本信息、最近农事记录和成本收支，"
        "整理成一份包含进度、成本分析和下一步建议的报告。"
    )
    result = graph.invoke({"messages": [HumanMessage(content=prompt)]})
    return result["messages"][-1].content


__all__ = ["build_report_agent", "generate_cycle_report"]
