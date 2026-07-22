"""QuillRAG 只读 HTTP client。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class QuillRAGDocument:
    """标准化后的单条检索结果。"""

    content: str
    score: float
    doc_id: str | None = None
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QuillRAGRetrieveResult:
    """标准化后的 /retrieve 返回。"""

    ok: bool
    results: list[QuillRAGDocument] = field(default_factory=list)
    actual_mode: str | None = None
    warning: str | None = None
    error_code: str | None = None
    error_message: str = ""
    status_code: int | None = None
    attempts: int = 1


@dataclass(frozen=True, slots=True)
class QuillRAGHealthResult:
    """标准化后的 /health 返回。"""

    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str = ""
    status_code: int | None = None
    attempts: int = 1


class QuillRAGClient:
    """QuillRAG 只读 HTTP client，只暴露 health 与 retrieve。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 3.0,
        retry: int = 1,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retry = max(0, retry)
        self.transport = transport

    def health(self) -> QuillRAGHealthResult:
        """调用 GET /health。"""
        attempts = 0
        for attempt in range(self.retry + 1):
            attempts = attempt + 1
            try:
                response = self._request("GET", "/health")
            except httpx.TimeoutException as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGHealthResult(
                    ok=False,
                    error_code="timeout",
                    error_message=str(exc),
                    attempts=attempts,
                )
            except httpx.HTTPError as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGHealthResult(
                    ok=False,
                    error_code="network_error",
                    error_message=str(exc),
                    attempts=attempts,
                )
            if response.status_code >= 400:
                return QuillRAGHealthResult(
                    ok=False,
                    data=self._safe_json(response),
                    error_code=f"http_{response.status_code}",
                    status_code=response.status_code,
                    attempts=attempts,
                )
            return QuillRAGHealthResult(
                ok=True,
                data=self._safe_json(response),
                status_code=response.status_code,
                attempts=attempts,
            )
        return QuillRAGHealthResult(ok=False, error_code="unknown", attempts=attempts)

    def retrieve(
        self,
        *,
        query: str,
        collection: str,
        mode: str = "hybrid",
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        use_hyde: bool = False,
    ) -> QuillRAGRetrieveResult:
        """调用 POST /retrieve，并把响应标准化为本地模型。"""
        payload = {
            "query": query,
            "collection": collection,
            "mode": mode,
            "top_k": top_k,
            "filters": filters or {},
            "use_hyde": use_hyde,
        }
        attempts = 0
        for attempt in range(self.retry + 1):
            attempts = attempt + 1
            try:
                response = self._request("POST", "/retrieve", json=payload)
            except httpx.TimeoutException as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGRetrieveResult(
                    ok=False,
                    error_code="timeout",
                    error_message=str(exc),
                    attempts=attempts,
                )
            except httpx.HTTPError as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGRetrieveResult(
                    ok=False,
                    error_code="network_error",
                    error_message=str(exc),
                    attempts=attempts,
                )
            if response.status_code >= 400:
                return self._http_failure(response, attempts)
            return self._retrieve_success(response, attempts)
        return QuillRAGRetrieveResult(
            ok=False,
            error_code="unknown",
            attempts=attempts,
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = self._headers()
        if extra_headers := kwargs.pop("headers", None):
            headers.update(extra_headers)
        with httpx.Client(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            return client.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                **kwargs,
            )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    def _http_failure(
        self,
        response: httpx.Response,
        attempts: int,
    ) -> QuillRAGRetrieveResult:
        body = self._safe_json(response)
        message = str(body.get("message") or body.get("detail") or "")
        return QuillRAGRetrieveResult(
            ok=False,
            error_code=f"http_{response.status_code}",
            error_message=message,
            status_code=response.status_code,
            attempts=attempts,
        )

    def _retrieve_success(
        self,
        response: httpx.Response,
        attempts: int,
    ) -> QuillRAGRetrieveResult:
        body = self._safe_json(response)
        data = body.get("data")
        if not isinstance(data, dict):
            data = body
        raw_results = data.get("results") or []
        results = [
            self._document_from_payload(item)
            for item in raw_results
            if isinstance(item, dict)
        ]
        return QuillRAGRetrieveResult(
            ok=True,
            results=results,
            actual_mode=self._string_or_none(data.get("actual_mode")),
            warning=self._string_or_none(body.get("warning") or data.get("warning")),
            status_code=response.status_code,
            attempts=attempts,
        )

    @staticmethod
    def _document_from_payload(payload: dict[str, Any]) -> QuillRAGDocument:
        metadata = payload.get("metadata")
        return QuillRAGDocument(
            content=str(payload.get("content") or ""),
            score=float(payload.get("score") or 0.0),
            doc_id=QuillRAGClient._string_or_none(payload.get("doc_id")),
            chunk_index=int(payload.get("chunk_index") or 0),
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)


__all__ = [
    "QuillRAGClient",
    "QuillRAGDocument",
    "QuillRAGHealthResult",
    "QuillRAGRetrieveResult",
]
