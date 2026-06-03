"""Agent 访问业务模块的端口定义。"""

from typing import Protocol


class FarmContextPort(Protocol):
    """读取 Agent 所需农场上下文的端口。"""

    async def get_context(self, farm_id: int) -> dict:
        """返回农场上下文。"""


class SkillExecutionPort(Protocol):
    """执行 Skill 的端口。"""

    async def execute(self, skill_name: str, params: dict, farm_id: int) -> object:
        """执行指定 Skill。"""


__all__ = ["FarmContextPort", "SkillExecutionPort"]
