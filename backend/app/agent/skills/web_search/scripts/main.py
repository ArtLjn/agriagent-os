"""网络搜索 Skill — 基于自建 SearXNG 获取实时网络信息。"""

import logging
from urllib.parse import urlencode

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.llm import LlmNotConfiguredError, get_llm
from app.core.config import settings
from app.infra.skill_cache import cached
from app.agent.skills.web_search.scripts.support import (
    _compute_relevance as _support_compute_relevance,
    _deduplicate as _support_deduplicate,
    _extract_keywords as _support_extract_keywords,
    _fetch_page_content as _support_fetch_page_content,
    _rerank_results as _support_rerank_results,
    detect_search_category,
    detect_time_range,
    format_results as _support_format_results,
)

_detect_search_category = detect_search_category
_detect_time_range = detect_time_range
_compute_relevance = _support_compute_relevance
_deduplicate = _support_deduplicate
_extract_keywords = _support_extract_keywords
_rerank_results = _support_rerank_results

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 15.0


def _get_searxng_url() -> str:
    return settings.secrets.searxng_url


async def _rewrite_query(raw_query: str) -> str:
    """兼容旧测试 patch 点的查询改写入口。"""
    try:
        llm = get_llm(role="generation")
        response = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "将用户查询改写为适合搜索引擎的关键词。"
                        "要求：补充地点、专业术语；只返回改写后的查询，不要解释，不要加年份。"
                    )
                ),
                HumanMessage(content=raw_query),
            ]
        )
        rewritten = response.content.strip()
        for prefix in ["改写后：", "改写：", "查询：", "关键词：", '"', "'"]:
            if rewritten.startswith(prefix):
                rewritten = rewritten[len(prefix) :].strip()
        rewritten = rewritten.splitlines()[0].strip()
        if len(rewritten) >= 3 and rewritten != raw_query:
            logger.info("web_search 查询改写 | 原始=%r | 改写=%r", raw_query, rewritten)
            return rewritten
    except (LlmNotConfiguredError, Exception):
        pass
    return raw_query


async def _fetch_page_content(url: str, max_length: int = 400) -> str | None:
    """兼容旧测试 patch 点的网页正文抓取入口。"""
    return await _support_fetch_page_content(url, max_length=max_length)


async def _format_results(query: str, data: dict, rewritten: str = "") -> str:
    """兼容旧测试 patch 点的格式化入口。"""
    original_fetch = _support_fetch_page_content
    try:
        import app.agent.skills.web_search.scripts.support as support

        support._fetch_page_content = _fetch_page_content
        return await _support_format_results(query, data, rewritten)
    finally:
        support._fetch_page_content = original_fetch


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
                "time_range": {
                    "type": "string",
                    "description": "时间过滤: day(当天), week(一周), month(一月), year(一年)。",
                    "enum": ["day", "week", "month", "year"],
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
            return SkillResult(status=ResultStatus.FAILED, reply="请提供搜索关键词。")

        searxng_url = _get_searxng_url()
        if not searxng_url:
            return SkillResult(status=ResultStatus.FAILED, reply="搜索服务未配置。")

        # 1. 查询改写（LLM）— 仅作辅助，不替代原始查询
        rewritten = await _rewrite_query(query)

        # 2. 分类判断（规则，零成本）
        categories = params.get("categories") or detect_search_category(query)

        # 3. 时间范围检测（含"价格/最新"等词时限定近一个月）
        time_range = params.get("time_range") or detect_time_range(query)

        logger.info(
            "web_search 查询优化 | 原始=%r | 改写=%r | 分类=%s | 时间=%s",
            query,
            rewritten,
            categories,
            time_range or "不限",
        )

        # 优先用原始查询搜索，更稳定
        data = await self._search(searxng_url, query, categories, time_range)

        # 带时间过滤无结果时，去掉时间限制重试
        if (
            time_range
            and data is not None
            and not data.get("results")
            and not data.get("answers")
            and not data.get("infoboxes")
        ):
            logger.info(
                "web_search time_range fallback | time_range=%s → 不限 | query=%r",
                time_range,
                query,
            )
            data = await self._search(searxng_url, query, categories, time_range=None)

        # 原始查询无结果时，尝试改写查询
        if (
            rewritten != query
            and data is not None
            and not data.get("results")
            and not data.get("answers")
            and not data.get("infoboxes")
        ):
            logger.info(
                "web_search 改写兜底 | 原始=%r → 改写=%r",
                query,
                rewritten,
            )
            data = await self._search(
                searxng_url, rewritten, categories, time_range=None
            )

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
            data = await self._search(searxng_url, rewritten, "general", time_range)

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

        reply = await _format_results(query, data, rewritten)
        logger.info(
            "web_search 完成 | query=%r | results=%d | answers=%d",
            query,
            len(results),
            len(answers),
        )
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)

    async def _search(
        self,
        searxng_url: str,
        query: str,
        categories: str,
        time_range: str | None = None,
    ) -> dict | None:
        """执行单次 SearXNG 搜索，返回 JSON 数据或 None（请求失败）。"""
        search_params = {
            "q": query,
            "format": "json",
            "categories": categories,
        }
        if time_range:
            search_params["time_range"] = time_range
        url = f"{searxng_url}/search?{urlencode(search_params)}"

        logger.info("web_search SearXNG 请求 | url=%s", url)

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                result_count = len(data.get("results", []))
                logger.info("web_search SearXNG 响应 | results=%d", result_count)
                return data
        except httpx.TimeoutException:
            logger.warning(
                "SearXNG 请求超时 | query=%r | categories=%s", query, categories
            )
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
