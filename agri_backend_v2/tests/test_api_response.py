"""REST 状态码和错误 envelope 的共享契约测试。"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.api_response import (
    ApiStatusCode,
    api_http_exception,
    install_api_exception_handlers,
    status_for_error,
)


class _CreateRequest(BaseModel):
    name: str


def _build_app() -> FastAPI:
    app = FastAPI()
    install_api_exception_handlers(app)

    @app.get("/legacy-error")
    async def legacy_error() -> None:
        raise HTTPException(403, {"code": "permission_denied", "message": "无权访问"})

    @app.get("/new-error")
    async def new_error() -> None:
        raise api_http_exception(
            "permission_denied",
            "无权写入",
            meta={"permission": "farm:write"},
        )

    @app.post("/validation")
    async def validation(request: _CreateRequest) -> dict:
        return request.model_dump()

    @app.get("/internal")
    async def internal() -> None:
        raise RuntimeError("secret backend detail")

    return app


@pytest.mark.asyncio
async def test_legacy_and_new_http_errors_share_detail_contract() -> None:
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        legacy = await client.get("/legacy-error", headers={"X-Request-ID": "req-1"})
        new = await client.get("/new-error")

    assert legacy.status_code == ApiStatusCode.FORBIDDEN
    assert legacy.json() == {
        "detail": {
            "code": "permission_denied",
            "message": "无权访问",
            "meta": {"path": "/legacy-error", "request_id": "req-1"},
        }
    }
    assert new.status_code == ApiStatusCode.FORBIDDEN
    assert new.json()["detail"] == {
        "code": "permission_denied",
        "message": "无权写入",
        "meta": {"path": "/new-error", "permission": "farm:write"},
    }


@pytest.mark.asyncio
async def test_validation_and_internal_errors_are_structured() -> None:
    transport = httpx.ASGITransport(app=_build_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        validation = await client.post("/validation", json={})
        internal = await client.get("/internal")

    assert validation.status_code == ApiStatusCode.UNPROCESSABLE_ENTITY
    assert validation.json()["detail"]["code"] == "validation_error"
    assert validation.json()["detail"]["meta"]["path"] == "/validation"
    assert internal.status_code == ApiStatusCode.INTERNAL_SERVER_ERROR
    assert internal.json() == {
        "detail": {
            "code": "internal",
            "message": "服务内部错误",
            "meta": {"path": "/internal"},
        }
    }


def test_new_error_codes_use_central_status_mapping() -> None:
    assert status_for_error("permission_denied") == ApiStatusCode.FORBIDDEN
    assert status_for_error("cursor_conflict") == ApiStatusCode.CONFLICT
    assert (
        status_for_error("dependency_unavailable") == ApiStatusCode.SERVICE_UNAVAILABLE
    )
