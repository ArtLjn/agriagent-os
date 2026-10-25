"""Agent 与 Business REST 共用的 HTTP 状态码和错误响应契约。"""

from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiStatusCode(IntEnum):
    """REST API 对外使用的稳定 HTTP 状态码集合。"""

    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    INTERNAL_SERVER_ERROR = 500


DEFAULT_ERROR_CODE_BY_STATUS: dict[int, str] = {
    ApiStatusCode.BAD_REQUEST: "invalid_request",
    ApiStatusCode.UNAUTHORIZED: "unauthorized",
    ApiStatusCode.FORBIDDEN: "forbidden",
    ApiStatusCode.NOT_FOUND: "not_found",
    ApiStatusCode.CONFLICT: "conflict",
    ApiStatusCode.UNPROCESSABLE_ENTITY: "validation_error",
    ApiStatusCode.TOO_MANY_REQUESTS: "rate_limited",
    ApiStatusCode.BAD_GATEWAY: "upstream_error",
    ApiStatusCode.SERVICE_UNAVAILABLE: "dependency_unavailable",
    ApiStatusCode.INTERNAL_SERVER_ERROR: "internal",
}

ERROR_STATUS_BY_CODE: dict[str, int] = {
    "missing_authorization": ApiStatusCode.UNAUTHORIZED,
    "invalid_authorization": ApiStatusCode.UNAUTHORIZED,
    "token_expired": ApiStatusCode.UNAUTHORIZED,
    "invalid_token": ApiStatusCode.UNAUTHORIZED,
    "invalid_credentials": ApiStatusCode.UNAUTHORIZED,
    "mcp_auth_failed": ApiStatusCode.UNAUTHORIZED,
    "user_inactive": ApiStatusCode.FORBIDDEN,
    "farm_forbidden": ApiStatusCode.FORBIDDEN,
    "permission_denied": ApiStatusCode.FORBIDDEN,
    "admin_required": ApiStatusCode.FORBIDDEN,
    "resource_forbidden": ApiStatusCode.FORBIDDEN,
    "turn_forbidden": ApiStatusCode.FORBIDDEN,
    "duplicate": ApiStatusCode.CONFLICT,
    "idempotency_conflict": ApiStatusCode.CONFLICT,
    "cursor_conflict": ApiStatusCode.CONFLICT,
    "validation_error": ApiStatusCode.UNPROCESSABLE_ENTITY,
    "rate_limited": ApiStatusCode.TOO_MANY_REQUESTS,
    "capacity_exceeded": ApiStatusCode.TOO_MANY_REQUESTS,
    "upstream_error": ApiStatusCode.BAD_GATEWAY,
    "auth_unavailable": ApiStatusCode.SERVICE_UNAVAILABLE,
    "dependency_unavailable": ApiStatusCode.SERVICE_UNAVAILABLE,
    "internal": ApiStatusCode.INTERNAL_SERVER_ERROR,
}


def status_for_error(
    code: str, default: int = ApiStatusCode.INTERNAL_SERVER_ERROR
) -> int:
    """返回新接口构造错误时应使用的 HTTP 状态码。"""
    return int(ERROR_STATUS_BY_CODE.get(code, default))


def api_error_detail(
    code: str,
    message: str,
    *,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """构造兼容现有 admin-web 的 ``detail`` 错误结构。"""
    return {
        "code": code,
        "message": message,
        "meta": dict(meta or {}),
    }


def api_http_exception(
    code: str,
    message: str,
    *,
    status_code: int | None = None,
    meta: Mapping[str, Any] | None = None,
) -> HTTPException:
    """构造带稳定状态码和错误码的 HTTP 异常，供新接口直接使用。"""
    return HTTPException(
        status_code=status_code or status_for_error(code),
        detail=api_error_detail(code, message, meta=meta),
    )


def _request_meta(request: Request) -> dict[str, Any]:
    """生成客户端可定位请求的安全上下文，不复制认证 Header。"""
    meta: dict[str, Any] = {"path": request.url.path}
    request_id = request.headers.get("x-request-id")
    if request_id:
        meta["request_id"] = request_id[:128]
    return meta


def _split_detail(status_code: int, detail: Any) -> tuple[str, str, dict[str, Any]]:
    """兼容历史字符串/字典 detail，并收敛为 code、message、meta。"""
    fallback_code = DEFAULT_ERROR_CODE_BY_STATUS.get(status_code, "http_error")
    if not isinstance(detail, Mapping):
        return fallback_code, str(detail or "请求失败"), {}

    code = str(detail.get("code") or fallback_code)
    message = detail.get("message") or detail.get("detail") or "请求失败"
    raw_meta = detail.get("meta")
    meta = dict(raw_meta) if isinstance(raw_meta, Mapping) else {}
    for key, value in detail.items():
        if key not in {"code", "message", "detail", "meta"}:
            meta.setdefault(key, value)
    return code, str(message), meta


def error_payload(
    status_code: int,
    detail: Any,
    request: Request,
    *,
    extra_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """将任意 HTTP 异常转换为现有 REST 错误 envelope。"""
    code, message, meta = _split_detail(status_code, detail)
    context = _request_meta(request)
    context.update(meta)
    context.update(dict(extra_meta or {}))
    return {"detail": api_error_detail(code, message, meta=context)}


def install_api_exception_handlers(
    app: FastAPI,
    *,
    logger: logging.Logger | None = None,
) -> None:
    """安装 Agent/Business 共用的 REST 异常处理器。"""
    error_logger = logger or logging.getLogger(__name__)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.status_code, exc.detail, request),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=ApiStatusCode.UNPROCESSABLE_ENTITY,
            content=error_payload(
                ApiStatusCode.UNPROCESSABLE_ENTITY,
                api_error_detail(
                    "validation_error",
                    "请求参数校验失败",
                    meta={"errors": exc.errors()},
                ),
                request,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        error_logger.exception("API internal error", exc_info=exc)
        return JSONResponse(
            status_code=ApiStatusCode.INTERNAL_SERVER_ERROR,
            content=error_payload(
                ApiStatusCode.INTERNAL_SERVER_ERROR,
                api_error_detail("internal", "服务内部错误"),
                request,
            ),
        )


__all__ = [
    "ApiStatusCode",
    "DEFAULT_ERROR_CODE_BY_STATUS",
    "ERROR_STATUS_BY_CODE",
    "api_error_detail",
    "api_http_exception",
    "error_payload",
    "install_api_exception_handlers",
    "status_for_error",
]
