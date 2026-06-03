"""Prompt 组合器。"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from jinja2 import Template

from app.prompt.models import PromptInput, PromptSnippet
from app.prompt.policy import priority_for_snippet, layer_for_snippet
from app.prompt.renderer import _build_builtin_vars, render_prompt_input

if TYPE_CHECKING:
    from app.prompt.registry import PromptRegistry

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(【[^】]+】)", re.MULTILINE)
_COMPOSITIONS_KEY = "compositions"


class PromptComposer:
    """按场景和职责层组合 snippet 片段，渲染最终 prompt。"""

    def __init__(self, registry: "PromptRegistry", prompts_dir: Path):
        self._registry = registry
        self._prompts_dir = prompts_dir
        self._snippets: dict[str, PromptSnippet] = {}
        self._compositions: dict[str, dict] = {}
        self._load_snippets()
        self._load_compositions()

    def _load_snippets(self) -> None:
        snippets_dir = self._prompts_dir / "snippets"
        if not snippets_dir.exists():
            logger.warning("snippets 目录不存在: %s", snippets_dir)
            return
        for file_path in snippets_dir.glob("*.j2"):
            name = file_path.stem
            self._snippets[name] = PromptSnippet(
                name=name,
                layer=layer_for_snippet(name),
                priority=priority_for_snippet(name),
                content=file_path.read_text(),
            )
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

    def list_layered_snippets(self, scene: str) -> list[PromptSnippet]:
        """按最终组合顺序列出指定场景的分层片段。"""
        if scene not in self._compositions:
            raise KeyError(f"场景未配置: {scene}")
        snippet_names = self._compositions[scene].get("snippets", [])
        snippets = [
            self._snippets[name]
            for name in dict.fromkeys(snippet_names)
            if name in self._snippets
        ]
        return sorted(snippets, key=lambda snippet: snippet.priority)

    def compose(
        self,
        scene: str,
        variables: dict | PromptInput | None = None,
        *,
        current_date=None,
        version: str | None = None,
    ) -> str:
        if scene not in self._compositions:
            raise KeyError(f"场景未配置: {scene}")
        prompt_input = self._coerce_input(variables, current_date=current_date)
        comp = self._compositions[scene]
        separator = comp.get("separator", "\n\n")
        template_name = comp.get("template")
        ctx = {
            **_build_builtin_vars(prompt_input.current_date),
            **prompt_input.as_variables(),
        }

        rendered_parts = [
            Template(snippet.content).render(ctx)
            for snippet in self.list_layered_snippets(scene)
        ]
        result = separator.join(rendered_parts)

        if template_name:
            template_text = render_prompt_input(
                template_name,
                prompt_input,
                registry=self._registry,
                version=version,
            )
            result = result + separator + template_text

        return self._deduplicate_headings(result)

    @staticmethod
    def _coerce_input(
        variables: dict | PromptInput | None,
        *,
        current_date=None,
    ) -> PromptInput:
        if isinstance(variables, PromptInput):
            return variables
        return PromptInput(variables=variables or {}, current_date=current_date)

    @staticmethod
    def _deduplicate_headings(text: str) -> str:
        """保留每个标题的首次出现，移除后续同标题段落。"""
        seen_headings: set[str] = set()
        lines = text.split("\n")
        out: list[str] = []
        skip = False
        for line in lines:
            match = _HEADING_RE.match(line)
            if match:
                heading = match.group(1)
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
        from app.core.config import settings
        from app.prompt.registry import get_registry

        _composer = PromptComposer(get_registry(), settings.prompts_dir)
    return _composer
