"""web-search skill.

Provider 优先级（参考 archive/backend/app/skills/web_search/scripts/main.py）：
  1. SearchHub — 配置环境变量 SEARCHHUB_API_KEY 和 SEARCHHUB_BASE_URL 时启用
  2. DuckDuckGo HTML — 无需 key，作为 fallback

两种 provider 返回统一结构：
    {"query": str, "count": int, "results": [{"title", "url", "snippet"}, ...]}
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext

logger = logging.getLogger(__name__)

# DuckDuckGo HTML 接口（无 key）
_DDG_URL = "https://html.duckduckgo.com/html/"

_REQUEST_TIMEOUT = 15.0

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


# ─────────────────────────────────────────────────────────────
# SearchHub provider
# ─────────────────────────────────────────────────────────────


async def _searchhub_search(
    query: str, top_k: int, base_url: str, api_key: str
) -> dict[str, Any]:
    """调用 SearchHub /search 接口。"""
    payload = {
        "query": query,
        "top_k": top_k,
        "enable_fetch": False,
        "enable_embedding_filter": False,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-API-Key"] = api_key

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(
            f"{base_url}/search", json=payload, headers=headers
        )
        resp.raise_for_status()
        return resp.json()


def _format_searchhub(data: dict[str, Any], query: str) -> dict[str, Any]:
    """将 SearchHub 响应转换为统一结构。"""
    raw_results = data.get("results") or []
    results = []
    for item in raw_results[:10]:  # 上限 10
        title = item.get("title") or ""
        url = item.get("url") or item.get("link") or ""
        snippet = item.get("content") or item.get("snippet") or ""
        if title and url:
            results.append({
                "title": _strip_html(title),
                "url": url,
                "snippet": _strip_html(snippet)[:300],
            })

    answers = data.get("answers") or []
    if answers and not results:
        # 无 results 但有 answer，把 answer 包装成单条
        first = answers[0] if isinstance(answers[0], str) else (
            answers[0].get("answer") or answers[0].get("content") or ""
        )
        if first:
            results.append({
                "title": f"SearchHub Answer: {query}",
                "url": "",
                "snippet": str(first)[:500],
            })

    return {
        "query": query,
        "provider": "searchhub",
        "count": len(results),
        "results": results,
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


async def _ddg_search(query: str, limit: int) -> dict[str, Any]:
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

    return {
        "query": query,
        "provider": "duckduckgo",
        "count": len(results),
        "results": results,
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
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        query = (params.get("query") or "").strip()
        if not query:
            return SkillResult(error="query 不能为空")
        top_k = max(1, min(int(params.get("top_k", 5)), 10))

        # ── Try SearchHub first ────────────────────────────────
        base_url, api_key = _searchhub_config()
        if base_url and api_key:
            try:
                data = await _searchhub_search(query, top_k, base_url, api_key)
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
            data = await _ddg_search(query, top_k)
        except httpx.HTTPError as exc:
            return SkillResult(error=f"搜索失败: {exc}")
        except Exception as exc:  # noqa: BLE001
            return SkillResult(error=f"搜索异常: {exc}")

        if not data["results"]:
            return SkillResult(data={
                "query": query,
                "count": 0,
                "message": f"未找到关于「{query}」的结果",
            })

        return SkillResult(data=data)


skill = WebSearchSkill()
