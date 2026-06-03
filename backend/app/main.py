import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.errors import GraphRecursionError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api import (  # noqa: E402
    admin,
    admin_config,
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
    user_settings,
    weather,
)
from app.simulation.routes import router as simulation_router  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.date_context import set_request_date  # noqa: E402
from app.infra.limiter import limiter  # noqa: E402
from app.core.logger import get_logger, setup_logging  # noqa: E402
from app.agent.prompt_registry import get_registry  # noqa: E402
from app.core.seed import seed_admin_user, seed_default_farm  # noqa: E402
from app.infra.trace_cleaner import clean_expired_traces  # noqa: E402
from app.infra.trace_collector import start_trace_system, stop_trace_system  # noqa: E402

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # LangSmith 环境变量配置
    if settings.langsmith_config.enabled and settings.langsmith_config.api_key:
        import os

        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_config.api_key
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_config.project_name
        logger.info(
            "LangSmith 已启用 | project=%s", settings.langsmith_config.project_name
        )

    from alembic import command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy import inspect

    alembic_cfg = AlembicConfig(
        str(Path(__file__).resolve().parent.parent / "alembic.ini")
    )
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        tables = set(inspector.get_table_names())
        if tables and "alembic_version" not in tables:
            await asyncio.to_thread(command.stamp, alembic_cfg, "head")
    finally:
        db.close()
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    db = SessionLocal()
    try:
        seed_default_farm(db)
        seed_admin_user(db, settings.auth.admin_phone, settings.auth.admin_password)
    finally:
        db.close()

    # 加载 Prompt 模板
    registry = get_registry()
    registry.reload(settings.prompts_dir)
    logger.info("Prompt 模板已加载 | dir=%s", settings.prompts_dir)

    # 初始化 PromptComposer 全局单例
    from app.agent.prompt_composer import get_composer

    get_composer()
    logger.info("PromptComposer 初始化完成")

    # 启动 Trace 后台 worker
    await start_trace_system()

    # 启动时立即清理过期数据
    await asyncio.to_thread(clean_expired_traces)

    # 注册定时清理任务
    async def _daily_cleanup() -> None:
        while True:
            await asyncio.sleep(86400)  # 24 小时
            await asyncio.to_thread(clean_expired_traces)

    cleanup_task = asyncio.create_task(_daily_cleanup())

    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        await stop_trace_system()


app = FastAPI(title=settings.project_name, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def date_injection_middleware(request: Request, call_next):
    """读取 X-Current-Date 请求头并注入上下文。"""
    header_date = request.headers.get("X-Current-Date")
    server_date = date.today()
    effective_date = server_date

    if header_date:
        try:
            client_date = date.fromisoformat(header_date)
            delta = abs((client_date - server_date).days)
            if delta <= 7:
                effective_date = client_date
            else:
                logger.warning(
                    "客户端日期偏差过大 | client=%s server=%s delta=%dd",
                    header_date,
                    server_date,
                    delta,
                )
        except ValueError:
            logger.warning("X-Current-Date 格式无效: %s", header_date)

    set_request_date(effective_date.isoformat())
    response = await call_next(request)
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request, exc):
    """HTTP 异常原样返回，保留 status code 和 detail。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc):
    """请求参数校验失败，返回 422 和结构化字段错误。"""
    errors = []
    for err in exc.errors():
        errors.append(
            {
                "field": ".".join(str(x) for x in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={"detail": "请求参数校验失败", "errors": errors},
    )


@app.exception_handler(GraphRecursionError)
async def graph_recursion_handler(request, exc):
    """Agent 步数超限，返回 429。"""
    logger.warning("GraphRecursionError | path=%s", request.url.path)
    return JSONResponse(
        status_code=429,
        content={"detail": "Agent 处理步数超出限制，请简化问题后重试"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """未捕获异常，返回 500，记录完整堆栈，不泄漏给客户端。"""
    logger.exception("未捕获异常 | path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务器错误"},
    )


app.include_router(crop.router)
app.include_router(cycle.router)
app.include_router(log.router)
app.include_router(cost.router)
app.include_router(cost_categories.router)
app.include_router(agent.router)
app.include_router(auth.router)
app.include_router(weather.router)
app.include_router(admin.router)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
    )
