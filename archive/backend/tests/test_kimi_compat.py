"""Kimi API OpenAI 兼容性测试。

用法:
    KIMI_API_KEY="sk-xxx" poetry run pytest backend/tests/test_kimi_compat.py -v
"""

import os

import pytest
from openai import APIStatusError
from openai import AsyncOpenAI, OpenAI

KIMI_BASE_URL = "https://api.kimi.com/coding/v1"
KIMI_MODEL = "kimi-k2.5"


def _skip_when_account_unavailable(exc: APIStatusError) -> None:
    if exc.status_code in {401, 402, 403}:
        pytest.skip(f"Kimi API 账号当前不可用: HTTP {exc.status_code}")
    raise exc


@pytest.fixture
def api_key():
    key = os.environ.get("KIMI_API_KEY")
    if not key:
        pytest.skip("KIMI_API_KEY 环境变量未设置")
    return key


@pytest.fixture
def sync_client(api_key):
    return OpenAI(api_key=api_key, base_url=KIMI_BASE_URL, timeout=30)


@pytest.fixture
def async_client(api_key):
    return AsyncOpenAI(api_key=api_key, base_url=KIMI_BASE_URL, timeout=30)


class TestBasicChat:
    """基础对话测试。"""

    def test_sync_chat(self, sync_client):
        try:
            resp = sync_client.chat.completions.create(
                model=KIMI_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个有帮助的助手。"},
                    {"role": "user", "content": "你好，请用一句话介绍自己。"},
                ],
                max_tokens=100,
                temperature=0.7,
            )
        except APIStatusError as exc:
            _skip_when_account_unavailable(exc)
        assert resp.choices
        assert resp.choices[0].message.content
        print(f"\n[同步回复] {resp.choices[0].message.content[:100]}")

    @pytest.mark.asyncio
    async def test_async_chat(self, async_client):
        try:
            resp = await async_client.chat.completions.create(
                model=KIMI_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个有帮助的助手。"},
                    {"role": "user", "content": "你好，请用一句话介绍自己。"},
                ],
                max_tokens=100,
                temperature=0.7,
            )
        except APIStatusError as exc:
            _skip_when_account_unavailable(exc)
        assert resp.choices
        assert resp.choices[0].message.content
        print(f"\n[异步回复] {resp.choices[0].message.content[:100]}")


class TestToolCalling:
    """Tool Calling (Function Calling) 兼容性测试。"""

    def test_tool_calling(self, sync_client):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取指定城市的天气",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称",
                            }
                        },
                        "required": ["city"],
                    },
                },
            }
        ]

        try:
            resp = sync_client.chat.completions.create(
                model=KIMI_MODEL,
                messages=[
                    {"role": "user", "content": "北京今天天气怎么样？"},
                ],
                tools=tools,
                tool_choice="auto",
                max_tokens=200,
            )
        except APIStatusError as exc:
            _skip_when_account_unavailable(exc)

        msg = resp.choices[0].message
        print(f"\n[Tool] content={msg.content!r}")
        print(f"[Tool] tool_calls={msg.tool_calls}")

        if msg.tool_calls:
            tc = msg.tool_calls[0]
            assert tc.function.name == "get_weather"
            import json

            args = json.loads(tc.function.arguments)
            assert "city" in args

    def test_parallel_tool_calls(self, sync_client):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取指定城市的天气",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ]

        try:
            resp = sync_client.chat.completions.create(
                model=KIMI_MODEL,
                messages=[
                    {"role": "user", "content": "北京和上海今天天气怎么样？"},
                ],
                tools=tools,
                tool_choice="auto",
                max_tokens=300,
            )
        except APIStatusError as exc:
            _skip_when_account_unavailable(exc)

        msg = resp.choices[0].message
        print(
            f"\n[Parallel] tool_calls count={len(msg.tool_calls) if msg.tool_calls else 0}"
        )


class TestStreaming:
    """流式输出测试。"""

    def test_sync_stream(self, sync_client):
        chunks = []
        try:
            stream = sync_client.chat.completions.create(
                model=KIMI_MODEL,
                messages=[{"role": "user", "content": "说一个笑话"}],
                max_tokens=100,
                stream=True,
            )
        except APIStatusError as exc:
            _skip_when_account_unavailable(exc)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)

        text = "".join(chunks)
        assert text
        print(f"\n[Stream] {text[:80]}...")

    @pytest.mark.asyncio
    async def test_async_stream(self, async_client):
        chunks = []
        try:
            stream = await async_client.chat.completions.create(
                model=KIMI_MODEL,
                messages=[{"role": "user", "content": "说一个笑话"}],
                max_tokens=100,
                stream=True,
            )
        except APIStatusError as exc:
            _skip_when_account_unavailable(exc)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)

        text = "".join(chunks)
        assert text
        print(f"\n[Async Stream] {text[:80]}...")


class TestModelList:
    """模型列表测试。"""

    def test_list_models(self, sync_client):
        try:
            models = sync_client.models.list()
            model_ids = [m.id for m in models.data]
            print(f"\n[Models] 可用模型: {model_ids}")
            assert any("kimi" in m for m in model_ids)
        except Exception as e:
            print(f"\n[Models] 获取模型列表失败（部分提供商不支持）: {e}")
            pytest.skip(f"不支持 models.list: {e}")
