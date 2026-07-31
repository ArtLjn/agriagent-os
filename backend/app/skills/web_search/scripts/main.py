"""网络搜索 Skill — 基于 SearchHub 获取 Agent 友好的实时网络信息。"""

import logging

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.shared.llm import LlmNotConfiguredError, get_llm
from app.shared.config import settings
from app.infra.skill_cache import cached
from app.skills.web_search.scripts.support import (
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
_TIME_RANGE_MAP = {
    "day": "d",
    "week": "w",
    "month": "m",
    "year": "y",
    "d": "d",
    "w": "w",
    "m": "m",
    "y": "y",
}
_EMBEDDING_IMPORTANT_KEYWORDS = (
    "价格",
    "行情",
    "走势",
    "政策",
    "补贴",
    "公告",
    "公示",
    "标准",
    "法规",
    "病害",
    "病虫害",
    "防治",
    "用药",
    "农药",
    "安全",
    "预警",
    "上市",
)
_EMBEDDING_NOISE_KEYWORDS = (
    "今天",
    "今日",
    "最新",
    "实时",
    "当前",
    "近期",
    "最近",
    "可靠",
    "准确",
    "精筛",
    "精排",
    "关键信息",
    "交叉验证",
    "多来源",
)


def _web_search_cache_key(params: dict) -> str:
    cache_fields = (
        "query",
        "categories",
        "time_range",
        "top_k",
        "enable_fetch",
        "enable_embedding_filter",
        "domain",
        "region",
        "crop",
    )
    parts = []
    for field in cache_fields:
        value = params.get(field)
        if isinstance(value, str):
            value = value.strip()
        parts.append(f"{field}={value!r}")
    return "web:" + "|".join(parts)


def _has_explicit_embedding_filter(params: dict) -> bool:
    return (
        "enable_embedding_filter" in params
        and params.get("enable_embedding_filter") is not None
    )


def _should_auto_enable_embedding_filter(
    query: str,
    categories: str,
    time_range: str | None,
    params: dict,
) -> bool:
    if _has_explicit_embedding_filter(params):
        return bool(params.get("enable_embedding_filter"))

    text = " ".join(
        str(value)
        for value in (
            query,
            categories,
            time_range or "",
            params.get("domain", ""),
            params.get("region", ""),
            params.get("crop", ""),
        )
        if value
    )
    has_important_signal = any(
        keyword in text for keyword in _EMBEDDING_IMPORTANT_KEYWORDS
    )
    has_noise_signal = (
        any(keyword in text for keyword in _EMBEDDING_NOISE_KEYWORDS)
        or categories == "news"
        or bool(time_range)
    )
    return has_important_signal and has_noise_signal


def _searchhub_response_needs_embedding_retry(data: dict | None) -> bool:
    if not data:
        return False
    agent = data.get("agent") or {}
    return agent.get("answerable") is False


def _with_embedding_filter(params: dict, enabled: bool) -> dict:
    next_params = dict(params)
    next_params["enable_embedding_filter"] = enabled
    return next_params


def _secret_value(name: str) -> str:
    value = getattr(settings.secrets, name, "")
    if isinstance(value, str):
        return value.strip()
    return ""


def _get_searchhub_base_url() -> str:
    base_url = _secret_value("searchhub_base_url")
    return base_url.rstrip("/")


def _get_searchhub_api_key() -> str:
    return _secret_value("searchhub_api_key")


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
        import app.skills.web_search.scripts.support as support

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
                    "description": "兼容旧参数。搜索类别: general(通用), news(新闻), "
                    "images(图片), videos(视频)。默认 general。",
                    "enum": ["general", "news", "images", "videos"],
                },
                "time_range": {
                    "type": "string",
                    "description": "时间过滤: day/d(当天), week/w(一周), month/m(一月), year/y(一年)。",
                    "enum": ["day", "week", "month", "year", "d", "w", "m", "y"],
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数，默认 5，范围 1-20。",
                    "minimum": 1,
                    "maximum": 20,
                },
                "enable_fetch": {
                    "type": "boolean",
                    "description": "是否请求 SearchHub 抓取网页正文。",
                },
                "enable_embedding_filter": {
                    "type": "boolean",
                    "description": (
                        "是否启用 SearchHub embedding 精筛。开启后服务端会扩大候选，"
                        "再按 query 与结果文本的向量相似度过滤排序；未显式传入时运行时自动判断。"
                    ),
                },
                "domain": {
                    "type": "string",
                    "description": "领域参数，例如 agriculture。",
                },
                "region": {
                    "type": "string",
                    "description": "地区参数，例如 苏州。",
                },
                "crop": {
                    "type": "string",
                    "description": "作物参数，例如 西瓜。",
                },
            },
            "required": ["query"],
        }

    @cached(
        ttl_seconds=600,
        key_fn=_web_search_cache_key,
    )
    async def execute(self, params: dict, context) -> SkillResult:
        query = params.get("query", "").strip()
        if not query:
            return SkillResult(status=ResultStatus.FAILED, reply="请提供搜索关键词。")

        searchhub_base_url = _get_searchhub_base_url()
        if not searchhub_base_url:
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

        search_params = _with_embedding_filter(
            params,
            _should_auto_enable_embedding_filter(query, categories, time_range, params),
        )

        # 优先用原始查询搜索，更稳定；SearchHub 会在服务端继续做查询理解和证据聚合。
        data = await self._search(
            searchhub_base_url, query, categories, time_range, search_params
        )

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
            data = await self._search(
                searchhub_base_url,
                query,
                categories,
                time_range=None,
                params=search_params,
            )

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
                searchhub_base_url,
                rewritten,
                categories,
                time_range=None,
                params=search_params,
            )

        if (
            data is not None
            and not _has_explicit_embedding_filter(params)
            and not search_params.get("enable_embedding_filter")
            and _searchhub_response_needs_embedding_retry(data)
        ):
            logger.info(
                "web_search embedding 精筛重试 | query=%r | reason=weak_evidence",
                query,
            )
            search_params = _with_embedding_filter(params, True)
            data = await self._search(
                searchhub_base_url, query, categories, time_range, search_params
            )

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
        searchhub_base_url: str,
        query: str,
        categories: str,
        time_range: str | None = None,
        params: dict | None = None,
    ) -> dict | None:
        """执行单次 SearchHub 搜索，返回 JSON 数据或 None（请求失败）。"""
        payload = self._build_searchhub_payload(query, time_range, params or {})
        url = f"{searchhub_base_url}/search"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        api_key = _get_searchhub_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["X-API-Key"] = api_key

        logger.info(
            "web_search SearchHub 请求 | url=%s | query=%r | category=%s",
            url,
            query,
            categories,
        )

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                result_count = len(data.get("results", []))
                logger.info("web_search SearchHub 响应 | results=%d", result_count)
                return data
        except httpx.TimeoutException:
            logger.warning(
                "SearchHub 请求超时 | query=%r | categories=%s", query, categories
            )
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "SearchHub HTTP 错误 | status=%d | query=%r",
                e.response.status_code,
                query,
            )
            return None
        except Exception as e:
            logger.warning(
                "SearchHub 请求失败 | query=%r | error=%s: %s",
                query,
                type(e).__name__,
                e,
            )
            return None

    def _build_searchhub_payload(
        self, query: str, time_range: str | None, params: dict
    ) -> dict:
        payload = {
            "query": query,
            "top_k": params.get("top_k", 5),
            "enable_fetch": bool(params.get("enable_fetch", False)),
            "enable_embedding_filter": bool(
                params.get("enable_embedding_filter", False)
            ),
        }
        mapped_time_range = _TIME_RANGE_MAP.get(time_range or "")
        if mapped_time_range:
            payload["time_range"] = mapped_time_range
        for key in ("domain", "region", "crop"):
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                payload[key] = value.strip()
        return payload
