"""Prompt 集中管理。

平台提示词（memory_*.md 等）仍从 prompts/ 目录加载；业务 system prompt 由
当前启用插件的 plugin.yaml 声明，不再固定放在 agent 包内。

用法：
    from agent.prompts import render_system_prompt
    prompt = render_system_prompt()  # 静态，无动态变量
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent
# 测试或开发环境可覆盖 system prompt 路径；生产环境从插件清单解析。
_SYSTEM_PROMPT_PATH: Path | None = None

# 模板缓存：resolved path → 渲染后的模板字符串（含 {placeholder}）。
_cache: dict[Path, str] = {}


def _system_prompt_path() -> Path:
    """返回当前启用插件的 system prompt 路径。"""
    if _SYSTEM_PROMPT_PATH is not None:
        return _SYSTEM_PROMPT_PATH
    from agent.config import settings

    manifest = settings.plugins.manifest
    if manifest is None:
        raise FileNotFoundError("plugin system prompt is not configured")
    return Path(manifest.system_prompt_path)


def _template_path(name: str) -> Path:
    """把模板名解析为文件路径。"""
    if name == "system":
        return _system_prompt_path()
    return _PROMPTS_DIR / f"{name}.md"


def _load_template(name: str) -> str:
    """加载并缓存 prompt 模板文件（.md）。"""
    path = _template_path(name)
    resolved = path.resolve()
    if resolved in _cache:
        return _cache[resolved]
    if not path.exists():
        raise FileNotFoundError(f"prompt template not found: {path}")
    content = path.read_text(encoding="utf-8")
    _cache[resolved] = content
    logger.info("prompt loaded: %s (%d chars)", path, len(content))
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
    """列出所有可用的 prompt 模板名，system 始终由插件提供。"""
    names = {path.stem for path in _PROMPTS_DIR.glob("*.md")}
    names.add("system")
    return sorted(names)


def reload() -> None:
    """清空缓存，下次访问时重新加载文件（用于 dev 模式热更新）。"""
    _cache.clear()


def inspect_prompts() -> list[dict]:
    """展示实际加载模板及内容指纹，版本随提示词内容变化。"""
    from agent.plugins import display_path

    items = []
    for name in list_prompts():
        path = _template_path(name)
        content = _load_template(name)
        source = (
            display_path(path)
            if name == "system"
            else f"agent/prompts/{name}.md"
        )
        items.append(
            {
                "name": name,
                "version": hashlib.sha256(content.encode()).hexdigest()[:12],
                "active": name == "system",
                "content": content,
                "content_length": len(content),
                "source": source,
            }
        )
    return items


__all__ = [
    "inspect_prompts",
    "list_prompts",
    "reload",
    "render_prompt",
    "render_system_prompt",
]
