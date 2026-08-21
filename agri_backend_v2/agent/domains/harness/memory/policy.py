"""Short Memory / Long-term Memory 的 Context 注入策略。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


_LONG_TERM_DEPENDENCIES = frozenset(
    {
        "long_term_memory",
        "memory_hits",
        "user_memory",
        "farm_memory",
    }
)


@dataclass(frozen=True)
class MemoryInjectionPolicy:
    """一次 Context 构建使用的 Memory 层选择结果。"""

    include_short_term: bool = True
    include_long_term: bool = False
    long_term_reason: str = "not_requested"


def resolve_memory_policy(
    *,
    include_long_term: bool = False,
    context_dependencies: Iterable[str] = (),
) -> MemoryInjectionPolicy:
    """根据显式请求或 Skill dependency 决定是否注入长期记忆。

    Short Memory 是每个 Conversation Context 的默认输入；Long-term Memory
    必须由调用方显式请求或由 Skill metadata 声明依赖，避免把跨会话事实
    无条件注入闲聊和简单查询。
    """
    dependencies = {str(item) for item in context_dependencies if item}
    dependency_requested = bool(dependencies & _LONG_TERM_DEPENDENCIES)
    if include_long_term:
        return MemoryInjectionPolicy(
            include_long_term=True,
            long_term_reason="explicit_request",
        )
    if dependency_requested:
        return MemoryInjectionPolicy(
            include_long_term=True,
            long_term_reason="skill_dependency",
        )
    return MemoryInjectionPolicy()


__all__ = ["MemoryInjectionPolicy", "resolve_memory_policy"]
