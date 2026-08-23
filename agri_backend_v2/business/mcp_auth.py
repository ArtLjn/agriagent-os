"""Business MCP 服务身份和用户委托鉴权。"""

from __future__ import annotations

import json
import hmac
from typing import Any

import jwt
from sqlalchemy import select

from business.config import settings
from business.db import SessionLocal
from business.models import Farm, User
from shared.roles import normalize_user_role


class McpAuthFailure(Exception):
    """MCP 认证或授权失败，并携带 HTTP 状态码。"""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


def _error_body(code: str, message: str) -> bytes:
    return json.dumps({"error": code, "message": message}).encode("utf-8")


def _reject(send, status: int, code: str, message: str):
    async def _send():
        body = _error_body(code, message)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    return _send()


def _verify_service_token(headers: dict[str, str]) -> None:
    expected = settings.auth.agent_service_token
    authorization = headers.get("authorization", "")
    if not expected:
        raise RuntimeError("AGENT_SERVICE_TOKEN 未配置")
    if not authorization.lower().startswith("bearer "):
        raise McpAuthFailure(401, "缺少 Agent 服务凭证")
    if not hmac.compare_digest(authorization[7:].strip(), expected):
        raise McpAuthFailure(401, "Agent 服务凭证无效")


def _verify_delegation(headers: dict[str, str]) -> dict[str, Any]:
    secret = settings.auth.delegation_secret
    raw = headers.get("x-delegation-token", "")
    if not secret or not raw:
        raise McpAuthFailure(401, "缺少用户委托凭证")
    try:
        payload = jwt.decode(
            raw,
            secret,
            algorithms=[settings.auth.jwt_algorithm],
            issuer=settings.auth.delegation_issuer,
            audience=settings.auth.delegation_audience,
        )
    except jwt.ExpiredSignatureError as exc:
        raise McpAuthFailure(401, "用户委托凭证已过期") from exc
    except jwt.InvalidTokenError as exc:
        raise McpAuthFailure(401, "用户委托凭证无效") from exc
    if payload.get("type") != "delegation":
        raise McpAuthFailure(401, "委托凭证类型无效")
    actor = payload.get("act") or {}
    if actor.get("sub") != "agent" or actor.get("type") != "service":
        raise McpAuthFailure(403, "委托凭证调用主体无效")
    return payload


def _resolve_principal(
    payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    user_id = str(payload.get("sub") or "")
    farm_uid = str(payload.get("farm_uid") or "")
    if not user_id or not farm_uid:
        raise McpAuthFailure(401, "委托凭证缺少用户或农场身份")
    if headers.get("x-user-id") and headers["x-user-id"] != user_id:
        raise McpAuthFailure(403, "用户身份不一致")
    if headers.get("x-farm-uid") and headers["x-farm-uid"] != farm_uid:
        raise McpAuthFailure(403, "农场身份不一致")

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        farm = db.execute(select(Farm).where(Farm.uid == farm_uid)).scalar_one_or_none()
        if user is None or user.status != "active":
            raise McpAuthFailure(403, "用户无效")
        if farm is None or farm.user_id != user_id:
            raise McpAuthFailure(403, "用户无权访问该农场")
        return {
            "user_id": user_id,
            "farm_uid": farm_uid,
            "farm_id": farm.id,
            # 委托 Token 的角色只作传输信息，最终权限以数据库当前角色为准。
            "role": normalize_user_role(user.role).value,
            "scope": payload.get("scope", ""),
            "actor_service": "agent",
        }
    finally:
        db.close()


class McpAuthMiddleware:
    """在 FastMCP ASGI 应用前验证服务身份和用户委托。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = _headers(scope)
        try:
            _verify_service_token(headers)
            payload = _verify_delegation(headers)
            scope.setdefault("state", {})["principal"] = _resolve_principal(
                payload, headers
            )
        except RuntimeError as exc:
            await _reject(send, 503, "service_auth_unavailable", str(exc))
            return
        except McpAuthFailure as exc:
            await _reject(send, exc.status_code, "mcp_auth_failed", str(exc))
            return
        await self.app(scope, receive, send)
