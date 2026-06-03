"""应用启动入口测试。"""

import runpy
from unittest.mock import patch


def test_main_uses_project_logging_and_disables_reload_by_default():
    """本地启动默认关闭 reload，并保留项目日志配置。"""
    with patch("uvicorn.run") as run:
        runpy.run_module("app.main", run_name="__main__")

    kwargs = run.call_args.kwargs
    assert run.call_args.args[0] is not None
    assert run.call_args.args[0] != "app.main:app"
    assert kwargs["log_config"] is None
    assert kwargs["reload"] is False
    assert "reload_dirs" not in kwargs
    assert "reload_includes" not in kwargs
    assert "reload_excludes" not in kwargs


def test_main_can_enable_limited_reload_with_env(monkeypatch):
    """需要热重载时，可通过环境变量显式开启受限监听。"""
    monkeypatch.setenv("UVICORN_RELOAD", "1")

    with patch("uvicorn.run") as run:
        runpy.run_module("app.main", run_name="__main__")

    assert run.call_args.args[0] == "app.main:app"
    kwargs = run.call_args.kwargs
    assert kwargs["reload"] is True
    assert any(path.endswith("/backend/app") for path in kwargs["reload_dirs"])
    assert kwargs["reload_includes"] == ["app/**/*.py"]
    assert "tests/*" in kwargs["reload_excludes"]
    assert "logs/*" in kwargs["reload_excludes"]
    assert "__pycache__/*" in kwargs["reload_excludes"]
