"""Skill loader.

启动时扫描 agent/skills/*/ 目录：
1. 解析 skill.md YAML front matter 获取元数据（name/description/parameters/risk_level）
2. 如有 scripts/main.py → 导入自定义 Skill 子类，注入 skill.md 元数据
3. 如仅有 skill.md → 自动创建 McpSkill 实例（纯 MCP 代理，无自定义逻辑）

skill.md 是元数据的唯一来源。Python 类只负责自定义逻辑（execute/dynamic_risk_level）。
"""

from __future__ import annotations

import importlib
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from agent.skills.base import McpSkill, Skill

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parent


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


def _discover_skill_dirs() -> list[Path]:
    """扫描 agent/skills/*/ 目录。"""
    dirs = []
    for entry in sorted(_SKILLS_DIR.iterdir()):
        if (
            not entry.is_dir()
            or entry.name.startswith("_")
            or entry.name.startswith(".")
        ):
            continue
        dirs.append(entry)
    return dirs


def _load_skill(skill_dir: Path) -> Skill | None:
    """加载单个 skill 目录。"""
    skill_md = skill_dir / "skill.md"
    main_py = skill_dir / "scripts" / "main.py"

    meta: dict[str, Any] | None = None
    if skill_md.exists():
        meta = _parse_skill_md(skill_md)
        if meta:
            logger.debug("parsed skill.md: %s → %s", skill_dir.name, meta.get("name"))

    # 有 scripts/main.py → 导入自定义 Skill 子类
    if main_py.exists():
        module_path = f"agent.skills.{skill_dir.name}.scripts.main"
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("failed to import %s: %s", module_path, exc)
            return None

        # 找 Skill 子类实例
        instance = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, Skill):
                instance = attr
                break

        if instance is None:
            logger.warning("no Skill instance found in %s", module_path)
            return None

        # 注入 skill.md 元数据（覆盖 Python 类的重复定义）
        if meta:
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
            logger.warning(
                "skill %s is kind=local but has no scripts/main.py",
                skill_dir.name,
            )
            return None
        skill = _build_mcp_skill(meta)
        logger.info(
            "loaded skill: %s (mcp-auto, %s, %s)",
            skill.name,
            skill.kind,
            skill.risk_level,
        )
        return skill

    logger.warning("skill dir %s has neither skill.md nor scripts/main.py", skill_dir)
    return None


def load_all() -> list[Skill]:
    """加载所有 skill，返回实例列表。"""
    skills: list[Skill] = []
    for skill_dir in _discover_skill_dirs():
        result = _load_skill(skill_dir)
        if result is not None:
            operation_skills = result.operation_skills()
            skills.extend(operation_skills or [result])
    return skills


def to_openai_tools(skills: list[Skill]) -> list[dict[str, Any]]:
    """合并所有 skill 为 OpenAI tools schema。"""
    return [s.to_openai_tool() for s in skills]


def find_skill(skills: list[Skill], name: str) -> Skill | None:
    """按 name 查找 skill。"""
    for s in skills:
        if s.name == name:
            return s
    return None
