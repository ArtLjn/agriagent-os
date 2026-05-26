"""报告 Agent 封装，生成种植周期周报/月报。"""

import logging
import time

from langchain_core.messages import HumanMessage

from app.core.guardrails import filter_output
from app.core.llm import get_llm
from app.core.prompt_registry import get_registry
from app.core.prompt_renderer import render_prompt
from app.core.date_context import get_request_date
from app.skills import get_langchain_tools

logger = logging.getLogger(__name__)

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
    start = time.perf_counter()
    logger.info("报告生成开始 | type=cycle | cycle_id=%d", cycle_id)
    llm = _get_report_llm()
    prompt = (
        f"请为 ID={cycle_id} 的种植周期生成一份综合报告。"
        "请查询该周期的基本信息、最近农事记录和成本收支，"
        "整理成一份包含进度、成本分析和下一步建议的报告。"
    )
    current_date = get_request_date()
    system_text = render_prompt(
        "report", registry=get_registry(), current_date=current_date
    )
    system = HumanMessage(content=system_text)
    response = await llm.ainvoke(
        [system, HumanMessage(content=prompt)],
        config={"run_name": "cycle_report", "metadata": {"cycle_id": cycle_id}},
    )
    result = filter_output(response.content)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info("报告生成完成 | len=%d | duration_ms=%d", len(result), duration_ms)
    return result


__all__ = ["generate_cycle_report"]
