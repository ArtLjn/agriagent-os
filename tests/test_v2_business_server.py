"""Business MCP 启动兼容性回归。"""

from business import server


def test_business_server_uses_uvicorn_auto_websocket_backend(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(server, "setup_logging", lambda: None)
    monkeypatch.setattr(server, "check_connection", lambda: None)
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main()

    assert calls == [
        {
            "transport": "http",
            "host": "127.0.0.1",
            "port": 9876,
            "path": "/mcp",
            "uvicorn_config": {"ws": "auto"},
        }
    ]
