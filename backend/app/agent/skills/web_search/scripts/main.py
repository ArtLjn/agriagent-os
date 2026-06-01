"""网络搜索 Skill — 基于自建 SearXNG 获取实时网络信息。"""

import logging
from urllib.parse import urlencode

import httpx

from langchain_core.messages import HumanMessage, SystemMessage
from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.llm import LlmNotConfiguredError, get_llm
from app.core.config import settings
from app.infra.skill_cache import cached

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 15.0


def _get_searxng_url() -> str:
    return settings.secrets.searxng_url


_NEWS_KEYWORDS = ["最新", "新闻", "今天", "近日", "刚刚", "报道", "事件", "发布会", "公告", "通知"]


def _detect_search_category(query: str) -> str:
    """基于关键词规则快速判断搜索分类（轻量 fallback）。"""
    q = query.lower()
    if any(kw in q for kw in _NEWS_KEYWORDS):
        return "news"
    return "general"


async def _optimize_query(raw_query: str) -> tuple[str, str]:
    """用 LLM 同时完成查询改写和搜索分类判断，返回 (改写后查询, 分类)。

    一次 LLM 调用同时完成两项任务，减少 API 开销。
    若 LLM 不可用则回退到规则分类 + 原查询。
    """
    try:
        llm = get_llm(role="generation")
        response = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是搜索查询优化专家。分析用户查询并输出两部分结果：\n"
                        "1. 改写后的搜索查询（补充时间、地点、专业术语）\n"
                        "2. 搜索分类（general/news/images/videos 之一）\n\n"
                        "输出格式严格为两行：\n"
                        "QUERY: <改写后的查询>\n"
                        "CATEGORY: <分类>"
                    )
                ),
                HumanMessage(content=f"用户查询：{raw_query}"),
            ]
        )
        text = response.content.strip()
        # 解析 LLM 输出
        rewritten = raw_query
        category = ""
        for line in text.splitlines():
            if line.strip().startswith("QUERY:"):
                rewritten = line.split(":", 1)[1].strip()
            elif line.strip().startswith("CATEGORY:"):
                category = line.split(":", 1)[1].strip().lower()
        # 校验
        if len(rewritten) >= 3 and category in ("general", "news", "images", "videos"):
            return rewritten, category
    except (LlmNotConfiguredError, Exception):
        pass
    # 回退：规则分类 + 原查询
    return raw_query, _detect_search_category(raw_query)


def _format_results(query: str, data: dict) -> str:
    """将 SearXNG 完整响应格式化为带编号引用的结构化文本。

    每条结果标注 [1] [2] 编号，LLM 回答时可引用对应来源。
    """
    lines: list[str] = []

    # 直接回答（如计算、百科摘要）
    answers = data.get("answers", [])
    if answers:
        lines.append("直接回答:")
        for a in answers:
            lines.append(f"  {a}")
        lines.append("")

    # 信息卡片
    infoboxes = data.get("infoboxes", [])
    for box in infoboxes:
        title = box.get("infobox", "")
        content = box.get("content", "")
        if title:
            lines.append(f"📋 {title}")
        if content:
            lines.append(f"  {content}")
        lines.append("")

    # 搜索结果 — 按 score 降序排列
    items = data.get("results", [])
    items.sort(key=lambda x: x.get("score", 0), reverse=True)

    if not items and not answers and not infoboxes:
        return f"未找到与「{query}」相关的结果。"

    source_count = 0
    if items:
        lines.append(f"搜索关键词: {query}")
        lines.append(f"找到 {len(items)} 条结果")
        lines.append("")
        for i, item in enumerate(items[:10], 1):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            content = item.get("content", "")
            engines = item.get("engines", [])
            published = item.get("publishedDate", "")

            source_count = i
            lines.append(f"[{i}] {title}")
            if published:
                lines.append(f"    时间: {published}")
            if content:
                lines.append(f"    摘要: {content}")
            if url:
                lines.append(f"    链接: {url}")
            if engines:
                lines.append(f"    引擎: {', '.join(engines)}")
            lines.append("")

    # 搜索建议
    suggestions = data.get("suggestions", [])
    if suggestions:
        lines.append("相关搜索:")
        for s in suggestions[:5]:
            lines.append(f"  - {s}")
        lines.append("")

    # Grounding 指令 — 引导 LLM 基于来源回答
    if source_count > 0:
        lines.append("---")
        lines.append(
            "请严格基于以上搜索结果回答用户问题。"
            "回答时用 [编号] 标注信息来源，如 [1][2]。"
            "如果搜索结果不足以回答问题，请如实告知用户。"
        )

    return "\n".join(lines)


class WebSearchSkill(Skill):
    def name(self) -> str:
        return "web_search"

    def description(self) -> str:
        return (
            "搜索互联网获取实时信息。当用户问最新新闻、市场价格、上市时间、"
            "最新政策、实时热点、百科知识等需要网络搜索的问题时调用。"
            "触发词: 最新、新闻、价格、上市、政策、热点、搜索、查一下"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如'2026年西瓜价格走势'。",
                },
                "categories": {
                    "type": "string",
                    "description": "搜索类别: general(通用), news(新闻), "
                    "images(图片), videos(视频)。默认 general。",
                    "enum": ["general", "news", "images", "videos"],
                },
            },
            "required": ["query"],
        }

    @cached(
        ttl_seconds=600,
        key_fn=lambda p: f"web:{p.get('query', '')}:{p.get('categories', 'general')}",
    )
    async def execute(self, params: dict, context) -> SkillResult:
        query = params.get("query", "").strip()
        if not query:
            return SkillResult(
                status=ResultStatus.FAILED, reply="请提供搜索关键词。"
            )

        searxng_url = _get_searxng_url()
        if not searxng_url:
            return SkillResult(
                status=ResultStatus.FAILED, reply="搜索服务未配置。"
            )

        # 查询优化：一次 LLM 调用同时完成改写 + 分类
        categories = params.get("categories")
        if categories:
            # 用户显式指定分类时只改写查询
            rewritten = (await _optimize_query(query))[0]
        else:
            rewritten, categories = await _optimize_query(query)

        logger.info(
            "web_search 查询优化 | 原始=%r | 改写=%r | 分类=%s",
            query,
            rewritten,
            categories,
        )

        data = await self._search(searxng_url, rewritten, categories)

        # 非通用分类无结果时 fallback 到 general
        if (
            categories != "general"
            and not data.get("results")
            and not data.get("answers")
            and not data.get("infoboxes")
        ):
            logger.info(
                "web_search fallback | categories=%s → general | query=%r",
                categories,
                rewritten,
            )
            data = await self._search(searxng_url, rewritten, "general")

        if data is None:
            return SkillResult(
                status=ResultStatus.FAILED, reply="搜索服务异常，请稍后重试。"
            )

        results = data.get("results", [])
        answers = data.get("answers", [])
        infoboxes = data.get("infoboxes", [])

        if not results and not answers and not infoboxes:
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=f"未找到与「{query}」相关的结果。",
            )

        reply = _format_results(query, data)
        logger.info(
            "web_search 完成 | query=%r | results=%d | answers=%d",
            query,
            len(results),
            len(answers),
        )
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)

    async def _search(
        self, searxng_url: str, query: str, categories: str
    ) -> dict | None:
        """执行单次 SearXNG 搜索，返回 JSON 数据或 None（请求失败）。"""
        search_params = {
            "q": query,
            "format": "json",
            "categories": categories,
            "language": "zh-CN",
        }
        url = f"{searxng_url}/search?{urlencode(search_params)}"

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            logger.warning("SearXNG 请求超时 | query=%r | categories=%s", query, categories)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "SearXNG HTTP 错误 | status=%d | query=%r",
                e.response.status_code,
                query,
            )
            return None
        except Exception as e:
            logger.warning(
                "SearXNG 请求失败 | query=%r | error=%s: %s",
                query,
                type(e).__name__,
                e,
            )
            return None
