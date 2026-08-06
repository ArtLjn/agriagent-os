"""SkillContext — 传递给 skill.execute() 的运行时上下文。

包含：
  - business_client: 已连接的 BusinessClient（async with 内）
  - turn: 当前 Turn 对象
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core.turn import Turn
    from agent.infra.mcp_client import BusinessClient


@dataclass
class SkillContext:
    """Skill 执行时的运行时上下文。"""

    business_client: "BusinessClient"
    turn: "Turn"
