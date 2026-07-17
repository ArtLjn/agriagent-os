"""报告 Agent 封装，生成种植周期周报/月报。"""

import logging
import time

from langchain_core.messages import HumanMessage

from app.agent.guardrails import filter_output
from app.core.llm import get_llm
from app.prompt.composer import get_composer
from app.core.date_context import get_request_date
from app.skills import get_langchain_tools

logger = logging.getLogger(__name__)


def _get_report_llm(farm_id: int = 1):
    """获取绑定了工具的报告 LLM 实例（每次返回新实例）。"""
    tools = get_langchain_tools(farm_id=farm_id)
    return get_llm().bind_tools(tools)


# TODO prompt 是否迁移
async def generate_cycle_report(cycle_id: int, farm_id: int = 1) -> str:
    """生成指定种植周期的综合报告。"""
    start = time.perf_counter()
    logger.info("报告生成开始 | type=cycle | cycle_id=%d", cycle_id)
    llm = _get_report_llm(farm_id=farm_id)
    prompt = (
        f"请为 ID={cycle_id} 的种植周期生成一份综合报告。"
        "请查询该周期的基本信息、最近农事记录和成本收支，"
        "整理成一份包含进度、成本分析和下一步建议的报告。"
    )
    current_date = get_request_date()
    system_text = get_composer().compose("report", current_date=current_date)
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
