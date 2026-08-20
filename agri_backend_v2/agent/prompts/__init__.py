"""Prompt 集中管理。

从 prompts/ 目录加载 .md 模板文件，用 str.format() 渲染变量。
支持按场景名加载不同 prompt 文件。

用法：
    from agent.prompts import render_system_prompt
    prompt = render_system_prompt()  # 静态，无动态变量
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent

# 模板缓存：文件名 → 渲染后的模板字符串（含 {placeholder}）。
_cache: dict[str, str] = {}


def _load_template(name: str) -> str:
    """加载并缓存 prompt 模板文件（.md）。

    文件路径：prompts/{name}.md
    """
    if name in _cache:
        return _cache[name]
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt template not found: {path}")
    content = path.read_text(encoding="utf-8")
    _cache[name] = content
    logger.info("prompt loaded: %s (%d chars)", name, len(content))
    return content


def render_prompt(name: str, **variables: Any) -> str:
    """渲染指定 prompt 模板。

    用 str.format() 替换 {variable} 占位符。
    """
    template = _load_template(name)
    return template.format(**variables)


def render_system_prompt() -> str:
    """渲染静态 system prompt（完全可缓存，不含动态变量）。

    时间和记忆在 context.build_initial_messages 中注入到 user message，
    保证 system prompt byte-for-byte 不变，最大化 prompt cache 命中率。
    """
    return _load_template("system")


def list_prompts() -> list[str]:
    """列出所有可用的 prompt 模板名。"""
    return sorted(p.stem for p in _PROMPTS_DIR.glob("*.md"))


def reload() -> None:
    """清空缓存，下次访问时重新加载文件（用于 dev 模式热更新）。"""
    _cache.clear()


__all__ = [
    "render_prompt",
    "render_system_prompt",
    "list_prompts",
    "reload",
]
