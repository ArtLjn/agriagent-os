"""Skill 基类和 SkillResult 数据结构。

所有 skill 继承 Skill 基类，实现 execute() 方法。
统一接口让 react.py 不关心是 mcp 还是 local。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    """Skill 执行结果。"""

    data: Any = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Skill:
    """Skill 基类。子类必须实现 name/description/risk_level/parameters_schema/execute。

    kind 由子类决定：
      - kind="mcp"   → execute() 内部用 ctx.business_client.call_tool(...)
      - kind="local" → execute() 内部直接计算或调第三方
    """

    kind: str = "mcp"  # 默认 mcp，local skill 子类覆盖为 "local"
    mcp_tool: str = ""  # kind=mcp 时填写，对应 business MCP tool 名

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        raise NotImplementedError

    @property
    def risk_level(self) -> str:
        """read | write_confirm | write_high"""
        return "read"

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据实际参数返回风险等级。

        默认实现返回 risk_level 属性。子类可覆盖此方法实现"按 operation 动态风险"：
        例如 manage_farm_logs 的 query=create / delete 风险不同。
        react.py 在 HITL 检查前会优先调用此方法。
        """
        return self.risk_level

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, params: dict[str, Any], ctx: "SkillContext") -> SkillResult:
        """执行 skill。子类必须实现。

        ctx 提供：
          - ctx.business_client: BusinessClient 实例（已连接，async with 内）
          - ctx.turn: 当前 Turn 对象（可读取 conversation_id、memory 等）
        """
        raise NotImplementedError

    def to_openai_tool(self) -> dict:
        """转换为 OpenAI tools schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
