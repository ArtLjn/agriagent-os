"""应用异常处理注册。"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agent.runtime.support import AgentLoopMaxStepsExceeded
from app.shared.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, exc):
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

    @app.exception_handler(AgentLoopMaxStepsExceeded)
    async def agent_loop_max_steps_handler(request, exc):
        logger.warning("AgentLoopMaxStepsExceeded | path=%s", request.url.path)
        return JSONResponse(
            status_code=429,
            content={"detail": "Agent 处理步数超出限制，请简化问题后重试"},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.exception("未捕获异常 | path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "内部服务器错误"},
        )
