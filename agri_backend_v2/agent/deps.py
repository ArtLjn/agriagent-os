"""共享运行时依赖。

_pending_approvals 和 _active_turns 是模块级单例，
chat / approve / turns 路由通过 import 共享同一实例。
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from agent.auth import parse_identity
from shared.roles import Permission, has_permission

# Pending HITL approvals keyed by turn_id.
pending_approvals: dict[str, asyncio.Future[tuple[bool, str]]] = {}

# Live turn snapshots for /turns/{turn_id} status polling.
active_turns: dict = {}


def get_current_principal(
    authorization: str | None = Header(default=None),
) -> dict:
    """将 Agent User JWT 转换为受保护路由使用的 Principal。"""
    return parse_identity(authorization)


CurrentPrincipal = Annotated[dict, Depends(get_current_principal)]


def require_permission(permission: Permission):
    """创建 Agent 路由权限依赖，保持认证和资源归属分层。"""

    def check(principal: CurrentPrincipal) -> dict:
        if not has_permission(
            principal.get("role"), principal.get("scope"), permission
        ):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "permission_denied",
                    "message": "当前身份没有所需权限",
                    "meta": {"permission": permission.value},
                },
            )
        return principal

    return check


async def approval_waiter(turn_id: str) -> tuple[bool, str]:
    """Block until /approve resolves the future for this turn_id.

    同一个 turn 可能有多步 write_confirm（如 plan 多步执行），每步都需要
    独立审批。消费完 future 后立即清理，让下一次审批创建新 future，
    避免第二步 await 到已 resolved 的旧 future 被自动确认。
    """
    loop = asyncio.get_running_loop()
    if turn_id not in pending_approvals or pending_approvals[turn_id].done():
        pending_approvals[turn_id] = loop.create_future()
    try:
        return await pending_approvals[turn_id]
    finally:
        # 清理已消费的 future，同 turn 下一次 write_confirm 能创建新 future
        pending_approvals.pop(turn_id, None)
