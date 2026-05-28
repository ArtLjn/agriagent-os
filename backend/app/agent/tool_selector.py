"""Tool 预筛选模块 — 两层过滤器（regex + keyword）缩小 LLM 候选工具集。"""

import logging
import re

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

WRITE_PATTERNS: dict[str, list[re.Pattern]] = {
    "create_cost_record": [
        re.compile(r"(?:买了|卖了|花了|收入|支出|赊账|记账|记一笔|付了|收了)"),
        re.compile(r"\d+\s*(?:元|块|万|w|W|千|百)"),
    ],
    "settle_debt": [
        re.compile(r"(?:还[了钱账给]|清账|结清|欠款|还款)"),
        re.compile(r"(?:账[结清]|结了.*账|欠.*结)"),
    ],
    "create_crop_cycle": [
        re.compile(r"(?:创建|建|开)\s*.*茬口"),
        re.compile(r"(?:种植|种[了上下]?)\s*(?:西瓜|番茄|辣椒|豆角|黄瓜|玉米)"),
        re.compile(r"(?:春茬|秋茬|夏茬|冬茬)"),
    ],
    "log_farm_activity": [
        re.compile(r"(?:浇[了水]|施[了肥]|打[了药]|除[了草]|翻[了地]|播[了种])"),
        re.compile(r"(?:记录|记下)\s*(?:农事|操作|浇水|施肥)"),
    ],
    "update_crop_stage": [
        re.compile(r"(?:进[了入]?).*(?:期|阶段)"),
        re.compile(r"(?:到[了]?|进入)\s*(?:苗期|开花期|结果期|采收期|伸蔓期|定植期)"),
    ],
}

QUERY_TRIGGERS: dict[str, set[str]] = {
    "get_weather_forecast": {
        "天气", "预报", "降雨", "温度", "极端天气",
    },
    "get_cost_summary": {
        "余额", "收支", "成本", "利润", "花了多少", "赚了多少", "账单", "月额",
    },
    "get_cost_analytics": {
        "趋势", "对比", "比去年", "比上月", "收支分析",
    },
    "get_crop_cycle_info": {
        "茬口状态", "当前阶段", "周期进度", "茬口详情",
    },
    "get_recent_farm_logs": {
        "农事记录", "操作日志", "干了啥",
    },
}


def select_tools(user_message: str, all_tools: list[BaseTool], top_k: int = 3) -> list[str]:
    candidates: set[str] = set()

    for tool_name, patterns in WRITE_PATTERNS.items():
        for pat in patterns:
            if pat.search(user_message):
                candidates.add(tool_name)
                break

    for tool_name, triggers in QUERY_TRIGGERS.items():
        for trigger in triggers:
            if trigger in user_message:
                candidates.add(tool_name)
                break

    if not candidates:
        tool_names = [t.name for t in all_tools]
        logger.info(
            "tool_pre_filter | input=%r | candidates=%s | total=%d | fallback=True",
            user_message[:80],
            tool_names,
            len(tool_names),
        )
        return tool_names

    ordered = [t.name for t in all_tools if t.name in candidates]
    result = ordered[:top_k]

    logger.info(
        "tool_pre_filter | input=%r | candidates=%s | returned=%d | total=%d",
        user_message[:80],
        ordered,
        len(result),
        len([t.name for t in all_tools]),
    )
    return result
