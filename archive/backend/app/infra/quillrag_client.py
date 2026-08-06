"""QuillRAG 公共 HTTP client。"""

from __future__ import annotations

import json
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


@dataclass(frozen=True, slots=True)
class QuillRAGListedDocument:
    """标准化后的文档列表记录。"""

    doc_id: str
    collection: str = ""
    source: str | None = None
    category: str | None = None
    chunk_count: int = 0
    content_hash: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QuillRAGListDocumentsResult:
    """标准化后的 collection 文档列表返回。"""

    ok: bool
    total: int = 0
    page: int = 1
    page_size: int = 100
    documents: list[QuillRAGListedDocument] = field(default_factory=list)
    error_code: str | None = None
    error_message: str = ""
    status_code: int | None = None
    attempts: int = 1


@dataclass(frozen=True, slots=True)
class QuillRAGWriteResult:
    """标准化后的 QuillRAG 写操作返回。"""

    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    warning: str | None = None
    error_code: str | None = None
    error_message: str = ""
    status_code: int | None = None
    attempts: int = 1


class QuillRAGClient:
    """QuillRAG HTTP client，封装健康检查、检索和受控入库。"""

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

    def ensure_collection(self, *, collection: str) -> QuillRAGWriteResult:
        """调用 POST /collections，QuillRAG 端负责幂等创建。"""
        return self._write_json(
            path="/collections",
            payload={"name": collection},
        )

    def list_documents(
        self,
        *,
        collection: str,
        page: int = 1,
        page_size: int = 100,
    ) -> QuillRAGListDocumentsResult:
        """调用 GET /collections/{name}/documents。"""
        attempts = 0
        for attempt in range(self.retry + 1):
            attempts = attempt + 1
            try:
                response = self._request(
                    "GET",
                    f"/collections/{collection}/documents",
                    params={"page": page, "page_size": page_size},
                )
            except httpx.TimeoutException as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGListDocumentsResult(
                    ok=False,
                    error_code="timeout",
                    error_message=str(exc),
                    attempts=attempts,
                )
            except httpx.HTTPError as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGListDocumentsResult(
                    ok=False,
                    error_code="network_error",
                    error_message=str(exc),
                    attempts=attempts,
                )
            if response.status_code >= 400:
                body = self._safe_json(response)
                return QuillRAGListDocumentsResult(
                    ok=False,
                    error_code=f"http_{response.status_code}",
                    error_message=str(body.get("message") or body.get("detail") or ""),
                    status_code=response.status_code,
                    attempts=attempts,
                )
            return self._list_documents_success(response, attempts)
        return QuillRAGListDocumentsResult(
            ok=False,
            error_code="unknown",
            attempts=attempts,
        )

    def ingest_text(
        self,
        *,
        collection: str,
        text: str,
        file_type: str = "txt",
        strategy: str = "fixed",
        chunk_size: int = 1200,
        chunk_overlap: int = 0,
        source: str,
        category: str,
        doc_id: str,
        metadata: dict[str, Any],
    ) -> QuillRAGWriteResult:
        """调用 POST /ingest，把结构化文本交给 QuillRAG 入库。"""
        return self._write_form(
            path="/ingest",
            data={
                "collection": collection,
                "text": text,
                "file_type": file_type,
                "strategy": strategy,
                "chunk_size": str(chunk_size),
                "chunk_overlap": str(chunk_overlap),
                "source": source,
                "category": category,
                "doc_id": doc_id,
                "metadata_json": self._json_dumps(metadata),
            },
        )

    def _write_json(
        self,
        *,
        path: str,
        payload: dict[str, Any],
    ) -> QuillRAGWriteResult:
        return self._write_request("POST", path, json=payload)

    def _write_form(
        self,
        *,
        path: str,
        data: dict[str, Any],
    ) -> QuillRAGWriteResult:
        return self._write_request("POST", path, data=data)

    def _write_request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> QuillRAGWriteResult:
        attempts = 0
        for attempt in range(self.retry + 1):
            attempts = attempt + 1
            try:
                response = self._request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGWriteResult(
                    ok=False,
                    error_code="timeout",
                    error_message=str(exc),
                    attempts=attempts,
                )
            except httpx.HTTPError as exc:
                if attempt < self.retry:
                    continue
                return QuillRAGWriteResult(
                    ok=False,
                    error_code="network_error",
                    error_message=str(exc),
                    attempts=attempts,
                )
            body = self._safe_json(response)
            if response.status_code >= 400:
                return QuillRAGWriteResult(
                    ok=False,
                    data=body,
                    error_code=f"http_{response.status_code}",
                    error_message=str(body.get("message") or body.get("detail") or ""),
                    status_code=response.status_code,
                    attempts=attempts,
                )
            data = body.get("data")
            return QuillRAGWriteResult(
                ok=True,
                data=data if isinstance(data, dict) else body,
                warning=self._string_or_none(body.get("warning")),
                status_code=response.status_code,
                attempts=attempts,
            )
        return QuillRAGWriteResult(ok=False, error_code="unknown", attempts=attempts)

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
    def _json_dumps(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

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

    def _list_documents_success(
        self,
        response: httpx.Response,
        attempts: int,
    ) -> QuillRAGListDocumentsResult:
        body = self._safe_json(response)
        data = body.get("data")
        if not isinstance(data, dict):
            data = body
        raw_documents = data.get("documents") or []
        documents = [
            self._listed_document_from_payload(item)
            for item in raw_documents
            if isinstance(item, dict) and item.get("doc_id")
        ]
        return QuillRAGListDocumentsResult(
            ok=True,
            total=int(data.get("total") or len(documents)),
            page=int(data.get("page") or 1),
            page_size=int(data.get("page_size") or len(documents) or 100),
            documents=documents,
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
    def _listed_document_from_payload(payload: dict[str, Any]) -> QuillRAGListedDocument:
        extra = payload.get("extra")
        return QuillRAGListedDocument(
            doc_id=str(payload["doc_id"]),
            collection=str(payload.get("collection") or ""),
            source=QuillRAGClient._string_or_none(payload.get("source")),
            category=QuillRAGClient._string_or_none(payload.get("category")),
            chunk_count=int(payload.get("chunk_count") or 0),
            content_hash=str(payload.get("content_hash") or ""),
            extra=extra if isinstance(extra, dict) else {},
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
    "QuillRAGListedDocument",
    "QuillRAGListDocumentsResult",
    "QuillRAGRetrieveResult",
    "QuillRAGWriteResult",
]
