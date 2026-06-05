"""Tool 预筛选模块 — 三层过滤器（regex + keyword + LLM intent）缩小 LLM 候选工具集。"""

import logging
import re
import time

from langchain_core.tools import BaseTool
from openai import OpenAI

logger = logging.getLogger(__name__)

WRITE_INTENT_HINTS = {"创建", "新建", "记录", "记下", "添加"}
QUERY_INTENT_HINTS = {"查询", "查看", "最近", "有哪些", "多少", "还欠", "统计"}

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
        re.compile(r"(?:我想|我要|想要|准备|打算)\s*种\s*[\u4e00-\u9fa5]{1,12}$"),
        re.compile(r"(?:春茬|秋茬|夏茬|冬茬)"),
    ],
    "create_crop_template": [
        re.compile(r"(?:创建|建|新建|添加).*(?:作物|模板)"),
        re.compile(r"(?:没有|缺少|找不到).*(?:模板|作物)"),
    ],
    "log_farm_activity": [
        re.compile(r"(?:浇[了水]|施[了肥]|打[了药]|除[了草]|翻[了地]|播[了种])"),
        re.compile(r"(?:记录|记下)\s*(?:农事|操作|浇水|施肥)"),
    ],
    "update_crop_stage": [
        re.compile(r"(?:进[了入]?).*(?:期|阶段)"),
        re.compile(r"(?:到[了]?|进入)\s*(?:苗期|开花期|结果期|采收期|伸蔓期|定植期)"),
    ],
    "update_crop_cycle": [
        re.compile(r"(?:修改|更改|调整|改|改成|改到).*(?:茬口|周期|开始|播种期|起始)"),
        re.compile(
            r"(?:西瓜|番茄|辣椒|豆角|黄瓜|玉米|水稻).*(?:修改|更改|调整|改|改成|改到).*(?:\d{1,2}月|开始|播种期|起始)"
        ),
    ],
    "create_operation_work_order": [
        re.compile(r"(?:授粉|压蔓|留瓜|垫瓜|采收|装车|打杈|绑蔓|整枝).*(?:工人|每人|人工|作业|干活)"),
        re.compile(r"(?:创建|新建|记录).*(?:作业单|农事作业|用工)"),
        re.compile(r"(?:东大棚|西大棚|地块|棚).*(?:工人|每人|人工).*(?:\d+\s*(?:元|块|人))"),
    ],
    "settle_labor_payment": [
        re.compile(r"(?:补付|支付|结算|付清|结清).*(?:人工|工钱|工资)"),
        re.compile(r"(?:给|付给).{1,12}(?:\d+\s*(?:元|块|百|千)).*(?:人工|工钱|工资)"),
    ],
    "update_operation_work_order": [
        re.compile(r"(?:刚才|上一条|那条|这条).*(?:不是|改成|改为|改到|更正|纠正).*(?:作业|记录|授粉|人工|工人|付)"),
        re.compile(r"(?:修改|更改|调整|纠正).*(?:作业单|农事作业|用工记录)"),
    ],
}

QUERY_TRIGGERS: dict[str, set[str]] = {
    "get_weather_forecast": {
        "天气",
        "预报",
        "降雨",
        "温度",
        "极端天气",
    },
    "get_cost_summary": {
        "余额",
        "收支",
        "成本",
        "利润",
        "花了多少",
        "赚了多少",
        "账单",
        "周账单",
        "月账单",
        "年账单",
        "本周",
        "本月",
        "今年",
        "去年",
        "流水",
        "明细",
        "欠款",
        "赊账",
        "还欠",
        "分类汇总",
        "月额",
    },
    "get_cost_analytics": {
        "趋势",
        "对比",
        "比去年",
        "比上月",
        "收支分析",
    },
    "get_crop_cycle_info": {
        "茬口",
        "当前阶段",
        "周期进度",
        "阶段",
    },
    "get_recent_farm_logs": {
        "农事记录",
        "操作日志",
        "干了啥",
        "记录",
    },
    "get_labor_payables": {
        "人工钱",
        "工钱",
        "工资",
        "未付人工",
        "欠人工",
        "还欠多少人工",
        "人工欠款",
    },
    "get_operation_work_orders": {
        "作业单",
        "农事作业",
        "授粉作业",
        "作业有哪些",
        "用工记录",
        "最近授粉",
        "最近采收",
    },
    "get_farm_status": {
        "农场",
        "茬口状态",
        "种植情况",
        "农事",
        "综合状态",
        "整体情况",
    },
    "web_search": {
        "最新",
        "新闻",
        "价格",
        "上市",
        "政策",
        "热点",
        "搜索",
        "查一下",
        "最近",
        "实时",
        "网上",
        "网上说",
    },
}

PLANTING_ADVICE_HINTS = (
    "怎么",
    "如何",
    "注意",
    "建议",
    "技术",
    "方法",
    "适合",
    "可以吗",
    "能不能",
    "什么时候",
)


class LLMIntentClassifier:
    """Layer 3 — LLM 意图分类兜底。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 5.0,
        provider: str = "config.yaml",
        role: str = "tool-selection",
    ):
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=3,
        )
        self._model = model
        self._provider = provider
        self._role = role

    def classify(
        self, user_message: str, all_tools: list[BaseTool]
    ) -> list[str] | None:
        tool_lines = []
        for t in all_tools:
            desc = (getattr(t, "description", "") or "")[:100]
            tool_lines.append(f"- {t.name}: {desc}")
        tool_descriptions = "\n".join(tool_lines)
        tool_names = [t.name for t in all_tools]

        prompt = (
            "You are an intent classifier. Given the user message below, "
            "determine which tool best matches the user's intent.\n"
            "Reply with ONLY the tool name, or 'none' if no tool matches.\n\n"
            f"Available tools:\n{tool_descriptions}\n\n"
            f"Tool names: {', '.join(tool_names)}\n\n"
            f"User message: {user_message}\n"
            "Matched tool name:"
        )

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            content = (response.choices[0].message.content or "").strip().lower()

            if content == "none":
                logger.info(
                    (
                        "tool_select LLM intent | provider=%s | model=%s | role=%s | "
                        "input=%r | raw=%r | matched=[] | latency_ms=%d"
                    ),
                    self._provider,
                    self._model,
                    self._role,
                    user_message[:80],
                    content,
                    latency_ms,
                )
                return []

            matched = None
            for name in tool_names:
                if name == content:
                    matched = [name]
                    break

            logger.info(
                (
                    "tool_select LLM intent | provider=%s | model=%s | role=%s | "
                    "input=%r | raw=%r | matched=%s | latency_ms=%d"
                ),
                self._provider,
                self._model,
                self._role,
                user_message[:80],
                content,
                matched,
                latency_ms,
            )
            return matched
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                (
                    "tool_select LLM intent failed | provider=%s | model=%s | "
                    "role=%s | input=%r | latency_ms=%d | error=%s: %s"
                ),
                self._provider,
                self._model,
                self._role,
                user_message[:80],
                latency_ms,
                type(e).__name__,
                e,
            )
            return None


DISABLED_SKILLS: set[str] = {
    "web_search",  # SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用
}


def _tool_enabled(tool: BaseTool) -> bool:
    metadata = getattr(tool, "skill_metadata", None)
    enabled = getattr(metadata, "enabled", None)
    if isinstance(enabled, bool):
        return enabled
    return tool.name not in DISABLED_SKILLS


def select_tools(
    user_message: str,
    all_tools: list[BaseTool],
    top_k: int = 3,
    intent_classifier: LLMIntentClassifier | None = None,
) -> list[str]:
    # 过滤掉禁用的 skill
    all_tools = [t for t in all_tools if _tool_enabled(t)]
    enabled_tool_names = {t.name for t in all_tools}
    candidates: set[str] = set()
    is_planting_advice = any(hint in user_message for hint in PLANTING_ADVICE_HINTS)
    has_write_intent = any(hint in user_message for hint in WRITE_INTENT_HINTS)
    has_query_intent = any(hint in user_message for hint in QUERY_INTENT_HINTS)

    for tool_name, patterns in WRITE_PATTERNS.items():
        if tool_name == "create_crop_cycle" and is_planting_advice:
            continue
        for pat in patterns:
            if pat.search(user_message):
                candidates.add(tool_name)
                break

    for tool_name, triggers in QUERY_TRIGGERS.items():
        for trigger in triggers:
            if trigger in user_message:
                candidates.add(tool_name)
                break

    if "update_crop_cycle" in candidates:
        candidates.difference_update({"get_crop_cycle_info", "get_farm_status"})

    if "get_labor_payables" in candidates:
        candidates.difference_update({"get_cost_summary"})

    if (
        "get_operation_work_orders" in candidates
        and "create_operation_work_order" not in candidates
    ):
        candidates.difference_update(
            {"create_operation_work_order", "get_recent_farm_logs", "get_farm_status"}
        )
    elif (
        "get_operation_work_orders" in candidates
        and "create_operation_work_order" in candidates
    ):
        if has_write_intent and not has_query_intent:
            candidates.remove("get_operation_work_orders")
        elif has_query_intent and not has_write_intent:
            candidates.remove("create_operation_work_order")

    if "settle_labor_payment" in candidates:
        candidates.difference_update({"settle_debt", "create_cost_record"})

    if "update_operation_work_order" in candidates:
        candidates.difference_update(
            {"create_operation_work_order", "get_recent_farm_logs", "log_farm_activity"}
        )

    candidates.intersection_update(enabled_tool_names)

    if not candidates:
        if intent_classifier is not None:
            llm_result = intent_classifier.classify(user_message, all_tools)
            if llm_result is not None:
                if len(llm_result) == 0:
                    logger.info(
                        "tool_select | layer=llm_intent_none | input=%r | total=%d",
                        user_message[:80],
                        len(all_tools),
                    )
                    return []
                ordered = [t.name for t in all_tools if t.name in llm_result]
                result = ordered[:top_k]
                logger.info(
                    (
                        "tool_select | layer=llm_intent | input=%r | returned=%s | "
                        "total=%d"
                    ),
                    user_message[:80],
                    result,
                    len(all_tools),
                )
                return result

        tool_names = [t.name for t in all_tools]
        logger.info(
            "tool_select | layer=fallback_all | input=%r | returned=%s | total=%d",
            user_message[:80],
            tool_names,
            len(tool_names),
        )
        return tool_names

    ordered = [t.name for t in all_tools if t.name in candidates]
    result = ordered[:top_k]

    logger.info(
        "tool_select | layer=rule | input=%r | candidates=%s | returned=%s | total=%d",
        user_message[:80],
        ordered,
        result,
        len(all_tools),
    )
    return result


TOOL_CHAIN_MAP: dict[str, list[str]] = {
    "get_weather_forecast": ["get_farm_status"],
    "get_cost_summary": ["get_farm_status"],
    "get_cost_analytics": ["get_farm_status"],
    "get_crop_cycle_info": ["get_farm_status"],
    "get_recent_farm_logs": ["get_farm_status"],
    "get_labor_payables": ["get_farm_status"],
    "get_operation_work_orders": ["get_farm_status"],
    "create_cost_record": [],
    "create_crop_cycle": [],
    "create_crop_template": [],
    "create_operation_work_order": [],
    "log_farm_activity": [],
    "settle_debt": [],
    "settle_labor_payment": [],
    "update_crop_cycle": [],
    "update_crop_stage": [],
    "update_operation_work_order": [],
    "get_farm_status": [],
    "web_search": [],
}


def expand_by_chain(selected: set[str], max_tools: int = 5) -> set[str]:
    """根据工具链关联扩展选中工具集。

    当查询类工具被选中时，自动关联 get_farm_status，
    因为查询结果通常需要农场整体上下文来解读。

    max_tools 限制最终返回集合的最大大小（包含原始工具）。
    """
    if max_tools <= 0:
        return set()
    expanded = set(selected)
    if len(expanded) >= max_tools:
        return expanded
    for tool_name in list(selected):
        for related in TOOL_CHAIN_MAP.get(tool_name, []):
            if related not in expanded:
                expanded.add(related)
                if len(expanded) >= max_tools:
                    return expanded
    return expanded
