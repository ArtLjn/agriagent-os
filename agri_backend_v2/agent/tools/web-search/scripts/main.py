"""web-search skill.

Provider 优先级（参考 archive/backend/app/skills/web_search/scripts/main.py）：
  1. SearchHub — 配置环境变量 SEARCHHUB_API_KEY 和 SEARCHHUB_BASE_URL 时启用
  2. DuckDuckGo HTML — 无需 key，作为 fallback

两种 provider 返回统一结构：
    {"query": str, "count": int, "results": [{"title", "url", "snippet", "content_available"}, ...]}
"""

from __future__ import annotations

import asyncio
from html.parser import HTMLParser
import logging
import os
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from agent.domains.harness.tools.base import Skill, SkillResult
from agent.domains.harness.tools.context import SkillContext

logger = logging.getLogger(__name__)

# DuckDuckGo HTML 接口（无 key）
_DDG_URL = "https://html.duckduckgo.com/html/"

_REQUEST_TIMEOUT = 15.0
_FETCH_TIMEOUT = 10.0
_MAX_CONTENT_LENGTH = 8_000
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

# 简单结果解析：标题 + URL + 摘要
_DDG_RESULT_PATTERN = re.compile(
    r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL,
)


def _searchhub_config() -> tuple[str, str]:
    """从环境变量读取 SearchHub 配置。返回 (base_url, api_key)。"""
    base_url = os.getenv("SEARCHHUB_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("SEARCHHUB_API_KEY", "").strip()
    return base_url, api_key


def _strip_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本。"""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    return text.strip()


class _PageTextParser(HTMLParser):
    """提取网页正文候选文本，避免 fallback 只返回搜索引擎摘要。"""

    _IGNORED_TAGS = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag.lower() in self._IGNORED_TAGS:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            text = re.sub(r"\s+", " ", data).strip()
            if text:
                self.parts.append(text)


def _extract_page_text(html: str) -> str:
    """把 HTML 转成有限长度的纯文本，失败时返回空正文。"""
    parser = _PageTextParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        return ""
    return " ".join(parser.parts)[:_MAX_CONTENT_LENGTH]


async def _fetch_page_text(client: httpx.AsyncClient, url: str) -> str:
    """抓取单个搜索结果页面；单页失败不影响其他结果。"""
    try:
        response = await client.get(url)
        response.raise_for_status()
        return _extract_page_text(response.text)
    except Exception as exc:  # noqa: BLE001
        logger.info("web search page fetch skipped: url=%s error=%s", url, exc)
        return ""


async def _enrich_with_page_text(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """为 fallback 结果并发抓正文，抓取失败时保留原搜索摘要。"""
    if not results:
        return results
    async with httpx.AsyncClient(
        timeout=_FETCH_TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        },
    ) as client:
        contents = await asyncio.gather(
            *(_fetch_page_text(client, item["url"]) for item in results),
        )
    for item, content in zip(results, contents):
        if content:
            item["content"] = content
            item["snippet"] = content[:500]
    return results


# ─────────────────────────────────────────────────────────────
# SearchHub provider
# ─────────────────────────────────────────────────────────────


async def _searchhub_search(
    query: str,
    top_k: int,
    base_url: str,
    api_key: str,
    *,
    time_range: str | None = None,
    enable_fetch: bool = True,
    content_mode: str = "evidence",
    fetch_top_k: int | None = None,
    max_content_chars: int = 8_000,
    evidence_chars: int = 2_000,
    enable_embedding_filter: bool | None = None,
    domain: str | None = None,
    region: str | None = None,
    crop: str | None = None,
) -> dict[str, Any]:
    """调用 SearchHub /search 接口。

    time_range / domain / region / crop 等高级参数仅在传入时加入 payload，
    让 SearchHub 启用对应增强流程。enable_embedding_filter=None 时不传，
    由 SearchHub 运行时自动判断。
    """
    payload: dict[str, Any] = {
        "query": query,
        "top_k": top_k,
        "enable_fetch": enable_fetch,
        "content_mode": content_mode,
        "fetch_top_k": fetch_top_k or min(top_k, 5),
        "max_content_chars": max_content_chars,
        "evidence_chars": evidence_chars,
    }
    if time_range:
        payload["time_range"] = _TIME_RANGE_MAP.get(time_range, time_range)
    if enable_embedding_filter is not None:
        payload["enable_embedding_filter"] = enable_embedding_filter
    if domain:
        payload["domain"] = domain
    if region:
        payload["region"] = region
    if crop:
        payload["crop"] = crop

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-API-Key"] = api_key

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(f"{base_url}/search", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _format_searchhub(data: dict[str, Any], query: str) -> dict[str, Any]:
    """将 SearchHub 响应转换为统一结构。"""
    raw_results = data.get("results") or []
    results = []
    for item in raw_results[:10]:  # 上限 10
        title = item.get("title") or ""
        url = item.get("url") or item.get("link") or ""
        content = _strip_html(str(item.get("content") or ""))
        snippet = _strip_html(str(item.get("snippet") or ""))
        if title and url:
            result = {
                "title": _strip_html(title),
                "url": url,
                "snippet": (snippet or content)[:500],
                "content_available": bool(content),
            }
            results.append(result)

    answers = data.get("answers") or []
    if answers and not results:
        # 无 results 但有 answer，把 answer 包装成单条
        first = (
            answers[0]
            if isinstance(answers[0], str)
            else (answers[0].get("answer") or answers[0].get("content") or "")
        )
        if first:
            results.append(
                {
                    "title": f"SearchHub Answer: {query}",
                    "url": "",
                    "snippet": str(first)[:500],
                }
            )

    return {
        "query": query,
        "provider": "searchhub",
        "count": len(results),
        "results": results,
        "evidence": data.get("evidence") or {},
        "agent": data.get("agent") or {},
        "summary": str((data.get("grounded_answer") or {}).get("markdown") or "")[
            :2_000
        ],
        "trace": _compact_searchhub_trace(data.get("trace") or {}),
    }


def _compact_searchhub_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """只保留 Agent 需要的追踪摘要，避免把完整 pipeline trace 回灌上下文。"""
    return {
        "request_id": trace.get("request_id"),
        "provider": trace.get("provider"),
        "search_time": trace.get("search_time", 0),
        "fetch_time": trace.get("fetch_time", 0),
        "result_count": trace.get("result_count", 0),
        "content_mode": trace.get("content_mode"),
        "fetch_requested": trace.get("fetch_requested"),
        "fetch_enabled": trace.get("fetch_enabled"),
        "fetched_count": trace.get("fetched_count", 0),
        "returned_content_chars": trace.get("returned_content_chars", 0),
        "error": trace.get("error"),
    }


# ─────────────────────────────────────────────────────────────
# DuckDuckGo provider (fallback)
# ─────────────────────────────────────────────────────────────


def _parse_ddg(html: str, limit: int) -> list[dict[str, str]]:
    """从 DuckDuckGo HTML 响应解析结果。"""
    results: list[dict[str, str]] = []
    for match in _DDG_RESULT_PATTERN.finditer(html):
        url = match.group(1)
        if "uddg=" in url:
            qs = parse_qs(urlparse(url).query)
            url = qs.get("uddg", [url])[0]
        title = _strip_html(match.group(2))
        snippet = _strip_html(match.group(3))
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


async def _ddg_search(
    query: str,
    limit: int,
    *,
    enable_fetch: bool = True,
) -> dict[str, Any]:
    """DuckDuckGo HTML 搜索，无需 API key。"""
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(
            _DDG_URL,
            data={"q": query, "b": ""},  # b= 关闭重定向
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        resp.raise_for_status()
        results = _parse_ddg(resp.text, limit)

    if enable_fetch:
        results = await _enrich_with_page_text(results)

    return {
        "query": query,
        "provider": "duckduckgo",
        "count": len(results),
        "results": results,
        "fetch_requested": enable_fetch,
        "fetch_enabled": enable_fetch,
    }


def _format_ddg(data: dict[str, Any], query: str) -> dict[str, Any]:
    """压缩 fallback 结果，避免抓取正文绕过 SearchHub 的响应预算。"""
    results = []
    for item in (data.get("results") or [])[:10]:
        title = _strip_html(str(item.get("title") or ""))
        url = str(item.get("url") or "")
        content = _strip_html(str(item.get("content") or ""))
        snippet = _strip_html(str(item.get("snippet") or ""))
        if title and url:
            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": (snippet or content)[:500],
                    "content_available": bool(content),
                }
            )
    return {
        "query": query,
        "provider": "duckduckgo",
        "count": len(results),
        "results": results,
        "trace": {
            "provider": "duckduckgo",
            "fetch_requested": bool(data.get("fetch_requested", False)),
            "fetch_enabled": bool(data.get("fetch_enabled", False)),
            "fetched_count": sum(
                1 for item in (data.get("results") or []) if item.get("content")
            ),
            "returned_content_chars": 0,
        },
    }


# ─────────────────────────────────────────────────────────────
# Skill
# ─────────────────────────────────────────────────────────────


class WebSearchSkill(Skill):
    """搜索互联网获取最新信息。

    优先 SearchHub（配置 SEARCHHUB_API_KEY 时启用），否则降级 DuckDuckGo。
    """

    kind = "local"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "搜索互联网获取实时信息。当用户问最新新闻、市场价格、上市时间、"
            "最新政策、实时热点、百科知识等需要网络搜索的问题时调用。"
            "触发词: 最新、新闻、价格、上市、政策、热点、搜索、查一下。"
        )

    @property
    def risk_level(self) -> str:
        return "read"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如'2026年西瓜价格走势'",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数，默认 5，范围 1-10",
                    "minimum": 1,
                    "maximum": 10,
                },
                "time_range": {
                    "type": "string",
                    "description": "日期筛选：day/week/month/year",
                    "enum": ["day", "week", "month", "year"],
                },
                "enable_fetch": {
                    "type": "boolean",
                    "description": "是否抓取网页正文（默认 true；SearchHub 或 DuckDuckGo fallback 均生效）",
                    "default": True,
                },
                "content_mode": {
                    "type": "string",
                    "enum": ["none", "evidence"],
                    "default": "evidence",
                    "description": "返回模式。默认 evidence，只返回摘要和结构化证据，不返回网页正文。",
                },
                "enable_embedding_filter": {
                    "type": "boolean",
                    "description": "是否启用 embedding 精筛（仅 SearchHub 生效）",
                },
                "domain": {
                    "type": "string",
                    "description": "领域参数，如 agriculture",
                },
                "region": {
                    "type": "string",
                    "description": "地区参数，如 苏州",
                },
                "crop": {
                    "type": "string",
                    "description": "作物参数，如 西瓜",
                },
            },
            "required": ["query"],
        }

    def enrich_params(self, params: dict[str, Any], ctx) -> dict[str, Any]:
        """把正文抓取默认值显式写入 action/trace，避免 LLM 省略可选参数。"""
        enriched = dict(params)
        if enriched.get("enable_fetch") is None:
            enriched["enable_fetch"] = True
        if enriched.get("content_mode") not in {"none", "evidence"}:
            enriched["content_mode"] = "evidence"
        return enriched

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        query = (params.get("query") or "").strip()
        if not query:
            return SkillResult(error="query 不能为空")
        top_k = max(1, min(int(params.get("top_k", 5)), 10))
        time_range = params.get("time_range")
        enable_fetch = params.get("enable_fetch") is not False
        content_mode = params.get("content_mode")
        if content_mode not in {"none", "evidence"}:
            content_mode = "evidence"
        enable_embedding_filter = params.get("enable_embedding_filter")
        domain = params.get("domain")
        region = params.get("region")
        crop = params.get("crop")

        # ── Try SearchHub first ────────────────────────────────
        base_url, api_key = _searchhub_config()
        if base_url and api_key:
            try:
                data = await _searchhub_search(
                    query,
                    top_k,
                    base_url,
                    api_key,
                    time_range=time_range,
                    enable_fetch=enable_fetch,
                    content_mode=content_mode,
                    fetch_top_k=min(top_k, 5),
                    max_content_chars=8_000,
                    evidence_chars=2_000,
                    enable_embedding_filter=enable_embedding_filter,
                    domain=domain,
                    region=region,
                    crop=crop,
                )
                formatted = _format_searchhub(data, query)
                if formatted["results"]:
                    return SkillResult(data=formatted)
                logger.info("searchhub returned empty, fallback to ddg")
            except Exception as exc:  # noqa: BLE001
                logger.warning("searchhub failed, fallback to ddg: %s", exc)
        else:
            logger.debug("searchhub not configured, using duckduckgo")

        # ── Fallback: DuckDuckGo ────────────────────────────────
        try:
            data = await _ddg_search(query, top_k, enable_fetch=enable_fetch)
        except httpx.HTTPError as exc:
            return SkillResult(error=f"搜索失败: {exc}")
        except Exception as exc:  # noqa: BLE001
            return SkillResult(error=f"搜索异常: {exc}")

        if not data["results"]:
            return SkillResult(
                data={
                    "query": query,
                    "count": 0,
                    "message": f"未找到关于「{query}」的结果",
                }
            )

        return SkillResult(data=_format_ddg(data, query))


skill = WebSearchSkill()
