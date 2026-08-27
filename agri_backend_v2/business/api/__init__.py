"""Business REST API 路由组装与统一错误响应。"""

from __future__ import annotations

from fastapi import APIRouter

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
from shared.api_response import (
    install_api_exception_handlers as install_exception_handlers,
)

api_router = APIRouter(prefix="/api/v2")

for router in (
    health.router,
    auth.router,
    users.router,
    users.admin_router,
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


__all__ = ["api_router", "install_exception_handlers"]
