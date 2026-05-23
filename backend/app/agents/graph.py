"""LangGraph 图编译模块。"""

from langgraph.prebuilt import create_react_agent

from app.agents.tools import (
    get_crop_cycle_info,
    get_cycle_cost_summary,
    get_recent_farm_logs,
    get_weather_forecast,
)
from app.core.llm import get_llm


TOOLS = [
    get_weather_forecast,
    get_crop_cycle_info,
    get_recent_farm_logs,
    get_cycle_cost_summary,
]

SYSTEM_PROMPT = (
    "你是一位经验丰富的农业技术顾问，擅长西瓜、豆角等作物的种植管理。"
    "你具备以下能力：查询天气预报和灾害预警、查看种植周期和当前阶段、"
    "了解近期农事记录、统计成本收支。请根据用户的问题，主动调用合适的工具"
    "获取信息，然后给出具体、可操作的建议。回答要简洁明了，适合农民理解。"
    "使用中文回答。"
)


def compile_advisor_graph():
    """编译建议 Agent 的 ReAct 图。

    Returns:
        编译后的 LangGraph 图实例。
    """
    llm = get_llm()
    return create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)


__all__ = ["compile_advisor_graph"]
