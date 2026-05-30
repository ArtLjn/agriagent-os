"""web_search skill 单元测试。"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.skills.web_search.scripts.main import (
    WebSearchSkill,
    _format_results,
)


# ─── Meta 测试 ───


class TestWebSearchMeta:
    def setup_method(self):
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


# ─── 格式化测试 ───


class TestFormatResults:
    def test_empty_all(self):
        data = {"results": [], "answers": [], "infoboxes": []}
        result = _format_results("test", data)
        assert "未找到" in result
        assert "test" in result

    def test_single_result(self):
        data = {
            "results": [
                {
                    "title": "西瓜价格走势",
                    "url": "https://example.com",
                    "content": "2026年西瓜价格下降",
                    "engines": ["bing", "baidu"],
                    "score": 1.5,
                }
            ],
            "answers": [],
            "infoboxes": [],
        }
        result = _format_results("西瓜", data)
        assert "[1] 西瓜价格走势" in result
        assert "2026年西瓜价格下降" in result
        assert "https://example.com" in result
        assert "bing" in result
        assert "请严格基于以上搜索结果回答" in result

    def test_multiple_results(self):
        data = {
            "results": [
                {
                    "title": f"结果{i}",
                    "url": f"https://ex.com/{i}",
                    "content": f"内容{i}",
                    "engines": ["baidu"],
                    "score": float(i),
                }
                for i in range(5)
            ],
            "answers": [],
            "infoboxes": [],
        }
        result = _format_results("test", data)
        assert "找到 5 条结果" in result

    def test_results_sorted_by_score(self):
        data = {
            "results": [
                {"title": "低分", "score": 0.1, "engines": []},
                {"title": "高分", "score": 2.0, "engines": []},
                {"title": "中分", "score": 1.0, "engines": []},
            ],
            "answers": [],
            "infoboxes": [],
        }
        result = _format_results("test", data)
        lines = [l for l in result.split("\n") if l.startswith(("[1]", "[2]", "[3]"))]
        assert "高分" in lines[0]
        assert "中分" in lines[1]
        assert "低分" in lines[2]

    def test_answers_displayed(self):
        data = {
            "results": [],
            "answers": ["42"],
            "infoboxes": [],
        }
        result = _format_results("test", data)
        assert "直接回答" in result
        assert "42" in result

    def test_infobox_displayed(self):
        data = {
            "results": [],
            "answers": [],
            "infoboxes": [{"infobox": "西瓜", "content": "葫芦科植物"}],
        }
        result = _format_results("西瓜", data)
        assert "西瓜" in result
        assert "葫芦科植物" in result

    def test_suggestions_displayed(self):
        data = {
            "results": [{"title": "t", "engines": [], "score": 1}],
            "answers": [],
            "infoboxes": [],
            "suggestions": ["西瓜价格", "西瓜种植"],
        }
        result = _format_results("test", data)
        assert "相关搜索" in result
        assert "西瓜价格" in result
        assert "[编号]" in result

    def test_published_date(self):
        data = {
            "results": [
                {
                    "title": "新闻",
                    "publishedDate": "2026-05-30",
                    "engines": ["bing"],
                    "score": 1.0,
                }
            ],
            "answers": [],
            "infoboxes": [],
        }
        result = _format_results("test", data)
        assert "2026-05-30" in result

    def test_missing_fields(self):
        data = {
            "results": [{"title": "只有标题"}],
            "answers": [],
            "infoboxes": [],
        }
        result = _format_results("test", data)
        assert "只有标题" in result
        assert "请严格基于以上搜索结果回答" in result

    def test_no_grounding_when_no_results(self):
        data = {
            "results": [],
            "answers": [],
            "infoboxes": [],
        }
        result = _format_results("test", data)
        assert "请严格基于" not in result
        assert "未找到" in result


# ─── 正常流程测试 ───


class TestWebSearchNormal:
    def setup_method(self):
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
                    "content": "批发价0.6元/斤",
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
            patch("app.agent.skills.web_search.scripts.main.httpx.AsyncClient", return_value=mock_client),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
        ):
            result = await self.skill.execute({"query": "西瓜价格"}, None)

        assert result.status.value == "success"
        assert "西瓜价格" in result.reply
        assert "批发价0.6元/斤" in result.reply

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
            patch("app.agent.skills.web_search.scripts.main.httpx.AsyncClient", return_value=mock_client),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
        ):
            result = await self.skill.execute({"query": "不存在的关键词"}, None)

        assert result.status.value == "success"
        assert "未找到" in result.reply

    @pytest.mark.asyncio
    async def test_with_categories(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [{"title": "t", "engines": ["bing"], "score": 1.0}],
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
            patch("app.agent.skills.web_search.scripts.main.httpx.AsyncClient", return_value=mock_client),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
        ):
            await self.skill.execute({"query": "test", "categories": "news"}, None)

        # 第一次调用应使用 news 分类
        first_call_url = mock_client.get.call_args_list[0][0][0]
        assert "categories=news" in first_call_url

    @pytest.mark.asyncio
    async def test_unconfigured_searxng_url(self):
        mock_settings = MagicMock()
        mock_settings.secrets.searxng_url = ""

        with patch("app.agent.skills.web_search.scripts.main.settings", mock_settings):
            result = await self.skill.execute({"query": "test"}, None)

        assert result.status.value == "failed"
        assert "未配置" in result.reply


# ─── 异常处理测试 ───


class TestWebSearchError:
    def setup_method(self):
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
            patch("app.agent.skills.web_search.scripts.main.httpx.AsyncClient", return_value=mock_client),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
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
            patch("app.agent.skills.web_search.scripts.main.httpx.AsyncClient", return_value=mock_client),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
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
            patch("app.agent.skills.web_search.scripts.main.httpx.AsyncClient", return_value=mock_client),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
        ):
            result = await self.skill.execute({"query": "test"}, None)

        assert result.status.value == "failed"
        assert "异常" in result.reply

    @pytest.mark.asyncio
    async def test_news_timeout_fallback_to_general(self):
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
                {"title": "fallback结果", "engines": ["bing"], "score": 1.0}
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
            patch("app.agent.skills.web_search.scripts.main.httpx.AsyncClient", return_value=mock_client),
            patch("app.agent.skills.web_search.scripts.main.settings", mock_settings),
        ):
            result = await self.skill.execute(
                {"query": "fallback_test_unique", "categories": "news"}, None
            )

        assert result.status.value == "success"
        assert "fallback结果" in result.reply
        assert mock_client.get.call_count == 2
