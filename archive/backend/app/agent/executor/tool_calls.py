"""Skill 调用执行入口。"""

from app.agent.runtime.nodes import _parallel_tool_node as execute_tool_calls
from app.agent.executor.models import ToolExecutionPlan
from app.infra.pending_actions import is_write_skill


def build_tool_execution_plan(name: str, arguments: dict) -> ToolExecutionPlan:
    """根据工具名生成权限和确认策略。"""
    is_write = is_write_skill(name)
    return ToolExecutionPlan(
        name=name,
        arguments=arguments,
        permission_level="write" if is_write else "read",
        requires_confirmation=is_write,
    )


__all__ = ["build_tool_execution_plan", "execute_tool_calls"]
