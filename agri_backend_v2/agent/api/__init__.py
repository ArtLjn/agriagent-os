"""Agent REST API router — 所有业务端点统一挂载到 /api/v2 前缀下。"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v2")
