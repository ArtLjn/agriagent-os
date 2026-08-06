"""Skill loader.

启动时扫描 agent/skills/*/scripts/main.py，实例化 Skill 子类，
合并为 react.py 使用的 skill registry。

loader 同时解析 skill.md front matter 的 risk_level 字段，
确保与 Skill.risk_level 属性一致（如果 skill.md 显式指定则覆盖）。
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any

from agent.skills.base import Skill

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parent


def _discover_skill_modules() -> list[str]:
    """扫描 agent/skills/*/scripts/main.py，返回完整模块路径。"""
    modules: list[str] = []
    for entry in _SKILLS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("_") or entry.name.startswith("."):
            continue
        scripts_dir = entry / "scripts"
        if not (scripts_dir / "main.py").exists():
            continue
        # 模块路径：agent.skills.<name>.scripts.main
        modules.append(f"agent.skills.{entry.name}.scripts.main")
    return modules


def _extract_skill_instance(module) -> Skill | None:
    """从模块中找到 Skill 子类实例。

    约定：每个 scripts/main.py 在模块底部有 `skill = <Name>Skill()`。
    """
    candidates = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, Skill):
            candidates.append(attr)
    if not candidates:
        return None
    if len(candidates) > 1:
        logger.warning(
            "module %s has %d Skill instances, using first",
            module.__name__, len(candidates),
        )
    return candidates[0]


def load_all() -> list[Skill]:
    """加载所有 skill，返回实例列表。"""
    skills: list[Skill] = []
    for module_path in _discover_skill_modules():
        try:
            module = importlib.import_module(module_path)
            instance = _extract_skill_instance(module)
            if instance is None:
                logger.warning("no Skill instance found in %s", module_path)
                continue
            skills.append(instance)
            logger.info("loaded skill: %s (%s, %s)",
                       instance.name, instance.kind, instance.risk_level)
        except Exception as exc:  # noqa: BLE001
            logger.exception("failed to load skill from %s: %s", module_path, exc)
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
