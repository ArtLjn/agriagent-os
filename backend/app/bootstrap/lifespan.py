"""FastAPI lifespan 初始化。"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.prompt.registry import get_registry
from app.shared.config import settings
from app.shared.database import SessionLocal
from app.shared.logging import get_logger, setup_logging
from app.ops.bootstrap_seed import seed_admin_user, seed_default_farm
from app.infra.mongo import close_mongo_client, init_mongo_client
from app.infra.repository_runtime import set_main_event_loop
from app.infra.trace_cleaner import clean_expired_traces
from app.infra.trace_collector import start_trace_system, stop_trace_system

logger = get_logger(__name__)


async def _run_migrations() -> None:
    """运行 Alembic 数据库迁移。"""
    import sys

    _backend_dir = str(Path(__file__).resolve().parent.parent.parent)
    _saved_path = sys.path[:]
    if _backend_dir in sys.path:
        sys.path.remove(_backend_dir)
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
    finally:
        sys.path[:] = _saved_path

    from sqlalchemy import inspect

    alembic_cfg = AlembicConfig(
        str(Path(__file__).resolve().parent.parent.parent / "alembic.ini")
    )
    alembic_cfg.set_main_option(
        "sqlalchemy.url", settings.database_url.replace("%", "%%")
    )
    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        tables = set(inspector.get_table_names())
        if tables and "alembic_version" not in tables:
            await asyncio.to_thread(command.stamp, alembic_cfg, "head")
    finally:
        db.close()
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


def _configure_langsmith() -> None:
    """配置 LangSmith 环境变量。"""
    if not (settings.langsmith_config.enabled and settings.langsmith_config.api_key):
        return
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_config.api_key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_config.project_name
    logger.info("LangSmith 已启用 | project=%s", settings.langsmith_config.project_name)


def _seed_initial_data() -> None:
    """写入启动所需的默认数据。"""
    db = SessionLocal()
    try:
        seed_default_farm(db)
        seed_admin_user(db, settings.auth.admin_phone, settings.auth.admin_password)
    finally:
        db.close()


def _load_prompts() -> None:
    """加载 Prompt 模板并初始化 composer。"""
    registry = get_registry()
    registry.reload(settings.prompts_dir)
    logger.info("Prompt 模板已加载 | dir=%s", settings.prompts_dir)

    from app.prompt.composer import get_composer

    get_composer()
    logger.info("PromptComposer 初始化完成")


async def _daily_trace_cleanup() -> None:
    """每日清理过期 trace。"""
    while True:
        await asyncio.sleep(86400)
        await asyncio.to_thread(clean_expired_traces)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期。"""
    set_main_event_loop(asyncio.get_running_loop())
    setup_logging()
    _configure_langsmith()
    await _run_migrations()
    setup_logging()
    _seed_initial_data()
    _load_prompts()

    init_mongo_client(settings.mongodb)
    await start_trace_system()
    await asyncio.to_thread(clean_expired_traces)
    cleanup_task = asyncio.create_task(_daily_trace_cleanup())

    try:
        yield
    finally:
        set_main_event_loop(None)
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        await stop_trace_system()
        await close_mongo_client()
