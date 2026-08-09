"""共享运行时依赖。

_pending_approvals 和 _active_turns 是模块级单例，
chat / approve / turns 路由通过 import 共享同一实例。
"""

from __future__ import annotations

import asyncio

# Pending HITL approvals keyed by turn_id.
pending_approvals: dict[str, asyncio.Future[tuple[bool, str]]] = {}

# Live turn snapshots for /turns/{turn_id} status polling.
active_turns: dict = {}


async def approval_waiter(turn_id: str) -> tuple[bool, str]:
    """Block until /approve resolves the future for this turn_id."""
    loop = asyncio.get_running_loop()
    if turn_id not in pending_approvals:
        pending_approvals[turn_id] = loop.create_future()
    return await pending_approvals[turn_id]
