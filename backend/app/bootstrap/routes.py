"""应用路由注册。"""

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.api import (
    admin,
    admin_config,
    admin_stats,
    admin_trace,
    admin_users,
    agent,
    app_version,
    cost,
    cost_categories,
    crop,
    cycle,
    debt,
    feedback,
    locations,
    log,
    planting,
    smart_fill,
    user_settings,
    weather,
)
from app.infra.limiter import limiter
from app.infra.mongo import check_mongo_health
from app.modules.auth.router import router as auth_router
from app.modules.data_flywheel.annotations_router import (
    router as data_flywheel_annotations_router,
)
from app.modules.data_flywheel.repair_packs_router import (
    router as data_flywheel_repair_packs_router,
)
from app.modules.data_flywheel.review_issue_chains_router import (
    router as data_flywheel_review_issue_chains_router,
)
from app.modules.data_flywheel.router import router as data_flywheel_router
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
    app.include_router(auth_router)
    app.include_router(weather.router)
    app.include_router(locations.router)
    app.include_router(admin.router)
    app.include_router(data_flywheel_router)
    app.include_router(data_flywheel_annotations_router)
    app.include_router(data_flywheel_review_issue_chains_router)
    app.include_router(data_flywheel_repair_packs_router)
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
    async def health_check(request: Request, response: Response):
        mongo = await check_mongo_health()
        status = "degraded" if mongo["status"] == "error" else "ok"
        return {"status": status, "mongo": mongo}
