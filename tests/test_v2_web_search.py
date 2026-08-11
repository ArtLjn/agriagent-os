from types import SimpleNamespace
from importlib import import_module

import pytest

web_search = import_module("agent.skills.web-search.scripts.main")


class _Response:
    def __init__(self, *, data=None, text=""):
        self._data = data
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _SearchHubClient:
    last_payload = None

    def __init__(self, *_args, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, _url, *, json, headers):
        self.last_payload = json
        type(self).last_payload = json
        return _Response(data={"results": []})


class _FallbackClient:
    def __init__(self, *_args, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, *_args, **_kwargs):
        return _Response(
            text=(
                '<a class="result__a" href="https://example.com/page">'
                "结果标题</a>"
                '<a class="result__snippet">搜索摘要</a>'
            )
        )

    async def get(self, _url):
        return _Response(
            text=(
                "<html><script>ignore()</script><article>"
                "这是网页正文内容。"
                "</article></html>"
            )
        )


@pytest.mark.asyncio
async def test_searchhub_maps_time_range_and_sends_fetch(monkeypatch):
    monkeypatch.setattr(web_search.httpx, "AsyncClient", _SearchHubClient)

    await web_search._searchhub_search(
        "西瓜价格",
        5,
        "https://search.example.com",
        "test-key",
        time_range="month",
        enable_fetch=True,
    )

    assert _SearchHubClient.last_payload == {
        "query": "西瓜价格",
        "top_k": 5,
        "enable_fetch": True,
        "content_mode": "evidence",
        "fetch_top_k": 5,
        "max_content_chars": 8_000,
        "evidence_chars": 2_000,
        "time_range": "m",
    }


@pytest.mark.asyncio
async def test_execute_explicitly_defaults_fetch_to_true(monkeypatch):
    calls = []

    async def fake_search(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "results": [
                {
                    "title": "正文来源",
                    "url": "https://example.com",
                    "content": "完整网页正文",
                    "snippet": "短摘要",
                }
            ]
        }

    monkeypatch.setattr(
        web_search, "_searchhub_config", lambda: ("https://search", "key")
    )
    monkeypatch.setattr(web_search, "_searchhub_search", fake_search)

    skill = web_search.WebSearchSkill()
    params = skill.enrich_params({"query": "西瓜种植"}, SimpleNamespace())
    result = await skill.execute(params, SimpleNamespace())

    assert params["enable_fetch"] is True
    assert params["content_mode"] == "evidence"
    assert calls[0][1]["enable_fetch"] is True
    assert calls[0][1]["content_mode"] == "evidence"
    assert result.data["results"][0]["snippet"] == "短摘要"
    assert result.data["results"][0]["content_available"] is True
    assert "content" not in result.data["results"][0]


@pytest.mark.asyncio
async def test_duckduckgo_fallback_fetches_page_content(monkeypatch):
    monkeypatch.setattr(web_search.httpx, "AsyncClient", _FallbackClient)

    result = await web_search._ddg_search(
        "西瓜种植",
        1,
        enable_fetch=True,
    )

    assert result["provider"] == "duckduckgo"
    assert result["results"][0]["content"] == "这是网页正文内容。"
    assert result["results"][0]["snippet"] == "这是网页正文内容。"


@pytest.mark.asyncio
async def test_execute_compacts_duckduckgo_content(monkeypatch):
    monkeypatch.setattr(web_search, "_searchhub_config", lambda: ("", ""))
    monkeypatch.setattr(web_search.httpx, "AsyncClient", _FallbackClient)

    skill = web_search.WebSearchSkill()
    result = await skill.execute(
        skill.enrich_params({"query": "西瓜种植"}, SimpleNamespace()),
        SimpleNamespace(),
    )

    item = result.data["results"][0]
    assert item["content_available"] is True
    assert item["snippet"] == "这是网页正文内容。"
    assert "content" not in item
    assert result.data["trace"]["provider"] == "duckduckgo"
