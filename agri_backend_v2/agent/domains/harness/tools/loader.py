"""Skill loader.

启动时扫描核心技能目录和当前启用插件的技能目录：
1. 解析 skill.md YAML front matter 获取元数据（name/description/parameters/risk_level）
2. 如有 scripts/main.py → 按文件路径导入自定义 Skill 子类，注入 skill.md 元数据
3. 如仅有 skill.md → 自动创建 McpSkill 实例（纯 MCP 代理，无自定义逻辑）

skill.md 是元数据的唯一来源。Python 类只负责自定义逻辑（execute/dynamic_risk_level）。
任何技能加载失败都会抛 SkillLoadError，不允许静默少加载能力。
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from agent.domains.harness.tools.base import McpSkill, Skill
from agent.domains.harness.tools.registry import SkillRegistry

logger = logging.getLogger(__name__)

_CORE_SKILLS_DIR = Path(__file__).resolve().parents[3] / "tools"
# 兼容旧调用方：该常量只代表核心通用技能目录，不再包含业务插件技能。
_SKILLS_DIR = _CORE_SKILLS_DIR
_MODULE_CACHE: dict[Path, ModuleType] = {}


class SkillLoadError(ValueError):
    """技能目录不合法或自定义脚本加载失败。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _parse_skill_md(skill_md_path: Path) -> dict[str, Any] | None:
    """解析 skill.md YAML front matter，返回元数据 dict。"""
    text = skill_md_path.read_text(encoding="utf-8")
    # 提取 --- 包围的 front matter
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1))
        if not isinstance(meta, dict):
            return None
        return meta
    except yaml.YAMLError as exc:
        logger.warning("failed to parse %s: %s", skill_md_path, exc)
        return None


def _normalize_mcp_tool(raw: str) -> str:
    """skill.md 的 mcp_tool 可能是 'business.get_weather'，取最后一段作为实际 tool name。"""
    return raw.rsplit(".", 1)[-1] if "." in raw else raw


def _build_mcp_skill(meta: dict[str, Any]) -> McpSkill:
    """从 skill.md 元数据创建 McpSkill 实例。"""
    skill = McpSkill()
    skill._meta = meta
    skill.kind = meta.get("kind", "mcp")
    if isinstance(meta.get("mcp_tool"), str):
        skill.mcp_tool = _normalize_mcp_tool(meta["mcp_tool"])
    return skill


def _module_name(skill_dir: Path) -> str:
    """为文件路径加载生成稳定且唯一的模块名。"""
    scope = skill_dir.parent.parent.name
    digest = hashlib.sha1(str(skill_dir.resolve()).encode()).hexdigest()[:8]
    safe_name = re.sub(r"[^0-9a-zA-Z_]", "_", f"{scope}_{skill_dir.name}")
    return f"agent_plugin_{safe_name}_{digest}"


def _load_custom_module(main_py: Path, skill_dir: Path) -> ModuleType:
    """按文件路径导入插件脚本，并按 resolved path 缓存。"""
    resolved = main_py.resolve()
    cached = _MODULE_CACHE.get(resolved)
    if cached is not None:
        return cached

    module_name = _module_name(skill_dir)
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise SkillLoadError(
            "skill_module_invalid", f"无法为 {resolved} 创建模块"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise SkillLoadError(
            "skill_module_import_failed", f"{resolved}: {exc}"
        ) from exc
    _MODULE_CACHE[resolved] = module
    return module


def clear_module_cache() -> None:
    """清空插件脚本缓存，供测试和开发热更新使用。"""
    _MODULE_CACHE.clear()


class SkillLoader:
    """从指定 tools 目录发现并实例化 Tool，供 Registry 统一接管。"""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _discover_skill_dirs(self) -> list[Path]:
        if not self.directory.is_dir():
            raise SkillLoadError(
                "skill_directory_missing", f"技能目录不存在: {self.directory}"
            )
        return [
            entry
            for entry in sorted(self.directory.iterdir(), key=lambda path: path.name)
            if entry.is_dir() and not entry.name.startswith(("_", "."))
        ]

    def load_sources(self) -> list[Skill]:
        """加载目录中的聚合 Skill，供配置审计等旧调用方使用。"""
        skills: list[Skill] = []
        for skill_dir in self._discover_skill_dirs():
            skills.append(_load_skill(skill_dir))
        return skills

    def load_all(self) -> list[Skill]:
        """加载 Runtime 使用的展开 Skill，包括隐藏的 follow-up。"""
        skills: list[Skill] = []
        for result in self.load_sources():
            operation_skills = result.operation_skills()
            skills.extend(operation_skills or [result])
        return skills


def default_skill_dirs() -> list[Path]:
    """返回核心技能目录 + 当前启用插件的技能目录。"""
    from agent.config import settings

    directories = [_CORE_SKILLS_DIR]
    manifest = settings.plugins.manifest
    if manifest is not None:
        directories.append(manifest.skills_dir)
    return directories


def _resolve_directories(directories: Sequence[Path | str] | None) -> list[Path]:
    return [Path(directory) for directory in (directories or default_skill_dirs())]


def _combined_skill_dirs(directories: Sequence[Path | str]) -> list[Path]:
    """合并多个技能根目录，按目录名统一排序并拒绝同名目录。"""
    skill_dirs: dict[str, Path] = {}
    for directory in directories:
        loader = SkillLoader(directory)
        for skill_dir in loader._discover_skill_dirs():
            existing = skill_dirs.get(skill_dir.name)
            if existing is not None:
                raise SkillLoadError(
                    "skill_directory_duplicate",
                    f"技能目录 {skill_dir.name} 同时存在于 {existing} 和 {skill_dir}",
                )
            skill_dirs[skill_dir.name] = skill_dir
    return [skill_dirs[name] for name in sorted(skill_dirs)]


def load_sources_from(
    directories: Sequence[Path | str] | None = None,
) -> list[Skill]:
    """按目录名排序加载多个根目录下的聚合 Skill。"""
    return [
        _load_skill(skill_dir)
        for skill_dir in _combined_skill_dirs(_resolve_directories(directories))
    ]


def load_all_from(directories: Sequence[Path | str] | None = None) -> list[Skill]:
    """按目录名排序加载多个根目录下的展开 Skill。"""
    skills: list[Skill] = []
    for result in load_sources_from(directories):
        operation_skills = result.operation_skills()
        skills.extend(operation_skills or [result])
    return skills


def _load_skill(skill_dir: Path) -> Skill:
    """加载单个 skill 目录；任何失败都抛出，不返回 None。"""
    skill_md = skill_dir / "skill.md"
    main_py = skill_dir / "scripts" / "main.py"

    meta: dict[str, Any] | None = None
    if skill_md.exists():
        meta = _parse_skill_md(skill_md)
        if meta is None:
            raise SkillLoadError(
                "skill_metadata_invalid", f"{skill_md} 缺少有效的 YAML front matter"
            )
        logger.debug("parsed skill.md: %s → %s", skill_dir.name, meta.get("name"))

    # 有 scripts/main.py → 按文件路径导入自定义 Skill 子类
    if main_py.exists():
        module = _load_custom_module(main_py, skill_dir)
        instance = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, Skill):
                instance = attr
                break

        if instance is None:
            raise SkillLoadError(
                "skill_instance_missing", f"{main_py} 中没有 Skill 实例"
            )
        if not meta:
            raise SkillLoadError(
                "skill_metadata_missing", f"{skill_dir} 缺少 skill.md 元数据"
            )

        # 注入 skill.md 元数据（覆盖 Python 类的重复定义）
        instance._meta = meta
        if isinstance(meta.get("mcp_tool"), str):
            instance.mcp_tool = _normalize_mcp_tool(meta["mcp_tool"])

        logger.info(
            "loaded skill: %s (custom, %s, %s)",
            instance.name,
            instance.kind,
            instance.risk_level,
        )
        return instance

    # 无 scripts/main.py，仅有 skill.md → 自动创建 McpSkill
    if meta:
        if meta.get("kind") == "local":
            raise SkillLoadError(
                "skill_local_script_missing",
                f"skill {skill_dir.name} 声明 kind=local 但缺少 scripts/main.py",
            )
        skill = _build_mcp_skill(meta)
        logger.info(
            "loaded skill: %s (mcp-auto, %s, %s)",
            skill.name,
            skill.kind,
            skill.risk_level,
        )
        return skill

    raise SkillLoadError(
        "skill_source_missing", f"{skill_dir} 既没有 skill.md 也没有 scripts/main.py"
    )


def find_skill_dir(name: str, directories: Sequence[Path | str] | None = None) -> Path:
    """按目录名查找技能目录，供测试和工具脚本复用。"""
    for skill_dir in _combined_skill_dirs(_resolve_directories(directories)):
        if skill_dir.name == name:
            return skill_dir
    raise SkillLoadError("skill_directory_not_found", f"未找到技能目录: {name}")


def load_skill_module(skill_dir: Path | str) -> ModuleType:
    """加载技能目录下的 scripts/main.py，供测试和自定义逻辑复用。"""
    path = Path(skill_dir)
    main_py = path / "scripts" / "main.py"
    if not main_py.is_file():
        raise SkillLoadError(
            "skill_module_missing", f"技能脚本不存在: {main_py}"
        )
    return _load_custom_module(main_py, path)


def load_registry(
    directories: Sequence[Path | str] | None = None,
) -> SkillRegistry:
    """发现并加载所有 Skill，返回运行时注册表。"""
    return SkillRegistry.from_skills(load_all_from(directories))


def load_all(directories: Sequence[Path | str] | None = None) -> list[Skill]:
    """返回 Runtime 使用的展开 Skill；新代码应使用 :func:`load_registry`。"""
    return list(load_registry(directories).all())


def load_aggregate_skills(
    directories: Sequence[Path | str] | None = None,
) -> list[Skill]:
    """返回未展开的聚合 Skill，仅用于配置/风险审计。"""
    return load_sources_from(directories)


def to_openai_tools(
    skills: list[Skill] | SkillRegistry,
) -> list[dict[str, Any]]:
    """合并所有 skill 为 OpenAI tools schema。

    expose_to_model=false 的 skill（如 commit_planting_plan）不暴露给模型，
    由 Runtime 在 prepare 审批通过后用原始参数自动驱动。
    """
    if isinstance(skills, SkillRegistry):
        return skills.exposed_tools()
    return [s.to_openai_tool() for s in skills if s.exposed]


def find_skill(skills: list[Skill] | SkillRegistry, name: str) -> Skill | None:
    """按 name 查找 skill。"""
    if isinstance(skills, SkillRegistry):
        return skills.get(name)
    for s in skills:
        if s.name == name:
            return s
    return None
