"""Web search Skill 支撑函数。"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from html import unescape

import httpx
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import LlmNotConfiguredError, get_llm

logger = logging.getLogger(__name__)

NEWS_KEYWORDS = [
    "最新",
    "新闻",
    "今天",
    "近日",
    "刚刚",
    "报道",
    "事件",
    "发布会",
    "公告",
    "通知",
]

TIME_RANGE_KEYWORDS = [
    "最新",
    "今天",
    "近期",
    "最近",
    "当前",
    "现在",
    "实时",
    "行情",
    "价格",
    "走势",
]


def detect_search_category(query: str) -> str:
    """基于关键词规则快速判断搜索分类。"""
    q = query.lower()
    if any(keyword in q for keyword in NEWS_KEYWORDS):
        return "news"
    return "general"


def detect_time_range(query: str) -> str | None:
    """基于关键词判断是否需要时间过滤。"""
    if any(keyword in query for keyword in TIME_RANGE_KEYWORDS):
        return "month"
    return None


async def rewrite_query(raw_query: str) -> str:
    """用 LLM 将用户查询改写成更精准的搜索关键词。"""
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


async def format_results(query: str, data: dict, rewritten: str = "") -> str:
    """将 SearXNG 完整响应格式化为带编号引用的结构化文本。"""
    lines: list[str] = []
    answers = data.get("answers", [])
    if answers:
        lines.append("直接回答:")
        for answer in answers:
            lines.append(f"  {answer}")
        lines.append("")

    infoboxes = data.get("infoboxes", [])
    for box in infoboxes:
        title = box.get("infobox", "")
        content = box.get("content", "")
        if title:
            lines.append(f"📋 {title}")
        if content:
            lines.append(f"  {content}")
        lines.append("")

    items = data.get("results", [])
    raw_count = len(items)
    items = _deduplicate(items)
    items = _rerank_results(items, query, rewritten)

    if items:
        logger.info(
            "web_search 结果处理 | 原始=%d | 去重=%d | 重排序后=%d",
            raw_count,
            len(items),
            min(len(items), 15),
        )

    if not items and not answers and not infoboxes:
        return f"未找到与「{query}」相关的结果。"

    source_count = await _append_search_results(lines, query, items)
    _append_suggestions(lines, data.get("suggestions", []))
    if source_count > 0:
        lines.append("---")
        lines.append(
            "请严格基于以上搜索结果回答用户问题。"
            "回答时用 [编号] 标注信息来源，如 [1][2]。"
            "如果搜索结果不足以回答问题，请如实告知用户。"
        )

    return "\n".join(lines)


async def _append_search_results(
    lines: list[str], query: str, items: list[dict]
) -> int:
    if not items:
        return 0

    lines.append(f"搜索关键词: {query}")
    lines.append(f"找到 {len(items)} 条结果")
    lines.append("")

    valid_items = [
        item for item in items if item.get("title") and len(item.get("url", "")) > 4
    ]
    fetched_contents = await _fetch_short_result_contents(valid_items)
    source_count = 0
    for index, item in enumerate(valid_items[:15], 1):
        title = item.get("title", "无标题")
        url = item.get("url", "")
        content = item.get("content", "") or ""
        engines = item.get("engines", [])
        published = item.get("publishedDate", "")
        if len(content) < 80 and url in fetched_contents:
            content = fetched_contents[url]

        source_count = index
        lines.append(f"[{index}] {title}")
        if published:
            lines.append(f"    时间: {published}")
        if content:
            lines.append(f"    摘要: {content}")
        if url:
            lines.append(f"    链接: {url}")
        if engines:
            lines.append(f"    引擎: {', '.join(engines)}")
        lines.append("")
    return source_count


async def _fetch_short_result_contents(valid_items: list[dict]) -> dict[str, str]:
    short_items = [
        item for item in valid_items[:5] if len(item.get("content", "") or "") < 80
    ]
    fetched_contents: dict[str, str] = {}
    if not short_items:
        return fetched_contents

    fetch_tasks = [
        _fetch_page_content(item.get("url", ""), max_length=300) for item in short_items
    ]
    results = await asyncio.gather(*fetch_tasks)
    for item, fetched in zip(short_items, results):
        if fetched:
            fetched_contents[item.get("url", "")] = fetched
    return fetched_contents


def _append_suggestions(lines: list[str], suggestions: list[str]) -> None:
    if not suggestions:
        return
    lines.append("相关搜索:")
    for suggestion in suggestions[:5]:
        lines.append(f"  - {suggestion}")
    lines.append("")


def _extract_keywords(query: str) -> list[str]:
    stopwords = {
        "的",
        "了",
        "吗",
        "是",
        "在",
        "有",
        "和",
        "与",
        "及",
        "等",
        "都",
        "个",
        "一",
        "不",
        "这",
        "那",
        "我",
        "你",
        "他",
        "她",
        "它",
        "查",
        "找",
        "搜",
        "看",
        "问",
        "帮",
        "请",
        "能",
        "会",
        "要",
        "如何",
        "怎么",
        "什么",
        "为什么",
        "哪",
        "哪些",
        "多少",
    }
    parts = re.split(r"[\s,，。？?！!、/]+", query)
    keywords = []
    for part in parts:
        part = part.strip()
        if not part or part in stopwords:
            continue
        if len(part) <= 4:
            keywords.append(part)
        else:
            keywords.extend(part[index : index + 2] for index in range(len(part) - 1))
    if not keywords:
        keywords = [query[index : index + 2] for index in range(max(len(query) - 1, 1))]
    return keywords


def _compute_relevance(item: dict, keywords: list[str]) -> float:
    title = (item.get("title") or "").lower()
    content = (item.get("content") or "").lower()
    text = f"{title} {content}"
    if not keywords:
        return 0.0
    hits = sum(1 for keyword in keywords if keyword.lower() in text)
    return hits / len(keywords)


def _deduplicate(items: list[dict]) -> list[dict]:
    original_count = len(items)
    seen_titles: dict[str, int] = {}
    result = []
    duped_titles: list[str] = []
    for index, item in enumerate(items):
        title = (item.get("title") or "").strip()
        clean = re.sub(r"[（(].*?[）)]", "", title).strip()
        clean = re.sub(r"\s+", "", clean)
        if not clean:
            result.append(item)
            continue
        if clean in seen_titles:
            _replace_duplicate_if_better(
                item,
                index,
                items,
                result,
                seen_titles,
                duped_titles,
                title,
                clean,
            )
        else:
            seen_titles[clean] = index
            result.append(item)
    if duped_titles:
        logger.info(
            "web_search 去重 | 原始=%d | 去重后=%d | 移除: %s",
            original_count,
            len(result),
            duped_titles,
        )
    return result


def _replace_duplicate_if_better(
    item: dict,
    index: int,
    items: list[dict],
    result: list[dict],
    seen_titles: dict[str, int],
    duped_titles: list[str],
    title: str,
    clean: str,
) -> None:
    prev_idx = seen_titles[clean]
    prev_score = items[prev_idx].get("score", 0)
    curr_score = item.get("score", 0)
    duped_titles.append(title[:30])
    if curr_score <= prev_score:
        return
    result[:] = [
        candidate
        for candidate in result
        if seen_titles.get(_clean_title(candidate.get("title") or ""), -1) != prev_idx
    ]
    seen_titles[clean] = index
    result.append(item)


def _clean_title(title: str) -> str:
    return re.sub(r"[（(].*?[）)]", "", title.strip()).replace(" ", "")


def _rerank_results(items: list[dict], query: str, rewritten: str = "") -> list[dict]:
    if not items:
        return items

    core_keywords = _extract_keywords(query)
    bonus_keywords = []
    if rewritten and rewritten != query:
        bonus_keywords = [
            keyword
            for keyword in _extract_keywords(rewritten)
            if keyword not in core_keywords
        ]
    now = datetime.now(timezone.utc)
    scored = []
    for item in items:
        score = _score_result(item, core_keywords, bonus_keywords, now)
        scored.append((score, item))
    scored.sort(key=lambda entry: entry[0], reverse=True)

    top5_titles = [item.get("title", "")[:30] for _, item in scored[:5]]
    logger.info(
        "web_search 重排序完成 | 核心=%s | 补充=%s | Top5: %s",
        core_keywords[:5],
        bonus_keywords[:5] if bonus_keywords else [],
        " > ".join(top5_titles),
    )
    return [item for _, item in scored]


def _score_result(
    item: dict,
    core_keywords: list[str],
    bonus_keywords: list[str],
    now: datetime,
) -> float:
    searx_score = item.get("score", 0)
    core_hits = _compute_relevance(item, core_keywords)
    bonus_hits = _compute_relevance(item, bonus_keywords) if bonus_keywords else 0.0
    relevance = core_hits * 0.7 + bonus_hits * 0.3
    time_bonus, days_ago = _time_bonus(item, now)
    final = searx_score * 0.4 + relevance * 10 * 0.6 + time_bonus
    logger.debug(
        "rerank | title=%.30s | searx=%.2f | core=%.2f bonus=%.2f rel=%.2f | time=%s(%+.1f) | final=%.2f",
        item.get("title", ""),
        searx_score,
        core_hits,
        bonus_hits,
        relevance,
        f"{days_ago}d" if days_ago is not None else "n/a",
        time_bonus,
        final,
    )
    return final


def _time_bonus(item: dict, now: datetime) -> tuple[float, int | None]:
    published = item.get("publishedDate", "")
    if not published:
        return 0.0, None
    try:
        pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        days_ago = (now - pub_dt).days
    except (ValueError, TypeError):
        return 0.0, None
    if days_ago <= 30:
        return 0.3, days_ago
    if days_ago <= 90:
        return 0.15, days_ago
    if days_ago > 365:
        return -0.2, days_ago
    return 0.0, days_ago


async def _fetch_page_content(url: str, max_length: int = 400) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            resp.raise_for_status()
            return _extract_page_text(resp.text, max_length)
    except Exception:
        return None


def _extract_page_text(html: str, max_length: int) -> str | None:
    body_match = re.search(r"<article[^>]*>(.*?)</article>", html, re.I | re.S)
    if not body_match:
        body_match = re.search(r"<main[^>]*>(.*?)</main>", html, re.I | re.S)
    if not body_match:
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.I | re.S)
    if not body_match:
        return None

    content = body_match.group(1)
    for tag in ["script", "style", "nav", "header", "footer", "aside"]:
        content = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", " ", content, flags=re.I | re.S)
    content = re.sub(r"<[^>]+>", " ", content)
    content = unescape(content)
    content = re.sub(r"\s+", " ", content).strip()
    if len(content) > 30:
        return content[:max_length]
    return None


__all__ = [
    "detect_search_category",
    "detect_time_range",
    "format_results",
    "rewrite_query",
]
