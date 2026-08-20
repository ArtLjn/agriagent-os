"""GET /api/agri_backend_v2/health + GET /api/agri_backend_v2/readiness。"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "farm-manager-business"}


@router.get("/readiness")
def readiness() -> dict:
    """就绪检查：确认 MySQL 连通。"""
    try:
        from business.db import check_connection as _check_db

        _check_db()
        return {"status": "ready", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "database_unavailable",
                    "message": "数据库连接不可用",
                    "meta": {"service": "farm-manager-business"},
                }
            },
        )
