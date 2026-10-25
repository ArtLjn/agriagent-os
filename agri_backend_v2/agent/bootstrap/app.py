"""FastAPI entry point — thin shell.

路由 → agent/api/*  (统一前缀 /api/v2)
鉴权 → agent/auth.py

Run: uv run --package farm-manager-agent python -m agent.bootstrap.app
"""

from __future__ import annotations

import importlib
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 直接执行 ``python agent/bootstrap/app.py`` 时，Python 只会把
# ``agent/bootstrap`` 放入 sys.path；包导入需要的是 ``agri_backend_v2``。
# shared 项目根必须排在仓库根之前，否则 ``agri_backend_v2/shared`` 会作为
# 命名空间包遮蔽真正的 ``shared/shared`` 包。
_PACKAGE_ROOT = str(Path(__file__).resolve().parents[2])
_SHARED_ROOT = str(Path(_PACKAGE_ROOT) / "shared")
for _path in (_PACKAGE_ROOT, _SHARED_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from shared.api_response import install_api_exception_handlers

from agent.api import (  # noqa: F401
    api_router,
    approve,
    chat,
    conversations,
    health,
    login,
    personalization,
    reset,
    traces,
    turns,
)  # register routes
from agent.application.sweeper import start as start_sweeper
from agent.application.sweeper import stop as stop_sweeper
from agent.application.worker import start as start_worker
from agent.application.worker import stop as stop_worker
from agent.config import settings
from agent.domains.harness.observability.trace import (
    start_trace_system,
    stop_trace_system,
)
from agent.domains.harness.tools import loader as skill_loader
from agent.platforms.logging import get_logger, setup_logging
from agent.platforms.persistence.mongo.chat_store import check_connection, close
from agent.platforms.persistence.redis.redis_store import (
    check_connection as check_redis_connection,
)
from agent.platforms.persistence.redis.redis_store import (
    close as close_redis,
)
from agent.prompts import render_system_prompt

# 导入模块以注册管理端 Skill 路由；其余 API 模块沿用下方的显式导入方式。
importlib.import_module("agent.api.admin_skills")
importlib.import_module("agent.api.admin_prompts")
importlib.import_module("agent.api.admin_tokens")

setup_logging(app_name="agent")
logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _validate_plugin_resources() -> None:
    """启动前加载技能与业务提示词，缺少插件资源时 fail fast。"""
    registry = skill_loader.load_registry()
    system_prompt = render_system_prompt()
    logger.info(
        "plugin loaded: %s (%d skills, %d system prompt chars)",
        settings.plugins.active or "<none>",
        len(registry.all()),
        len(system_prompt),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_plugin_resources()
    await check_connection()
    await check_redis_connection()
    await start_trace_system()
    await start_worker()
    from agent.domains.harness.memory import learning

    learning.start()
    await start_sweeper()
    yield
    await learning.stop()
    await stop_worker()
    await stop_sweeper()
    await stop_trace_system()
    await close_redis()
    await close()


app = FastAPI(title="farm-manager agent", version="2.0.0", lifespan=lifespan)
install_api_exception_handlers(app)
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

    server_url = f"http://{settings.server.host}:{settings.server.port}"
    logger.info("starting agent on %s", server_url)
    uvicorn.run(
        "agent.bootstrap.app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
