"""web_search skill 单元测试。"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.skills.web_search.scripts.main import (
    WebSearchSkill,
    _format_results,
    _detect_search_category,
    _detect_time_range,
    _extract_keywords,
    _compute_relevance,
    _deduplicate,
    _rerank_results,
    _rewrite_query,
    _fetch_page_content,
)
from app.infra.skill_cache import clear_cache


# ─── Meta 测试 ───


class TestWebSearchMeta:
    def setup_method(self):
        clear_cache("web_search")
        self.skill = WebSearchSkill()

    def test_name(self):
        assert self.skill.name() == "web_search"

    def test_description_contains_trigger_words(self):
        desc = self.skill.description()
        assert "搜索" in desc
        assert "价格" in desc

    def test_parameters_schema_required_query(self):
        schema = self.skill.parameters_schema()
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "query" in schema["required"]

    def test_parameters_schema_optional_categories(self):
        schema = self.skill.parameters_schema()
        assert "categories" in schema["properties"]
        assert "categories" not in schema["required"]


# ─── 分类检测测试 ───


class TestDetectSearchCategory:
    def test_news_keywords(self):
        assert _detect_search_category("最新西瓜价格") == "news"
        assert _detect_search_category("今天的新闻") == "news"
        assert _detect_search_category("近日报道事件") == "news"
        assert _detect_search_category("刚刚发布公告") == "news"

    def test_general_queries(self):
        assert _detect_search_category("西瓜价格") == "general"
        assert _detect_search_category("如何种植水稻") == "general"
        assert _detect_search_category("天气预报") == "general"

    def test_case_insensitive(self):
        assert _detect_search_category("最新") == "news"


# ─── 时间范围检测测试 ───


class TestDetectTimeRange:
    def test_price_keyword(self):
        assert _detect_time_range("西瓜价格") == "month"

    def test_latest_keyword(self):
        assert _detect_time_range("最新新闻") == "month"

    def test_no_match(self):
        assert _detect_time_range("如何种植水稻") is None

    def test_realtime_keyword(self):
        assert _detect_time_range("实时行情") == "month"


# ─── 关键词提取测试 ───


class TestExtractKeywords:
    def test_basic_split(self):
        kws = _extract_keywords("睢宁 西瓜 价格")
        assert "睢宁" in kws
        assert "西瓜" in kws
        assert "价格" in kws

    def test_stops_words_filtered(self):
        kws = _extract_keywords("西瓜 价格 行情")
        assert "西瓜" in kws
        assert "价格" in kws

    def test_fallback_to_full_query(self):
        kws = _extract_keywords("价格")
        assert kws == ["价格"]


# ─── 相关性计算测试 ───


class TestComputeRelevance:
    def test_full_match(self):
        item = {"title": "睢宁西瓜价格行情", "content": "今日睢宁西瓜0.7元/斤"}
        score = _compute_relevance(item, ["睢宁", "西瓜", "价格"])
        assert score == 1.0

    def test_partial_match(self):
        item = {"title": "睢宁县百度百科", "content": "睢宁古有泗睢两水横贯"}
        score = _compute_relevance(item, ["睢宁", "西瓜", "价格"])
        assert 0 < score < 1.0

    def test_no_match(self):
        item = {"title": "天气预报", "content": "明天晴天"}
        score = _compute_relevance(item, ["西瓜", "价格"])
        assert score == 0.0


# ─── 去重测试 ───


class TestDeduplicate:
    def test_removes_similar_titles(self):
        items = [
            {"title": "睢宁县（江苏）_百度百科", "url": "https://a.com", "score": 2.0},
            {"title": "睢宁县_百度百科", "url": "https://b.com", "score": 1.5},
        ]
        result = _deduplicate(items)
        assert len(result) == 1
        assert result[0]["score"] == 2.0

    def test_keeps_different_titles(self):
        items = [
            {"title": "西瓜价格行情", "url": "https://a.com", "score": 1.0},
            {"title": "西瓜种植技术", "url": "https://b.com", "score": 1.0},
        ]
        result = _deduplicate(items)
        assert len(result) == 2

    def test_empty_title_kept(self):
        items = [
            {"title": "", "url": "https://a.com", "score": 1.0},
        ]
        result = _deduplicate(items)
        assert len(result) == 1


# ─── 重排序测试 ───


class TestRerankResults:
    def test_relevance_overrides_searx_score(self):
        """高相关低 SearXNG 得分的结果应排在低相关高得分前面。"""
        items = [
            {
                "title": "睢宁县百科",
                "content": "睢宁历史简介",
                "score": 5.0,
                "url": "https://a.com",
            },
            {
                "title": "睢宁西瓜价格",
                "content": "睢宁西瓜价格0.7元/斤",
                "score": 1.0,
                "url": "https://b.com",
            },
        ]
        result = _rerank_results(items, "睢宁西瓜价格")
        assert result[0]["title"] == "睢宁西瓜价格"

    def test_empty_list(self):
        assert _rerank_results([], "test") == []

    def test_time_bonus_for_recent(self):
        """近期发布的结果应获得加分。"""
        from datetime import datetime, timedelta, timezone

        recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()

        items = [
            {
                "title": "旧结果",
                "content": "西瓜价格",
                "score": 2.0,
                "url": "https://a.com",
                "publishedDate": old,
            },
            {
                "title": "新结果",
                "content": "西瓜价格",
                "score": 2.0,
                "url": "https://b.com",
                "publishedDate": recent,
            },
        ]
        result = _rerank_results(items, "西瓜价格")
        assert result[0]["title"] == "新结果"


class TestRewriteQuery:
    @pytest.mark.asyncio
    async def test_llm_rewrite_success(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "2026年6月西瓜批发市场价格走势"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "app.agent.skills.web_search.scripts.main.get_llm", return_value=mock_llm
        ):
            result = await _rewrite_query("西瓜价格")

        assert result == "2026年6月西瓜批发市场价格走势"

    @pytest.mark.asyncio
    async def test_llm_rewrite_strips_prefix(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "改写后：2026年西瓜市场行情"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "app.agent.skills.web_search.scripts.main.get_llm", return_value=mock_llm
        ):
            result = await _rewrite_query("西瓜")

        assert result == "2026年西瓜市场行情"

    @pytest.mark.asyncio
    async def test_llm_rewrite_takes_first_line(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "2026年西瓜行情\n这是额外解释"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "app.agent.skills.web_search.scripts.main.get_llm", return_value=mock_llm
        ):
            result = await _rewrite_query("西瓜")

        assert result == "2026年西瓜行情"
        assert "额外" not in result

    @pytest.mark.asyncio
    async def test_llm_not_configured_fallback(self):
        from app.agent.llm import LlmNotConfiguredError

        with patch(
            "app.agent.skills.web_search.scripts.main.get_llm",
            side_effect=LlmNotConfiguredError("no key"),
        ):
            result = await _rewrite_query("西瓜价格")

        assert result == "西瓜价格"

    @pytest.mark.asyncio
    async def test_llm_returns_same_query_fallback(self):
        """LLM 返回与原查询相同时不改写。"""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "西瓜价格"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "app.agent.skills.web_search.scripts.main.get_llm", return_value=mock_llm
        ):
            result = await _rewrite_query("西瓜价格")

        assert result == "西瓜价格"

    @pytest.mark.asyncio
    async def test_llm_returns_too_short_fallback(self):
        """LLM 返回太短的结果不改写。"""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "西瓜"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "app.agent.skills.web_search.scripts.main.get_llm", return_value=mock_llm
        ):
            result = await _rewrite_query("西瓜价格行情走势")

        assert result == "西瓜价格行情走势"


# ─── 网页抓取测试 ───


class TestFetchPageContent:
    @pytest.mark.asyncio
    async def test_extract_article_content(self):
        article_text = "西瓜价格稳中有升，批发均价1.2元/斤，市场需求旺盛，供应充足。各地产区陆续上市，价格波动明显。"
        html = f"<html><body><article>{article_text}</article></body></html>"

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_page_content("https://example.com")

        assert result is not None
        assert "西瓜价格" in result

    @pytest.mark.asyncio
    async def test_strips_script_and_style(self):
        html = (
            "<html><body><article>"
            "<script>var x=1;</script>"
            "<style>.a{color:red}</style>"
            "正文内容足够长了，超过五十字的内容才能返回，这里是正文部分，还需要更多。"
            "</article></body></html>"
        )

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_page_content("https://example.com")

        assert result is not None
        assert "var x" not in result
        assert "color:red" not in result
        assert "正文内容" in result

    @pytest.mark.asyncio
    async def test_too_short_content_returns_none(self):
        """页面内容太短（如登录页）返回 None。"""
        html = "<html><body><article>短内容</article></body></html>"

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_page_content("https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_request_failure_returns_none(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_page_content("https://example.com")

        assert result is None


# ─── 格式化测试 ───


class TestFormatResults:
    @pytest.mark.asyncio
    async def test_empty_all(self):
        data = {"results": [], "answers": [], "infoboxes": []}
        result = await _format_results("test", data)
        assert "未找到" in result
        assert "test" in result

    @pytest.mark.asyncio
    async def test_single_result(self):
        data = {
            "results": [
                {
                    "title": "西瓜价格走势",
                    "url": "https://example.com",
                    "content": "2026年西瓜价格下降" * 10,
                    "engines": ["bing", "baidu"],
                    "score": 1.5,
                }
            ],
            "answers": [],
            "infoboxes": [],
        }
        result = await _format_results("西瓜", data)
        assert "[1] 西瓜价格走势" in result
        assert "https://example.com" in result
        assert "bing" in result
        assert "请严格基于以上搜索结果回答" in result

    @pytest.mark.asyncio
    async def test_filters_invalid_results(self):
        """标题为空或 URL 异常短的结果应被过滤。"""
        data = {
            "results": [
                {
                    "title": "正常结果",
                    "url": "https://example.com",
                    "content": "正常内容" * 20,
                    "engines": [],
                    "score": 2.0,
                },
                {
                    "title": "URL太短",
                    "url": "h",
                    "content": "被过滤",
                    "engines": [],
                    "score": 1.5,
                },
                {
                    "title": "",
                    "url": "https://example.com/other",
                    "content": "也被过滤",
                    "engines": [],
                    "score": 1.0,
                },
            ],
            "answers": [],
            "infoboxes": [],
        }
        # mock 网页抓取避免真实网络请求
        with patch(
            "app.agent.skills.web_search.scripts.main._fetch_page_content",
            return_value=None,
        ):
            result = await _format_results("test", data)
        assert "[1] 正常结果" in result
        assert "URL太短" not in result
        # 只有 1 条有效结果，不应出现 [2] 开头的结果行
        result_lines = result.split("\n")
        assert not any(line.startswith("[2]") for line in result_lines)

    @pytest.mark.asyncio
    async def test_max_15_results(self):
        """最多展示 15 条有效结果。"""
        data = {
            "results": [
                {
                    "title": f"结果{i}",
                    "url": f"https://ex.com/{i}",
                    "engines": [],
                    "score": float(20 - i),
                }
                for i in range(20)
            ],
            "answers": [],
            "infoboxes": [],
        }
        result = await _format_results("test", data)
        assert "[15]" in result
        assert "[16]" not in result

    @pytest.mark.asyncio
    async def test_results_sorted_by_score(self):
        data = {
            "results": [
                {"title": "低分", "score": 0.1, "engines": [], "url": "https://a.com"},
                {"title": "高分", "score": 2.0, "engines": [], "url": "https://b.com"},
                {"title": "中分", "score": 1.0, "engines": [], "url": "https://c.com"},
            ],
            "answers": [],
            "infoboxes": [],
        }
        result = await _format_results("test", data)
        lines = [
            line
            for line in result.split("\n")
            if line.startswith(("[1]", "[2]", "[3]"))
        ]
        assert "高分" in lines[0]
        assert "中分" in lines[1]
        assert "低分" in lines[2]

    @pytest.mark.asyncio
    async def test_answers_displayed(self):
        data = {
            "results": [],
            "answers": ["42"],
            "infoboxes": [],
        }
        result = await _format_results("test", data)
        assert "直接回答" in result
        assert "42" in result

    @pytest.mark.asyncio
    async def test_suggestions_displayed(self):
        data = {
            "results": [
                {"title": "t", "engines": [], "score": 1, "url": "https://a.com"}
            ],
            "answers": [],
            "infoboxes": [],
            "suggestions": ["西瓜价格", "西瓜种植"],
        }
        result = await _format_results("test", data)
        assert "相关搜索" in result
        assert "西瓜价格" in result

    @pytest.mark.asyncio
    async def test_no_grounding_when_no_results(self):
        data = {
            "results": [],
            "answers": [],
            "infoboxes": [],
        }
        result = await _format_results("test", data)
        assert "请严格基于" not in result
        assert "未找到" in result

    @pytest.mark.asyncio
    async def test_short_summary_fetched(self):
        """摘要过短时触发网页抓取补全。"""
        data = {
            "results": [
                {
                    "title": "短摘要结果",
                    "url": "https://example.com/short",
                    "content": "短",  # < 80 字符，触发抓取
                    "engines": [],
                    "score": 1.0,
                },
            ],
            "answers": [],
            "infoboxes": [],
        }
        mock_fetched = "这是从网页抓取到的完整内容，足够长以替代短摘要。"

        with patch(
            "app.agent.skills.web_search.scripts.main._fetch_page_content",
            return_value=mock_fetched,
        ):
            result = await _format_results("test", data)

        assert "这是从网页抓取到的完整内容" in result


# ─── 正常流程测试 ───


class TestWebSearchNormal:
    def setup_method(self):
        clear_cache("web_search")
        self.skill = WebSearchSkill()

    @pytest.mark.asyncio
    async def test_successful_search(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "西瓜价格",
                    "url": "https://example.com",
                    "content": "批发价0.6元/斤" * 10,
                    "engines": ["bing"],
                    "score": 1.0,
                }
            ],
            "answers": [],
            "infoboxes": [],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="西瓜价格",
            ),
            patch(
                "app.agent.skills.web_search.scripts.main._fetch_page_content",
                return_value=None,
            ),
        ):
            result = await self.skill.execute({"query": "西瓜价格"}, None)

        assert result.status.value == "success"
        assert "西瓜价格" in result.reply

    @pytest.mark.asyncio
    async def test_no_results(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [],
            "answers": [],
            "infoboxes": [],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="不存在的关键词",
            ),
        ):
            result = await self.skill.execute({"query": "不存在的关键词"}, None)

        assert result.status.value == "success"
        assert "未找到" in result.reply

    @pytest.mark.asyncio
    async def test_with_explicit_categories(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "t",
                    "engines": ["bing"],
                    "score": 1.0,
                    "url": "https://a.com",
                }
            ],
            "answers": [],
            "infoboxes": [],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="test",
            ),
            patch(
                "app.agent.skills.web_search.scripts.main._fetch_page_content",
                return_value=None,
            ),
        ):
            await self.skill.execute({"query": "test", "categories": "news"}, None)

        first_call_url = mock_client.get.call_args_list[0][0][0]
        assert "categories=news" in first_call_url

    @pytest.mark.asyncio
    async def test_auto_detect_news_category(self):
        """含新闻关键词的查询自动分类为 news。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "新闻",
                    "engines": ["bing"],
                    "score": 1.0,
                    "url": "https://a.com",
                }
            ],
            "answers": [],
            "infoboxes": [],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="最新西瓜新闻",
            ),
            patch(
                "app.agent.skills.web_search.scripts.main._fetch_page_content",
                return_value=None,
            ),
        ):
            await self.skill.execute({"query": "最新西瓜新闻"}, None)

        first_call_url = mock_client.get.call_args_list[0][0][0]
        assert "categories=news" in first_call_url

    @pytest.mark.asyncio
    async def test_unconfigured_searxng_url(self):
        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = ""

        with (
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="test",
            ),
        ):
            result = await self.skill.execute({"query": "test"}, None)

        assert result.status.value == "failed"
        assert "未配置" in result.reply


# ─── 异常处理测试 ───


class TestWebSearchError:
    def setup_method(self):
        clear_cache("web_search")
        self.skill = WebSearchSkill()

    @pytest.mark.asyncio
    async def test_empty_query(self):
        result = await self.skill.execute({"query": ""}, None)
        assert result.status.value == "failed"
        assert "搜索关键词" in result.reply

    @pytest.mark.asyncio
    async def test_missing_query(self):
        result = await self.skill.execute({}, None)
        assert result.status.value == "failed"

    @pytest.mark.asyncio
    async def test_timeout(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="test",
            ),
        ):
            result = await self.skill.execute({"query": "test"}, None)

        assert result.status.value == "failed"
        assert "异常" in result.reply

    @pytest.mark.asyncio
    async def test_http_error(self):
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_response
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="test",
            ),
        ):
            result = await self.skill.execute({"query": "test"}, None)

        assert result.status.value == "failed"
        assert "异常" in result.reply

    @pytest.mark.asyncio
    async def test_connection_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="test",
            ),
        ):
            result = await self.skill.execute({"query": "test"}, None)

        assert result.status.value == "failed"
        assert "异常" in result.reply

    @pytest.mark.asyncio
    async def test_news_fallback_to_general(self):
        """news 分类无结果时自动 fallback 到 general。"""
        empty_response = MagicMock()
        empty_response.status_code = 200
        empty_response.raise_for_status = MagicMock()
        empty_response.json.return_value = {
            "results": [],
            "answers": [],
            "infoboxes": [],
        }

        fallback_response = MagicMock()
        fallback_response.status_code = 200
        fallback_response.raise_for_status = MagicMock()
        fallback_response.json.return_value = {
            "results": [
                {
                    "title": "fallback结果",
                    "engines": ["bing"],
                    "score": 1.0,
                    "url": "https://a.com",
                }
            ],
            "answers": [],
            "infoboxes": [],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[empty_response, fallback_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = "http://test:8888"

        with (
            patch(
                "app.agent.skills.web_search.scripts.main.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
            patch(
                "app.agent.skills.web_search.scripts.main._rewrite_query",
                return_value="fallback_test_unique",
            ),
            patch(
                "app.agent.skills.web_search.scripts.main._fetch_page_content",
                return_value=None,
            ),
        ):
            result = await self.skill.execute(
                {"query": "fallback_test_unique", "categories": "news"}, None
            )

        assert result.status.value == "success"
        assert "fallback结果" in result.reply
        assert mock_client.get.call_count == 2
        # 第二次调用应使用 general
        second_call_url = mock_client.get.call_args_list[1][0][0]
        assert "categories=general" in second_call_url
