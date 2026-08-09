"""Business REST API 路由组装与统一错误响应。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from business.api import (
    auth,
    costs,
    crop_cycles,
    crop_templates,
    dashboard,
    debts,
    farm_logs,
    farms,
    health,
    locations,
    users,
    weather,
    work_orders,
    workers,
)

logger = logging.getLogger(__name__)
api_router = APIRouter(prefix="/api/v2")

for router in (
    health.router,
    auth.router,
    users.router,
    farms.router,
    dashboard.router,
    crop_templates.router,
    crop_cycles.router,
    farm_logs.router,
    workers.router,
    work_orders.router,
    work_orders.operations_router,
    costs.categories_router,
    costs.records_router,
    debts.router,
    weather.router,
    locations.router,
):
    api_router.include_router(router)


def _error_payload(code: str, message: str, request: Request, **meta) -> dict:
    context = {"path": request.url.path, **meta}
    return {"detail": {"code": code, "message": message, "meta": context}}


def install_exception_handlers(app: FastAPI) -> None:
    """安装统一错误格式，确保客户端始终获得 code 与请求上下文。"""

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code_by_status = {
            400: "validation_error",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "duplicate",
            503: "dependency_unavailable",
        }
        if isinstance(exc.detail, dict):
            code = str(
                exc.detail.get("code")
                or code_by_status.get(exc.status_code, "http_error")
            )
            message = str(
                exc.detail.get("message") or exc.detail.get("detail") or "请求失败"
            )
            meta = dict(exc.detail.get("meta") or {})
        else:
            code = code_by_status.get(exc.status_code, "http_error")
            message = str(exc.detail)
            meta = {}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(code, message, request, **meta),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "validation_error",
                "请求参数校验失败",
                request,
                errors=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("business API unexpected error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_error_payload("internal", "服务内部错误", request),
        )


__all__ = ["api_router", "install_exception_handlers"]
