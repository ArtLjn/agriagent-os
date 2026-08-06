"""Prompt 集中管理。

从 prompts/ 目录加载 .md 模板文件，用 str.format() 渲染变量。
支持按场景名加载不同 prompt 文件。

用法：
    from agent.prompts import render_system_prompt
    prompt = render_system_prompt(memory_block=..., now=...)
"""
from __future__ import annotations

import logging
from datetime import datetime
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


def render_system_prompt(
    memory_block: str = "",
    now: str | None = None,
) -> str:
    """渲染 system prompt。

    Args:
        memory_block: 格式化的记忆文本块
        now: ISO 时间字符串，默认取当前时间
    """
    if now is None:
        now = datetime.now().isoformat(timespec="seconds")
    return render_prompt("system", memory_block=memory_block, now=now)


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
