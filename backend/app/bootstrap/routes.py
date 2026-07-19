"""应用路由注册。"""

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.domains.conversation import feedback_routes
from app.domains.conversation import routes as conversation_routes
from app.domains.finance import cost_category_routes
from app.domains.finance import cost_routes
from app.domains.finance import debt_routes
from app.domains.planting import crop_routes
from app.domains.planting import cycle_routes
from app.domains.planting import log_routes
from app.domains.planting import routes as planting_routes
from app.domains.planting import smart_fill_routes
from app.domains.users import admin_routes as admin_user_routes
from app.domains.users import settings_routes as user_settings_routes
from app.domains.weather import locations_routes
from app.domains.weather import routes as weather_routes
from app.infra.limiter import limiter
from app.infra.mongo import check_mongo_health
from app.domains.users.routes import router as auth_router
from app.platforms.admin import app_version_routes
from app.platforms.admin import config_routes as admin_config_routes
from app.platforms.admin import dashboard_routes as admin_dashboard_routes
from app.platforms.admin import routes as admin_routes
from app.platforms.admin import stats_routes as admin_stats_routes
from app.platforms.admin import trace_routes as admin_trace_routes
from app.platforms.data_flywheel.annotations_router import (
    router as data_flywheel_annotations_router,
)
from app.platforms.data_flywheel.repair_packs_router import (
    router as data_flywheel_repair_packs_router,
)
from app.platforms.data_flywheel.review_issue_chains_router import (
    router as data_flywheel_review_issue_chains_router,
)
from app.platforms.data_flywheel.router import router as data_flywheel_router
from app.platforms.simulation.routes import router as simulation_router


def register_routes(app: FastAPI) -> None:
    """注册所有 HTTP 路由。"""
    app.include_router(crop_routes.router)
    app.include_router(cycle_routes.router)
    app.include_router(log_routes.router)
    app.include_router(planting_routes.router)
    app.include_router(cost_routes.router)
    app.include_router(cost_category_routes.router)
    app.include_router(smart_fill_routes.router)
    app.include_router(conversation_routes.router)
    app.include_router(auth_router)
    app.include_router(weather_routes.router)
    app.include_router(locations_routes.router)
    app.include_router(admin_routes.router)
    app.include_router(data_flywheel_router)
    app.include_router(data_flywheel_annotations_router)
    app.include_router(data_flywheel_review_issue_chains_router)
    app.include_router(data_flywheel_repair_packs_router)
    app.include_router(admin_trace_routes.router)
    app.include_router(admin_stats_routes.router)
    app.include_router(admin_dashboard_routes.router)
    app.include_router(admin_config_routes.router)
    app.include_router(admin_user_routes.router)
    app.include_router(user_settings_routes.router)
    app.include_router(debt_routes.router)
    app.include_router(feedback_routes.router)
    app.include_router(app_version_routes.router)
    app.include_router(simulation_router)

    @app.get("/health")
    @limiter.limit("30/minute")
    async def health_check(request: Request, response: Response):
        mongo = await check_mongo_health()
        status = "degraded" if mongo["status"] == "error" else "ok"
        return {"status": status, "mongo": mongo}
