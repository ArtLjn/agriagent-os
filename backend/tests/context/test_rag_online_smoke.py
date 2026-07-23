"""外部 QuillRAG 线上只读冒烟测试。"""

from __future__ import annotations

from dataclasses import dataclass
import os

import pytest

from app.infra.quillrag_client import QuillRAGClient, QuillRAGRetrieveResult


pytestmark = pytest.mark.no_db

SMOKE_QUERY = "番茄苗期管理"
SUPPORTED_MODES = frozenset({"vector", "bm25", "hybrid"})


@dataclass(frozen=True, slots=True)
class OnlineRAGSmokeConfig:
    url: str
    api_key: str
    collection: str
    mode: str
    top_k: int
    timeout_seconds: float
    retry: int


def test_online_smoke_failure_message_redacts_api_key() -> None:
    message = _failure_message(
        "retrieve",
        "认证失败：请检查 RAG_SERVICE__API_KEY，原始片段 placeholder-redaction-token。",
        api_key="placeholder-redaction-token",
        result=QuillRAGRetrieveResult(
            ok=False,
            error_code="http_401",
            status_code=401,
        ),
    )

    assert "placeholder-redaction-token" not in message
    assert "[REDACTED]" in message


def test_online_quillrag_health_and_retrieve_smoke() -> None:
    config = _load_online_config_or_skip()
    client = QuillRAGClient(
        base_url=config.url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
        retry=config.retry,
    )

    health = client.health()
    if not health.ok:
        _fail_for_unhealthy_service(
            endpoint="health",
            api_key=config.api_key,
            error_code=health.error_code,
            status_code=health.status_code,
        )

    result = client.retrieve(
        query=SMOKE_QUERY,
        collection=config.collection,
        mode=config.mode,
        top_k=config.top_k,
        filters={},
        use_hyde=False,
    )
    if not result.ok:
        _fail_for_unhealthy_service(
            endpoint="retrieve",
            api_key=config.api_key,
            error_code=result.error_code,
            status_code=result.status_code,
            result=result,
        )
    if not result.results:
        pytest.fail(
            _failure_message(
                "retrieve",
                (
                    "retrieve 返回空结果；线上只读冒烟要求目标 collection 至少能命中"
                    f" harmless query：{SMOKE_QUERY}。请检查 RAG_SERVICE__DEFAULT_COLLECTION"
                    "、RAG_SERVICE__DEFAULT_MODE 和线上知识库状态。"
                ),
                api_key=config.api_key,
                result=result,
            )
        )


def _load_online_config_or_skip() -> OnlineRAGSmokeConfig:
    url = _env("RAG_SERVICE__URL")
    api_key = _env("RAG_SERVICE__API_KEY")
    missing = [
        name
        for name, value in (
            ("RAG_SERVICE__URL", url),
            ("RAG_SERVICE__API_KEY", api_key),
        )
        if not value
    ]
    if missing:
        pytest.skip(
            "缺少线上 RAG 冒烟配置，跳过只读 retrieve 验证："
            + "、".join(missing)
        )

    mode = _env("RAG_SERVICE__DEFAULT_MODE", "hybrid")
    if mode not in SUPPORTED_MODES:
        pytest.fail("RAG_SERVICE__DEFAULT_MODE 只能是 vector、bm25 或 hybrid。")

    return OnlineRAGSmokeConfig(
        url=url,
        api_key=api_key,
        collection=_env("RAG_SERVICE__DEFAULT_COLLECTION", "agri_knowledge"),
        mode=mode,
        top_k=_positive_int_env("RAG_SERVICE__TOP_K", default=3),
        timeout_seconds=_positive_float_env(
            "RAG_SERVICE__TIMEOUT_SECONDS",
            default=5.0,
        ),
        retry=_non_negative_int_env("RAG_SERVICE__RETRY", default=0),
    )


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _positive_int_env(name: str, *, default: int) -> int:
    raw = _env(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        pytest.fail(f"{name} 必须是正整数。")
    if value <= 0:
        pytest.fail(f"{name} 必须大于 0。")
    return value


def _non_negative_int_env(name: str, *, default: int) -> int:
    raw = _env(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        pytest.fail(f"{name} 必须是非负整数。")
    if value < 0:
        pytest.fail(f"{name} 不能小于 0。")
    return value


def _positive_float_env(name: str, *, default: float) -> float:
    raw = _env(name, str(default))
    try:
        value = float(raw)
    except ValueError:
        pytest.fail(f"{name} 必须是正数。")
    if value <= 0:
        pytest.fail(f"{name} 必须大于 0。")
    return value


def _fail_for_unhealthy_service(
    *,
    endpoint: str,
    api_key: str,
    error_code: str | None,
    status_code: int | None,
    result: QuillRAGRetrieveResult | None = None,
) -> None:
    if status_code in {401, 403}:
        reason = "认证失败：请检查 RAG_SERVICE__API_KEY 是否匹配目标 QuillRAG 服务。"
    elif status_code is not None and status_code >= 500:
        reason = "QuillRAG 服务返回 5xx：请检查服务进程、Qdrant 和 embedding provider 状态。"
    elif error_code in {"timeout", "network_error"}:
        reason = "网络不可达或超时：请检查 RAG_SERVICE__URL、网络连通性和超时时间。"
    else:
        reason = "QuillRAG 只读冒烟失败：请检查 URL、collection、mode 和服务日志。"
    pytest.fail(
        _failure_message(
            endpoint,
            reason,
            api_key=api_key,
            result=result,
            error_code=error_code,
            status_code=status_code,
        )
    )


def _failure_message(
    endpoint: str,
    reason: str,
    *,
    api_key: str,
    result: QuillRAGRetrieveResult | None = None,
    error_code: str | None = None,
    status_code: int | None = None,
) -> str:
    if result is not None:
        error_code = result.error_code or error_code
        status_code = result.status_code or status_code
    message = (
        f"{endpoint} 线上只读冒烟失败：{reason}"
        f" error_code={error_code or 'unknown'} status_code={status_code or 'unknown'}"
    )
    return _redact_secret(message, api_key)


def _redact_secret(text: str, secret: str) -> str:
    if not secret:
        return text
    return text.replace(secret, "[REDACTED]")
