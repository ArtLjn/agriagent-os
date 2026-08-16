"""已加载 Skill 的运行时注册表。

Loader 负责从文件系统发现并实例化 Skill；Registry 负责运行时按名称查找、
生成模型 Schema 和暴露能力。这样 ReAct Runtime 不需要知道 Skill 的目录结构。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from agent.skills.base import Skill


@dataclass(frozen=True)
class SkillRegistry:
    """一轮任务可用 Skill 的不可变快照。"""

    _skills: tuple[Skill, ...]
    _by_name: dict[str, Skill]

    @classmethod
    def from_skills(cls, skills: Iterable[Skill]) -> SkillRegistry:
        loaded = tuple(skills)
        by_name: dict[str, Skill] = {}
        for skill in loaded:
            if not skill.name:
                raise ValueError("skill name must not be empty")
            if skill.name in by_name:
                raise ValueError(f"duplicate skill name: {skill.name}")
            by_name[skill.name] = skill
        return cls(_skills=loaded, _by_name=by_name)

    def all(self) -> tuple[Skill, ...]:
        """返回所有已加载 Skill，包括仅供 Runtime 驱动的后继动作。"""
        return self._skills

    def get(self, name: str) -> Skill | None:
        """按模型侧或 Runtime 侧名称查找 Skill。"""
        return self._by_name.get(name)

    def require(self, name: str) -> Skill:
        """查找 Skill；不存在时抛出明确的配置错误。"""
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"unknown skill: {name}")
        return skill

    def as_index(self) -> dict[str, Skill]:
        """返回供 Planner 和执行代码兼容使用的索引副本。"""
        return dict(self._by_name)

    def names(self) -> tuple[str, ...]:
        """返回稳定的注册顺序，供诊断日志使用。"""
        return tuple(skill.name for skill in self._skills)

    def exposed_tools(self) -> list[dict[str, Any]]:
        """只返回允许模型直接调用的工具 Schema。"""
        return [skill.to_openai_tool() for skill in self._skills if skill.exposed]
