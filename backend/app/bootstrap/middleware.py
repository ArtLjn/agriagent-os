"""应用 middleware 注册。"""

from datetime import date

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.core.date_context import set_request_date
from app.core.logger import get_logger

logger = get_logger(__name__)


def register_middlewares(app: FastAPI) -> None:
    """注册全局 middleware。"""
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
        return await call_next(request)
