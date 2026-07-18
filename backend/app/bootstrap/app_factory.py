"""FastAPI 应用工厂。"""

from fastapi import FastAPI

from app.bootstrap.exceptions import register_exception_handlers
from app.bootstrap.lifespan import lifespan
from app.bootstrap.middleware import register_middlewares
from app.bootstrap.routes import register_routes
from app.shared.config import settings
from app.shared.logging import setup_logging
from app.infra.limiter import limiter


def create_app() -> FastAPI:
    """创建并装配 FastAPI app。"""
    setup_logging()
    app = FastAPI(title=settings.project_name, lifespan=lifespan)
    app.state.limiter = limiter
    register_exception_handlers(app)
    register_middlewares(app)
    register_routes(app)
    return app
