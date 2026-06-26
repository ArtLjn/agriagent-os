"""应用 lifespan 测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bootstrap.lifespan import lifespan


@pytest.mark.asyncio
async def test_lifespan_reinitializes_logging_in_server_process():
    """reload 子进程进入 lifespan 时应重新安装项目日志 handler。"""
    with (
        patch("app.bootstrap.lifespan.setup_logging") as setup_logging,
        patch("app.bootstrap.lifespan._configure_langsmith"),
        patch("app.bootstrap.lifespan._run_migrations", new=AsyncMock()),
        patch("app.bootstrap.lifespan._seed_initial_data"),
        patch("app.bootstrap.lifespan._load_prompts"),
        patch("app.bootstrap.lifespan.start_trace_system", new=AsyncMock()),
        patch("app.bootstrap.lifespan.clean_expired_traces"),
        patch("app.bootstrap.lifespan.stop_trace_system", new=AsyncMock()),
    ):
        async with lifespan(MagicMock()):
            pass

    assert setup_logging.call_count == 2


@pytest.mark.asyncio
async def test_lifespan_initializes_and_closes_mongo_client_when_enabled():
    """启用 MongoDB 时，lifespan 应创建共享 client 并在关闭时释放。"""
    fake_settings = MagicMock()
    fake_settings.mongodb.enabled = True

    with (
        patch("app.bootstrap.lifespan.settings", fake_settings),
        patch("app.bootstrap.lifespan.setup_logging"),
        patch("app.bootstrap.lifespan._configure_langsmith"),
        patch("app.bootstrap.lifespan._run_migrations", new=AsyncMock()),
        patch("app.bootstrap.lifespan._seed_initial_data"),
        patch("app.bootstrap.lifespan._load_prompts"),
        patch("app.bootstrap.lifespan.start_trace_system", new=AsyncMock()),
        patch("app.bootstrap.lifespan.clean_expired_traces"),
        patch("app.bootstrap.lifespan.stop_trace_system", new=AsyncMock()),
        patch("app.bootstrap.lifespan.init_mongo_client") as init_mongo_client,
        patch(
            "app.bootstrap.lifespan.close_mongo_client",
            new=AsyncMock(),
        ) as close_mongo_client,
    ):
        async with lifespan(MagicMock()):
            init_mongo_client.assert_called_once_with(fake_settings.mongodb)

    close_mongo_client.assert_awaited_once()
