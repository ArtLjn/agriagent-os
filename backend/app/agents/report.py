"""报告 Agent 封装，生成种植周期周报/月报。"""

import logging
from datetime import datetime, timedelta, timezone

from langchain_core.messages import HumanMessage

from app.core.guardrails import filter_output
from app.core.llm import get_llm
from app.skills import get_langchain_tools

logger = logging.getLogger(__name__)

REPORT_SYSTEM_PROMPT = (
    "你是一位农业数据分析师，擅长整理种植周期的各项数据并生成清晰报告。"
    "你可以查询天气、茬口信息、农事记录和成本收支。报告要求数据准确、"
    "条理清晰，包含关键指标（成本、收入、农事进度）和下一步建议。"
    "使用中文输出。"
)

_REPORT_LLM = None


def _get_report_llm():
    """获取绑定了工具的报告 LLM 实例。"""
    global _REPORT_LLM
    if _REPORT_LLM is None:
        tools = get_langchain_tools()
        _REPORT_LLM = get_llm().bind_tools(tools)
    return _REPORT_LLM


async def generate_cycle_report(cycle_id: int) -> str:
    """生成指定种植周期的综合报告。"""
    llm = _get_report_llm()
    prompt = (
        f"请为 ID={cycle_id} 的种植周期生成一份综合报告。"
        "请查询该周期的基本信息、最近农事记录和成本收支，"
        "整理成一份包含进度、成本分析和下一步建议的报告。"
    )
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
    time_info = f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_cn}"
    system = HumanMessage(content=f"{REPORT_SYSTEM_PROMPT}\n{time_info}")
    response = await llm.ainvoke([system, HumanMessage(content=prompt)])
    return filter_output(response.content)


__all__ = ["generate_cycle_report"]
