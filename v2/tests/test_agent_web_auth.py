"""Agent 公网登录代理和生产开发接口边界测试。"""

from __future__ import annotations

import asyncio
import importlib
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from agent.api.health import dev_users
from agent.config import settings

login_module = importlib.import_module("agent.api.login")


class _Response:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _Client:
    def __init__(self, response: _Response, **kwargs) -> None:
        self.response = response
        self.kwargs = kwargs
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, url: str, json: dict) -> _Response:
        self.request = (url, json)
        return self.response


class AgentWebAuthTests(unittest.TestCase):
    def test_login_proxy_returns_only_public_user_auth_fields(self) -> None:
        response = _Response(
            200,
            {
                "access_token": "user-token",
                "token_type": "Bearer",
                "user": {"id": "user-1", "nickname": "农友"},
                "farm_uid": "farm-1",
                "farm_id": 9,
                "password_hash": "must-not-leak",
            },
        )

        def client_factory(**kwargs):
            client = _Client(response, **kwargs)
            self.client = client
            return client

        with patch.object(login_module.httpx, "AsyncClient", client_factory):
            result = asyncio.run(
                login_module.login(
                    login_module.LoginRequest(phone="13800138000", password="secret123")
                )
            )

        self.assertEqual(result["access_token"], "user-token")
        self.assertNotIn("farm_id", result)
        self.assertNotIn("password_hash", result)
        self.assertEqual(self.client.request[1]["password"], "secret123")

    def test_dev_users_is_disabled_outside_development(self) -> None:
        previous = settings.environment
        settings.environment = "production"
        try:
            with self.assertRaises(HTTPException) as raised:
                dev_users()
            self.assertEqual(raised.exception.status_code, 404)
            self.assertEqual(raised.exception.detail["code"], "not_found")
        finally:
            settings.environment = previous


if __name__ == "__main__":
    unittest.main()
