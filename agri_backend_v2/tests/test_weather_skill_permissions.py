"""天气 Skill 在可选用户设置权限不足时的降级测试。"""

from __future__ import annotations

import pytest

from agent.domains.harness.runtime.error_policy import (
    ClassifiedError,
    ErrorCategory,
)
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.mcp.client import McpCallError
from agent.tools.weather.scripts.main import WeatherSkill


class _WeatherContext:
    def __init__(self) -> None:
        self.turn = Turn(user_input="农场这边天气怎么样")
        self.calls: list[tuple[str, dict]] = []

    async def call_mcp_tool(self, name: str, arguments: dict, **_kwargs):
        self.calls.append((name, arguments))
        if name == "manage_user_settings":
            classified = ClassifiedError(
                category=ErrorCategory.PERMANENT,
                retryable=False,
                code="permission_denied",
                message="MCP 工具需要权限: profile:read",
            )
            raise McpCallError(name, classified, 0)
        return {"location": "苏州", "days": arguments.get("days", 3)}


@pytest.mark.asyncio
async def test_weather_falls_back_when_optional_profile_read_is_denied() -> None:
    context = _WeatherContext()
    skill = WeatherSkill()
    skill._meta = {
        "name": "get_weather",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": [],
        },
    }
    skill.mcp_tool = "get_weather"

    result = await skill.execute({}, context)

    assert result.ok
    assert result.data == {"location": "苏州", "days": 3}
    assert [name for name, _ in context.calls] == [
        "manage_user_settings",
        "get_weather",
    ]


@pytest.mark.asyncio
async def test_weather_does_not_swallow_non_permission_profile_errors() -> None:
    class Context(_WeatherContext):
        async def call_mcp_tool(self, name: str, arguments: dict, **kwargs):
            if name == "manage_user_settings":
                raise RuntimeError("Business MCP 暂时不可用")
            return await super().call_mcp_tool(name, arguments, **kwargs)

    skill = WeatherSkill()
    skill._meta = {"name": "get_weather", "parameters": {"type": "object"}}
    skill.mcp_tool = "get_weather"

    with pytest.raises(RuntimeError, match="暂时不可用"):
        await skill.execute({}, Context())
