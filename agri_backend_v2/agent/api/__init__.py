"""Agent REST API router — 所有业务端点统一挂载到 /api/agri_backend_v2 前缀下。"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/agri_backend_v2")
