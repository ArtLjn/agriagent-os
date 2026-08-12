"""FastAPI entry point — thin shell.

路由 → agent/api/*  (统一前缀 /api/v2)
鉴权 → agent/auth.py

Run: cd v2/agent && python main.py
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from agent.api import api_router  # noqa: E402
from agent.api import (  # noqa: E402, F401
    approve,
    chat,
    conversations,
    health,
    reset,
    traces,
    turns,
)  # register routes
from agent.infra.chat_store import check_connection, close  # noqa: E402
from agent.infra.redis_store import (  # noqa: E402
    check_connection as check_redis_connection,
    close as close_redis,
)
from agent.infra.worker import start as start_worker, stop as stop_worker  # noqa: E402
from agent.infra.sweeper import start as start_sweeper, stop as stop_sweeper  # noqa: E402
from agent.infra.logging import get_logger, setup_logging  # noqa: E402
from agent.infra.trace import start_trace_system, stop_trace_system  # noqa: E402

setup_logging(app_name="agent")
logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_connection()
    await check_redis_connection()
    await start_trace_system()
    await start_worker()
    await start_sweeper()
    yield
    await stop_worker()
    await stop_sweeper()
    await stop_trace_system()
    await close_redis()
    await close()


app = FastAPI(title="farm-manager agent", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(api_router)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def main() -> None:
    import uvicorn

    logger.info("starting agent on http://127.0.0.1:8000")
    uvicorn.run(
        "agent.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
