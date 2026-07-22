"""QuillRAG 只读 HTTP client 契约测试。"""

import json

import httpx
import pytest

from app.infra.quillrag_client import QuillRAGClient


PLACEHOLDER_API_KEY = "placeholder-rag-key"


def test_health_uses_x_api_key_header() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["api_key"] = request.headers["X-API-Key"]
        return httpx.Response(200, json={"status": "ok"})

    client = QuillRAGClient(
        base_url="http://rag.local",
        api_key=PLACEHOLDER_API_KEY,
        transport=httpx.MockTransport(handler),
    )

    result = client.health()

    assert result.ok is True
    assert captured == {"path": "/health", "api_key": PLACEHOLDER_API_KEY}


def test_retrieve_sends_payload_and_normalizes_success_response() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        captured["payload"] = json.loads(request.content)
        captured["api_key"] = request.headers["X-API-Key"]
        return httpx.Response(
            200,
            json={
                "code": "OK",
                "data": {
                    "actual_mode": "bm25",
                    "results": [
                        {
                            "content": "番茄苗低温后需要控水并观察根系。",
                            "score": 0.91,
                            "doc_id": "tomato-cold",
                            "chunk_index": 2,
                            "metadata": {"source": "agri.md", "category": "tomato"},
                        }
                    ],
                },
                "warning": "hybrid_to_bm25_fallback",
            },
        )

    client = QuillRAGClient(
        base_url="http://rag.local/",
        api_key=PLACEHOLDER_API_KEY,
        transport=httpx.MockTransport(handler),
    )

    result = client.retrieve(
        query="番茄苗降温后怎么办",
        collection="agri_knowledge",
        mode="hybrid",
        top_k=3,
        filters={"crop": "tomato"},
        use_hyde=True,
    )

    assert captured["api_key"] == PLACEHOLDER_API_KEY
    assert captured["payload"] == {
        "query": "番茄苗降温后怎么办",
        "collection": "agri_knowledge",
        "mode": "hybrid",
        "top_k": 3,
        "filters": {"crop": "tomato"},
        "use_hyde": True,
    }
    assert result.ok is True
    assert result.actual_mode == "bm25"
    assert result.warning == "hybrid_to_bm25_fallback"
    assert result.results[0].score == 0.91
    assert result.results[0].doc_id == "tomato-cold"
    assert result.results[0].chunk_index == 2
    assert result.results[0].metadata["category"] == "tomato"


def test_network_error_retries_before_success() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(
            200,
            json={"data": {"actual_mode": "hybrid", "results": []}},
        )

    client = QuillRAGClient(
        base_url="http://rag.local",
        api_key="",
        retry=2,
        transport=httpx.MockTransport(handler),
    )

    result = client.retrieve(query="黄瓜霜霉病", collection="agri")

    assert result.ok is True
    assert result.attempts == 2
    assert attempts == 2


def test_5xx_response_is_standardized_without_retry() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error_code": "QDRANT_UNAVAILABLE"})

    client = QuillRAGClient(
        base_url="http://rag.local",
        api_key="",
        retry=3,
        transport=httpx.MockTransport(handler),
    )

    result = client.retrieve(query="黄瓜霜霉病", collection="agri")

    assert result.ok is False
    assert result.status_code == 503
    assert result.error_code == "http_503"
    assert result.attempts == 1
    assert attempts == 1


@pytest.mark.parametrize(
    ("exc", "error_code"),
    [
        (httpx.TimeoutException("timeout"), "timeout"),
        (httpx.ConnectError("connection failed"), "network_error"),
    ],
)
def test_timeout_and_network_failure_are_standardized(
    exc: httpx.HTTPError,
    error_code: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        exc.request = request
        raise exc

    client = QuillRAGClient(
        base_url="http://rag.local",
        api_key="",
        retry=1,
        transport=httpx.MockTransport(handler),
    )

    result = client.retrieve(query="黄瓜霜霉病", collection="agri")

    assert result.ok is False
    assert result.error_code == error_code
    assert result.attempts == 2
    assert result.error_message
