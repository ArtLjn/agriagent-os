"""Skill Router embedding client 测试。"""

import base64
import json

import httpx
import pytest

from app.agent.router.embedding_client import (
    OllamaEmbeddingClient,
    build_router_embedding_fn,
)
from app.shared.config import EmbeddingConfig

pytestmark = pytest.mark.no_db


def test_ollama_embedding_client_calls_native_embed_endpoint_with_basic_auth() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["authorization"] = request.headers.get("authorization", "")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    client = OllamaEmbeddingClient(
        EmbeddingConfig(
            enabled=True,
            model="qwen3-embedding:0.6b",
            base_url="https://ollama.example.com",
            endpoint="/api/embed",
            username="ollama",
            password="secret",
            dimensions=3,
        ),
        transport=httpx.MockTransport(handler),
    )

    vector = client.embed("我有哪些欠款")

    expected_auth = base64.b64encode(b"ollama:secret").decode()
    assert vector == [0.1, 0.2, 0.3]
    assert seen["path"] == "/api/embed"
    assert seen["authorization"] == f"Basic {expected_auth}"
    assert json.loads(seen["body"]) == {
        "model": "qwen3-embedding:0.6b",
        "input": "我有哪些欠款",
    }


def test_ollama_embedding_client_accepts_embeddings_array_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.4, 0.5]]})

    client = OllamaEmbeddingClient(
        EmbeddingConfig(
            enabled=True,
            base_url="https://ollama.example.com",
            dimensions=2,
        ),
        transport=httpx.MockTransport(handler),
    )

    assert client.embed("查询欠款") == [0.4, 0.5]


def test_ollama_embedding_client_wraps_http_errors_without_leaking_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client = OllamaEmbeddingClient(
        EmbeddingConfig(
            enabled=True,
            base_url="https://ollama.example.com",
            username="ollama",
            password="secret",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.embed("查询欠款")

    assert str(exc_info.value) == "EMBEDDING_REQUEST_FAILED"
    assert "secret" not in str(exc_info.value)


def test_build_router_embedding_fn_requires_explicit_enabled_flag() -> None:
    embed = build_router_embedding_fn(
        EmbeddingConfig(
            enabled=False,
            base_url="https://ollama.example.com",
        )
    )

    assert embed is None
