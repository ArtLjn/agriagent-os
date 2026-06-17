"""应用路由注册。"""

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.api import (
    admin,
    admin_config,
    admin_data_flywheel,
    admin_data_flywheel_repair_packs,
    admin_stats,
    admin_trace,
    admin_users,
    agent,
    app_version,
    auth,
    cost,
    cost_categories,
    crop,
    cycle,
    debt,
    feedback,
    log,
    planting,
    smart_fill,
    user_settings,
    weather,
)
from app.infra.limiter import limiter
from app.simulation.routes import router as simulation_router


def register_routes(app: FastAPI) -> None:
    """注册所有 HTTP 路由。"""
    app.include_router(crop.router)
    app.include_router(cycle.router)
    app.include_router(log.router)
    app.include_router(planting.router)
    app.include_router(cost.router)
    app.include_router(cost_categories.router)
    app.include_router(smart_fill.router)
    app.include_router(agent.router)
    app.include_router(auth.router)
    app.include_router(weather.router)
    app.include_router(admin.router)
    app.include_router(admin_data_flywheel.router)
    app.include_router(admin_data_flywheel_repair_packs.router)
    app.include_router(admin_trace.router)
    app.include_router(admin_stats.router)
    app.include_router(admin_config.router)
    app.include_router(admin_users.router)
    app.include_router(user_settings.router)
    app.include_router(debt.router)
    app.include_router(feedback.router)
    app.include_router(app_version.router)
    app.include_router(simulation_router)

    @app.get("/health")
    @limiter.limit("30/minute")
    def health_check(request: Request, response: Response):
        return {"status": "ok"}
