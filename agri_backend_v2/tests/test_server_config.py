"""Agent 与 Business HTTP 监听配置回归测试。"""

from __future__ import annotations

from pathlib import Path

import yaml
import uvicorn

from agent import config as agent_config
from agent.bootstrap import app as agent_server
from business import config as business_config
from business import server as business_server


def _write_config(tmp_path: Path, payload: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return config_file


def test_server_settings_read_yaml_and_environment_overrides(tmp_path, monkeypatch):
    agent_config_file = _write_config(
        tmp_path / "agent",
        {"server": {"host": "192.0.2.10", "port": 18000}},
    )
    business_config_file = _write_config(
        tmp_path / "business",
        {"server": {"host": "192.0.2.11", "port": 19876}},
    )
    monkeypatch.setattr(agent_config, "_CONFIG_FILE", agent_config_file)
    monkeypatch.setattr(business_config, "_CONFIG_FILE", business_config_file)

    agent_settings = agent_config._build_settings()
    business_settings = business_config._build_settings()

    assert (agent_settings.server.host, agent_settings.server.port) == (
        "192.0.2.10",
        18000,
    )
    assert (business_settings.server.host, business_settings.server.port) == (
        "192.0.2.11",
        19876,
    )

    monkeypatch.setenv("SERVER__HOST", "198.51.100.20")
    monkeypatch.setenv("SERVER__PORT", "28000")

    agent_settings = agent_config._build_settings()
    business_settings = business_config._build_settings()

    assert (agent_settings.server.host, agent_settings.server.port) == (
        "198.51.100.20",
        28000,
    )
    assert (business_settings.server.host, business_settings.server.port) == (
        "198.51.100.20",
        28000,
    )


def test_agent_main_uses_configured_server(monkeypatch):
    calls = {}
    monkeypatch.setattr(agent_server.settings.server, "host", "192.0.2.30")
    monkeypatch.setattr(agent_server.settings.server, "port", 38000)
    monkeypatch.setattr(
        uvicorn,
        "run",
        lambda *args, **kwargs: calls.update(kwargs),
    )

    agent_server.main()

    assert calls["host"] == "192.0.2.30"
    assert calls["port"] == 38000


def test_business_main_uses_configured_server(monkeypatch):
    calls = {}
    monkeypatch.setattr(business_server.settings.server, "host", "192.0.2.31")
    monkeypatch.setattr(business_server.settings.server, "port", 39876)
    monkeypatch.setattr(business_server, "setup_logging", lambda: None)
    monkeypatch.setattr(business_server, "check_connection", lambda: None)
    monkeypatch.setattr(business_server, "ensure_admin_user", lambda: None)
    monkeypatch.setattr(business_server, "create_app", lambda: object())
    monkeypatch.setattr(
        business_server.uvicorn,
        "run",
        lambda *args, **kwargs: calls.update(kwargs),
    )

    business_server.main()

    assert calls["host"] == "192.0.2.31"
    assert calls["port"] == 39876
