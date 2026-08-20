"""SkillContext — 传递给 skill.execute() 的运行时上下文。

包含：
  - business_client: 已连接的 BusinessClient（async with 内，已注入身份 headers）
  - turn: 当前 Turn 对象
  - user_id / farm_uid / farm_id / agent_token: 从 JWT 解析的身份信息，skill 可直接读取
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agent.platforms.mcp.client import call_mcp_with_retry

if TYPE_CHECKING:
    from agent.domains.harness.runtime.turn import Turn
    from agent.platforms.mcp.client import BusinessClient


@dataclass
class SkillContext:
    """Skill 执行时的运行时上下文。"""

    business_client: BusinessClient
    turn: Turn
    user_id: str = ""
    farm_uid: str = ""
    farm_id: int = 1
    agent_token: str = ""

    async def call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        risk_level: str = "read",
        idempotency_key: str | None = None,
        allow_idempotent_write_retry: bool = False,
    ) -> dict[str, Any]:
        """通过统一策略调用 Business MCP。"""
        return await call_mcp_with_retry(
            self.business_client,
            tool_name,
            arguments,
            risk_level=risk_level,
            idempotency_key=idempotency_key,
            allow_idempotent_write_retry=allow_idempotent_write_retry,
        )
