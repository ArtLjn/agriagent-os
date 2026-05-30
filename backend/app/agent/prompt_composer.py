"""Prompt 组合器 -- 按场景组合 snippet 片段渲染最终 prompt。"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from jinja2 import Template

if TYPE_CHECKING:
    from app.agent.prompt_registry import PromptRegistry

from app.agent.prompt_renderer import _build_builtin_vars

logger = logging.getLogger(__name__)

_PRIORITY_RE = re.compile(r"^p(\d)-")
_HEADING_RE = re.compile(r"^(【[^】]+】)", re.MULTILINE)
_COMPOSITIONS_KEY = "compositions"


class PromptComposer:
    """按场景组合 snippet 片段渲染最终 prompt。"""

    def __init__(self, registry: "PromptRegistry", prompts_dir: Path):
        self._registry = registry
        self._prompts_dir = prompts_dir
        self._snippets: dict[str, str] = {}
        self._compositions: dict[str, dict] = {}
        self._load_snippets()
        self._load_compositions()

    def _load_snippets(self) -> None:
        snippets_dir = self._prompts_dir / "snippets"
        if not snippets_dir.exists():
            logger.warning("snippets 目录不存在: %s", snippets_dir)
            return
        for f in snippets_dir.glob("*.j2"):
            name = f.stem
            self._snippets[name] = f.read_text()
        logger.info("Snippet 加载完成 | count=%d", len(self._snippets))

    def _load_compositions(self) -> None:
        config_path = self._prompts_dir / "config.yaml"
        if not config_path.exists():
            return
        config = yaml.safe_load(config_path.read_text()) or {}
        self._compositions = config.get(_COMPOSITIONS_KEY, {})
        logger.info("Compositions 加载完成 | count=%d", len(self._compositions))

    def list_snippets(self) -> list[str]:
        return sorted(self._snippets.keys())

    def compose(
        self,
        scene: str,
        variables: dict | None = None,
        *,
        current_date=None,
    ) -> str:
        if scene not in self._compositions:
            raise KeyError(f"场景未配置: {scene}")
        comp = self._compositions[scene]
        snippet_names = comp.get("snippets", [])
        separator = comp.get("separator", "\n\n")
        template_name = comp.get("template")

        builtin_vars = _build_builtin_vars(current_date)
        ctx = {**builtin_vars, **(variables or {})}

        parts = []
        seen = set()
        for name in snippet_names:
            if name in seen:
                continue
            seen.add(name)
            content = self._snippets.get(name)
            if content is None:
                logger.warning("Snippet 不存在: %s", name)
                continue
            rendered = Template(content).render(ctx)
            parts.append((name, rendered))

        parts.sort(key=lambda x: self._priority_of(x[0]))

        result = separator.join(p[1] for p in parts)

        if template_name:
            from app.agent.prompt_renderer import render_prompt

            template_text = render_prompt(
                template_name,
                variables=variables,
                registry=self._registry,
                current_date=current_date,
            )
            result = result + separator + template_text

        result = self._deduplicate_headings(result)

        return result

    @staticmethod
    def _priority_of(name: str) -> int:
        m = _PRIORITY_RE.match(name)
        if m:
            return int(m.group(1))
        return 99

    @staticmethod
    def _deduplicate_headings(text: str) -> str:
        """保留每个标题的首次出现，移除后续同标题段落。"""
        seen_headings: set[str] = set()
        lines = text.split("\n")
        out: list[str] = []
        skip = False
        for line in lines:
            m = _HEADING_RE.match(line)
            if m:
                heading = m.group(1)
                if heading in seen_headings:
                    skip = True
                    continue
                seen_headings.add(heading)
                skip = False
            if not skip:
                out.append(line)
        return "\n".join(out)


_composer: PromptComposer | None = None


def get_composer() -> PromptComposer:
    global _composer
    if _composer is None:
        from app.agent.prompt_registry import get_registry
        from app.core.config import get_settings

        settings = get_settings()
        _composer = PromptComposer(get_registry(), settings.prompts_dir)
    return _composer


__all__ = ["PromptComposer"]
