"""已加载 Skill 的运行时注册表。

Loader 负责从文件系统发现并实例化 Skill；Registry 负责运行时按名称查找、
生成模型 Schema 和暴露能力。这样 ReAct Runtime 不需要知道 Skill 的目录结构。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.skills.base import McpSkill, Skill


class SkillRegistryError(ValueError):
    """Skill 配置错误，保留稳定 code 和 Skill 名称供诊断。"""

    def __init__(self, code: str, skill_name: str, message: str) -> None:
        self.code = code
        self.skill_name = skill_name
        super().__init__(f"{code}: {skill_name}: {message}")


@dataclass(frozen=True)
class SkillRegistry:
    """一轮任务可用 Skill 的不可变快照。"""

    _skills: tuple[Skill, ...]
    _by_name: dict[str, Skill]

    @classmethod
    def from_directory(cls, directory: Path | str) -> SkillRegistry:
        """通过 Loader 发现指定目录中的 Skill 并构建 Registry。

        Loader 只负责文件系统和模块发现；Registry 在这里统一接管校验、
        查找和公开能力视图，避免运行时再次维护列表或索引。
        """
        from agent.skills.loader import SkillLoader

        return cls.from_skills(SkillLoader(directory).load_all())

    @classmethod
    def from_skills(cls, skills: Iterable[Skill]) -> SkillRegistry:
        loaded = tuple(skills)
        by_name: dict[str, Skill] = {}
        for skill in loaded:
            if not skill.name:
                raise SkillRegistryError(
                    "skill_name_empty", "<unknown>", "skill name must not be empty"
                )
            if skill.name in by_name:
                raise SkillRegistryError(
                    "duplicate_skill_name", skill.name, "skill name is registered twice"
                )
            cls._validate_skill(skill)
            by_name[skill.name] = skill
        cls._validate_followups(loaded, by_name)
        return cls(_skills=loaded, _by_name=by_name)

    @staticmethod
    def _validate_skill(skill: Skill) -> None:
        schema = skill.parameters_schema
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise SkillRegistryError(
                "invalid_skill_schema",
                skill.name,
                "parameters must be an object schema",
            )
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise SkillRegistryError(
                "invalid_skill_schema",
                skill.name,
                "properties must be an object and required must be a list",
            )
        if not all(isinstance(name, str) for name in required):
            raise SkillRegistryError(
                "invalid_skill_schema",
                skill.name,
                "required entries must be strings",
            )
        unknown_required = [name for name in required if name not in properties]
        if unknown_required:
            raise SkillRegistryError(
                "invalid_skill_schema",
                skill.name,
                f"required field is missing from properties: {unknown_required}",
            )
        if skill.kind not in {"local", "mcp"}:
            raise SkillRegistryError(
                "invalid_skill_kind", skill.name, f"unsupported kind: {skill.kind}"
            )
        if isinstance(skill, McpSkill) and not skill.mcp_tool:
            raise SkillRegistryError(
                "mcp_tool_missing", skill.name, "MCP Skill must declare mcp_tool"
            )

    @staticmethod
    def _validate_followups(
        skills: tuple[Skill, ...], by_name: dict[str, Skill]
    ) -> None:
        for skill in skills:
            followup = skill.approval_followup
            if not followup:
                continue
            target_name = followup.get("tool_name")
            target = by_name.get(target_name)
            if target is None:
                raise SkillRegistryError(
                    "approval_followup_missing",
                    skill.name,
                    f"follow-up skill is not registered: {target_name}",
                )
            if target.exposed:
                raise SkillRegistryError(
                    "approval_followup_exposed",
                    target.name,
                    "approval follow-up must not be exposed to the model",
                )

    def all(self) -> tuple[Skill, ...]:
        """返回所有已加载 Skill，包括仅供 Runtime 驱动的后继动作。"""
        return self._skills

    def get(self, name: str) -> Skill | None:
        """按模型侧或 Runtime 侧名称查找 Skill。"""
        return self._by_name.get(name)

    def __contains__(self, name: object) -> bool:
        """兼容 Planner 的名称 membership 检查，同时保持查找集中在 Registry。"""
        return isinstance(name, str) and name in self._by_name

    def require(self, name: str) -> Skill:
        """查找 Skill；不存在时抛出明确的配置错误。"""
        skill = self.get(name)
        if skill is None:
            raise SkillRegistryError("skill_missing", name, "skill is not registered")
        return skill

    def as_index(self) -> dict[str, Skill]:
        """兼容旧调用方的索引副本；新 Runtime 直接使用 Registry。"""
        return dict(self._by_name)

    def names(self) -> tuple[str, ...]:
        """返回稳定的注册顺序，供诊断日志使用。"""
        return tuple(skill.name for skill in self._skills)

    def exposed(self) -> tuple[Skill, ...]:
        """返回允许模型直接调用的 Skill，保留 Registry 的查找边界。"""
        return tuple(skill for skill in self._skills if skill.exposed)

    def exposed_tools(self) -> list[dict[str, Any]]:
        """只返回允许模型直接调用的工具 Schema。"""
        return [skill.to_openai_tool() for skill in self.exposed()]

    def snapshot(self) -> dict[str, tuple[Any, ...]]:
        """返回排序后的能力快照，用于迁移前后集合比较。"""
        exposed = self.exposed()
        return {
            "skill_names": tuple(sorted(skill.name for skill in self._skills)),
            "exposed_tool_names": tuple(
                sorted(skill.to_openai_tool()["function"]["name"] for skill in exposed)
            ),
            "risk_levels": tuple(
                sorted((skill.name, skill.risk_level) for skill in self._skills)
            ),
        }
