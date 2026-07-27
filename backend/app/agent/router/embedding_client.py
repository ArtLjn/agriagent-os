"""Skill Router embedding 客户端。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx

from app.infra.trace_context import get_trace
from app.shared.config import EmbeddingConfig, settings
from app.shared.logging import log_event


EmbedFn = Callable[[str], list[float]]
logger = logging.getLogger(__name__)


class OllamaEmbeddingClient:
    """调用 Ollama 原生 `/api/embed` 接口。"""

    def __init__(
        self,
        config: EmbeddingConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport

    def embed(self, text: str) -> list[float]:
        if not self._config.base_url:
            raise ValueError("EMBEDDING_BASE_URL_EMPTY")
        started_at = time.perf_counter()
        try:
            response = self._post(text)
        except httpx.HTTPError as exc:
            self._log_call(
                status="failed",
                started_at=started_at,
                input_chars=len(text),
                error_code="EMBEDDING_REQUEST_FAILED",
            )
            raise RuntimeError("EMBEDDING_REQUEST_FAILED") from exc
        try:
            vector = _extract_embedding(response.json())
            if len(vector) != self._config.dimensions:
                raise ValueError("EMBEDDING_DIMENSION_MISMATCH")
        except ValueError as exc:
            self._log_call(
                status="failed",
                started_at=started_at,
                input_chars=len(text),
                error_code=str(exc),
            )
            raise
        self._log_call(
            status="success",
            started_at=started_at,
            input_chars=len(text),
            dimensions=len(vector),
        )
        return vector

    def _post(self, text: str) -> httpx.Response:
        auth = None
        if self._config.username or self._config.password:
            auth = (self._config.username, self._config.password)
        with httpx.Client(
            timeout=self._config.timeout_seconds,
            transport=self._transport,
        ) as client:
            response = client.post(
                f"{self._config.base_url.rstrip('/')}{self._config.endpoint}",
                json={
                    "model": self._config.model,
                    "input": text,
                },
                auth=auth,
            )
        response.raise_for_status()
        return response

    def _log_call(
        self,
        *,
        status: str,
        started_at: float,
        input_chars: int,
        error_code: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        trace = get_trace()
        parsed = urlparse(self._config.base_url)
        endpoint_host = parsed.netloc or parsed.path
        log_event(
            logger,
            logging.INFO if status == "success" else logging.WARNING,
            "skill_router_embedding_call",
            code=error_code,
            request_id=trace.request_id if trace else None,
            session_id=trace.session_id if trace else None,
            status=status,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            data={
                "provider": self._config.provider,
                "model": self._config.model,
                "endpoint_host": endpoint_host,
                "endpoint": self._config.endpoint,
                "input_chars": input_chars,
                "dimensions": dimensions,
            },
        )


def build_router_embedding_fn(
    config: EmbeddingConfig | None = None,
) -> EmbedFn | None:
    """按配置创建 Router embedding 函数，未显式启用时不访问外部服务。"""
    embedding_config = config or settings.embedding
    if not embedding_config.enabled or not embedding_config.base_url:
        return None
    if embedding_config.provider != "ollama":
        return None
    return OllamaEmbeddingClient(embedding_config).embed


def _extract_embedding(payload: dict[str, Any]) -> list[float]:
    embedding = payload.get("embedding")
    if isinstance(embedding, list):
        return [float(value) for value in embedding]
    embeddings = payload.get("embeddings")
    if (
        isinstance(embeddings, list)
        and embeddings
        and isinstance(embeddings[0], list)
    ):
        return [float(value) for value in embeddings[0]]
    raise ValueError("EMBEDDING_RESPONSE_INVALID")


__all__ = [
    "EmbedFn",
    "OllamaEmbeddingClient",
    "build_router_embedding_fn",
]
