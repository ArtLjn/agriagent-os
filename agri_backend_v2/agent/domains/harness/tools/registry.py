"""已加载 Skill 的运行时注册表。

Loader 负责从文件系统发现并实例化 Skill；Registry 负责运行时按名称查找、
生成模型 Schema 和暴露能力。这样 ReAct Runtime 不需要知道 Skill 的目录结构。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.domains.harness.tools.base import McpSkill, Skill


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
        from agent.domains.harness.tools.loader import SkillLoader

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
        cls._validate_dependencies(loaded, by_name)
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
        execution = skill._meta.get("execution") or {}
        if not isinstance(execution, dict):
            raise SkillRegistryError(
                "invalid_execution_policy",
                skill.name,
                "execution must be an object",
            )
        mode = execution.get("mode", "serial")
        if mode not in {
            "serial",
            "parallel_safe",
            "serial_after_observation",
            "internal_followup",
        }:
            raise SkillRegistryError(
                "invalid_execution_mode",
                skill.name,
                f"unsupported execution mode: {mode}",
            )
        max_concurrency = execution.get("max_concurrency", 1)
        if (
            not isinstance(max_concurrency, int)
            or isinstance(max_concurrency, bool)
            or max_concurrency < 1
        ):
            raise SkillRegistryError(
                "invalid_max_concurrency",
                skill.name,
                "max_concurrency must be a positive integer",
            )
        requires_observation = execution.get("requires_observation", False)
        if not isinstance(requires_observation, bool):
            raise SkillRegistryError(
                "invalid_execution_policy",
                skill.name,
                "requires_observation must be boolean",
            )
        depends_on = execution.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(
            isinstance(item, str) and item for item in depends_on
        ):
            raise SkillRegistryError(
                "invalid_execution_dependencies",
                skill.name,
                "depends_on must be a list of non-empty strings",
            )
        if mode == "parallel_safe" and skill.risk_level != "read":
            raise SkillRegistryError(
                "parallel_write_forbidden",
                skill.name,
                "parallel_safe requires risk_level=read",
            )
        if mode == "internal_followup" and skill.exposed:
            raise SkillRegistryError(
                "internal_followup_exposed",
                skill.name,
                "internal_followup skill must not be exposed",
            )
        completion = skill._meta.get("completion") or {}
        if not isinstance(completion, dict):
            raise SkillRegistryError(
                "invalid_completion_policy",
                skill.name,
                "completion must be an object",
            )
        if "finalize_after_success" in completion and not isinstance(
            completion["finalize_after_success"], bool
        ):
            raise SkillRegistryError(
                "invalid_completion_policy",
                skill.name,
                "completion.finalize_after_success must be boolean",
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

    @staticmethod
    def _validate_dependencies(
        skills: tuple[Skill, ...], by_name: dict[str, Skill]
    ) -> None:
        """校验 Registry 内可解析的 Tool 依赖，保留资源键的扩展空间。"""
        graph = {
            skill.name: [
                dependency for dependency in skill.depends_on if dependency in by_name
            ]
            for skill in skills
        }
        for skill in skills:
            if skill.name in skill.depends_on:
                raise SkillRegistryError(
                    "execution_dependency_self",
                    skill.name,
                    "skill cannot depend on itself",
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise SkillRegistryError(
                    "execution_dependency_cycle",
                    name,
                    "execution dependencies contain a cycle",
                )
            if name in visited:
                return
            visiting.add(name)
            for dependency in graph.get(name, []):
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for skill in skills:
            visit(skill.name)

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
