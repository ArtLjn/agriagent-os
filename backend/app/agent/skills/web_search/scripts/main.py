"""网络搜索 Skill — 基于自建 SearXNG 获取实时网络信息。"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from html import unescape
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

_TIME_RANGE_KEYWORDS = ["最新", "今天", "近期", "最近", "当前", "现在", "实时", "行情", "价格", "走势"]


def _detect_search_category(query: str) -> str:
    """基于关键词规则快速判断搜索分类（轻量 fallback）。"""
    q = query.lower()
    if any(kw in q for kw in _NEWS_KEYWORDS):
        return "news"
    return "general"


def _detect_time_range(query: str) -> str | None:
    """基于关键词判断是否需要时间过滤。返回 SearXNG time_range 值。"""
    if any(kw in query for kw in _TIME_RANGE_KEYWORDS):
        return "month"
    return None


def _extract_keywords(query: str) -> list[str]:
    """从查询中提取核心关键词。先按空格/标点拆分，再做双字滑动窗口。"""
    stopwords = {"的", "了", "吗", "是", "在", "有", "和", "与", "及", "等", "都",
                 "个", "一", "不", "这", "那", "我", "你", "他", "她", "它",
                 "查", "找", "搜", "看", "问", "帮", "请", "能", "会", "要",
                 "如何", "怎么", "什么", "为什么", "哪", "哪些", "多少"}
    # 按标点和空格拆分
    parts = re.split(r"[\s,，。？?！!、/]+", query)
    keywords = []
    for p in parts:
        p = p.strip()
        if not p or p in stopwords:
            continue
        if len(p) <= 4:
            keywords.append(p)
        else:
            # 长词拆分为双字片段
            keywords.extend(p[i:i+2] for i in range(len(p) - 1))
    if not keywords:
        keywords = [query[i:i+2] for i in range(max(len(query) - 1, 1))]
    return keywords


def _compute_relevance(item: dict, keywords: list[str]) -> float:
    """计算单条结果与查询关键词的相关性得分 (0~1)。"""
    title = (item.get("title") or "").lower()
    content = (item.get("content") or "").lower()
    text = f"{title} {content}"
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return hits / len(keywords)


def _deduplicate(items: list[dict]) -> list[dict]:
    """相似标题去重，只保留得分最高的。"""
    original_count = len(items)
    seen_titles: dict[str, int] = {}
    result = []
    duped_titles: list[str] = []
    for i, item in enumerate(items):
        title = (item.get("title") or "").strip()
        # 标准化：去括号内容和空格
        clean = re.sub(r"[（(].*?[）)]", "", title).strip()
        clean = re.sub(r"\s+", "", clean)
        if not clean:
            result.append(item)
            continue
        if clean in seen_titles:
            prev_idx = seen_titles[clean]
            prev_score = items[prev_idx].get("score", 0)
            curr_score = item.get("score", 0)
            duped_titles.append(title[:30])
            if curr_score > prev_score:
                result = [x for x in result if seen_titles.get(
                    re.sub(r"[（(].*?[）)]", "", (x.get("title") or "").strip()).replace(" ", ""), -1
                ) != prev_idx]
                seen_titles[clean] = i
                result.append(item)
        else:
            seen_titles[clean] = i
            result.append(item)
    if duped_titles:
        logger.info(
            "web_search 去重 | 原始=%d | 去重后=%d | 移除: %s",
            original_count, len(result), duped_titles,
        )
    return result


def _rerank_results(items: list[dict], query: str, rewritten: str = "") -> list[dict]:
    """综合 SearXNG 得分、关键词相关性和时间新鲜度重排序。"""
    if not items:
        return items

    # 核心关键词（原始查询）权重高，补充关键词（改写查询）权重低
    core_kws = _extract_keywords(query)
    bonus_kws = []
    if rewritten and rewritten != query:
        bonus_kws = [kw for kw in _extract_keywords(rewritten) if kw not in core_kws]
    now = datetime.now(timezone.utc)

    scored = []
    for item in items:
        searx_score = item.get("score", 0)

        # 核心关键词命中率（权重 0.7）：必须包含原始查询实体才算相关
        core_hits = _compute_relevance(item, core_kws)
        # 补充关键词命中率（权重 0.3）：改写查询的加分项
        bonus_hits = _compute_relevance(item, bonus_kws) if bonus_kws else 0.0
        relevance = core_hits * 0.7 + bonus_hits * 0.3

        # 时间新鲜度：30 天内加分，超过 365 天降权
        time_bonus = 0.0
        published = item.get("publishedDate", "")
        days_ago = None
        if published:
            try:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                days_ago = (now - pub_dt).days
                if days_ago <= 30:
                    time_bonus = 0.3
                elif days_ago <= 90:
                    time_bonus = 0.15
                elif days_ago > 365:
                    time_bonus = -0.2
            except (ValueError, TypeError):
                pass

        final = searx_score * 0.4 + relevance * 10 * 0.6 + time_bonus
        scored.append((final, item))

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

    scored.sort(key=lambda x: x[0], reverse=True)

    # 排序后 Top5 摘要日志
    top5_titles = [item.get("title", "")[:30] for _, item in scored[:5]]
    logger.info(
        "web_search 重排序完成 | 核心=%s | 补充=%s | Top5: %s",
        core_kws[:5],
        bonus_kws[:5] if bonus_kws else [],
        " > ".join(top5_titles),
    )

    return [item for _, item in scored]


async def _rewrite_query(raw_query: str) -> str:
    """用 LLM 将用户查询改写成更精准的搜索关键词。

    只要求输出改写后的查询，格式极简，降低模型跑偏概率。
    若 LLM 不可用则回退到原查询。
    """
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
        # 防御：过滤掉模型输出的解释性前缀/后缀
        for prefix in ["改写后：", "改写：", "查询：", "关键词：", '"', "'"]:
            if rewritten.startswith(prefix):
                rewritten = rewritten[len(prefix):].strip()
        # 只取第一行，防止模型输出多行导致内容混乱
        rewritten = rewritten.splitlines()[0].strip()
        if len(rewritten) >= 3 and rewritten != raw_query:
            logger.info("web_search 查询改写 | 原始=%r | 改写=%r", raw_query, rewritten)
            return rewritten
    except (LlmNotConfiguredError, Exception):
        pass
    return raw_query


async def _fetch_page_content(url: str, max_length: int = 400) -> str | None:
    """抓取网页正文，提取纯文本摘要。"""
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
            text = resp.text

            # 优先提取 article/main 标签内容
            body_match = re.search(
                r"<article[^>]*>(.*?)</article>", text, re.DOTALL | re.IGNORECASE
            )
            if not body_match:
                body_match = re.search(
                    r"<main[^>]*>(.*?)</main>", text, re.DOTALL | re.IGNORECASE
                )
            if not body_match:
                body_match = re.search(
                    r"<body[^>]*>(.*?)</body>", text, re.DOTALL | re.IGNORECASE
                )

            if body_match:
                content = body_match.group(1)
                # 移除 script/style/nav/header/footer/aside 标签及内容
                for tag in ["script", "style", "nav", "header", "footer", "aside"]:
                    content = re.sub(
                        rf"<{tag}[^>]*>.*?</{tag}>",
                        " ",
                        content,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                # 移除所有 HTML 标签
                content = re.sub(r"<[^>]+>", " ", content)
                # 解码 HTML 实体
                content = unescape(content)
                # 清理空白
                content = re.sub(r"\s+", " ", content).strip()
                # 过滤掉太短的内容（可能是登录页/错误页）
                if len(content) > 30:
                    return content[:max_length]
    except Exception:
        pass
    return None


async def _format_results(query: str, data: dict, rewritten: str = "") -> str:
    """将 SearXNG 完整响应格式化为带编号引用的结构化文本。

    对摘要过短的结果尝试抓取网页补全内容。
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

    # 搜索结果 — 相关性重排序 + 去重
    items = data.get("results", [])
    raw_count = len(items)
    items = _deduplicate(items)
    items = _rerank_results(items, query, rewritten)

    if items:
        logger.info(
            "web_search 结果处理 | 原始=%d | 去重=%d | 重排序后=%d",
            raw_count, len(items), min(len(items), 15),
        )

    if not items and not answers and not infoboxes:
        return f"未找到与「{query}」相关的结果。"

    source_count = 0
    if items:
        lines.append(f"搜索关键词: {query}")
        lines.append(f"找到 {len(items)} 条结果")
        lines.append("")

        # 过滤无效结果：标题为空或 URL 异常短的视为垃圾数据
        valid_items = [
            item for item in items
            if item.get("title") and len(item.get("url", "")) > 4
        ]

        # 对前 5 条摘要过短的结果并行抓取网页补全
        short_items = [
            item for item in valid_items[:5]
            if len(item.get("content", "") or "") < 80
        ]
        fetched_contents: dict[str, str] = {}
        if short_items:
            fetch_tasks = [
                _fetch_page_content(item.get("url", ""), max_length=300)
                for item in short_items
            ]
            results = await asyncio.gather(*fetch_tasks)
            for item, fetched in zip(short_items, results):
                if fetched:
                    fetched_contents[item.get("url", "")] = fetched

        for i, item in enumerate(valid_items[:15], 1):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            content = item.get("content", "") or ""
            engines = item.get("engines", [])
            published = item.get("publishedDate", "")

            # 用抓取的网页内容补全短摘要
            if len(content) < 80 and url in fetched_contents:
                content = fetched_contents[url]

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
            return SkillResult(
                status=ResultStatus.FAILED, reply="请提供搜索关键词。"
            )

        searxng_url = _get_searxng_url()
        if not searxng_url:
            return SkillResult(
                status=ResultStatus.FAILED, reply="搜索服务未配置。"
            )

        # 1. 查询改写（LLM）— 仅作辅助，不替代原始查询
        rewritten = await _rewrite_query(query)

        # 2. 分类判断（规则，零成本）
        categories = params.get("categories") or _detect_search_category(query)

        # 3. 时间范围检测（含"价格/最新"等词时限定近一个月）
        time_range = params.get("time_range") or _detect_time_range(query)

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
        if time_range and data is not None and not data.get("results") and not data.get("answers") and not data.get("infoboxes"):
            logger.info(
                "web_search time_range fallback | time_range=%s → 不限 | query=%r",
                time_range,
                query,
            )
            data = await self._search(searxng_url, query, categories, time_range=None)

        # 原始查询无结果时，尝试改写查询
        if rewritten != query and data is not None and not data.get("results") and not data.get("answers") and not data.get("infoboxes"):
            logger.info(
                "web_search 改写兜底 | 原始=%r → 改写=%r",
                query,
                rewritten,
            )
            data = await self._search(searxng_url, rewritten, categories, time_range=None)

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
        self, searxng_url: str, query: str, categories: str, time_range: str | None = None
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
