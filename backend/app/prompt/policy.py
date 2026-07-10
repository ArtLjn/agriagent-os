"""Prompt 片段分层和排序策略。"""

import re

from app.prompt.models import PromptLayer

LAYER_ORDER: tuple[PromptLayer, ...] = (
    PromptLayer.SAFETY,
    PromptLayer.ROLE,
    PromptLayer.CAPABILITY,
    PromptLayer.TOOL,
    PromptLayer.CONTEXT,
    PromptLayer.OUTPUT,
    PromptLayer.STYLE,
)

_LAYER_PRIORITY = {layer: index * 100 for index, layer in enumerate(LAYER_ORDER)}
_PREFIX_RE = re.compile(r"^p(\d+)-")

_NAME_LAYER_MAP: dict[str, PromptLayer] = {
    "language": PromptLayer.SAFETY,
    "tool-guardrails": PromptLayer.SAFETY,
    "parallel-tool": PromptLayer.TOOL,
    "tool-result-guardrails": PromptLayer.SAFETY,
    "role": PromptLayer.ROLE,
    "capability": PromptLayer.CAPABILITY,
    "tool-guide": PromptLayer.TOOL,
    "context": PromptLayer.CONTEXT,
    "format": PromptLayer.OUTPUT,
    "style": PromptLayer.STYLE,
}


def layer_for_snippet(snippet_name: str) -> PromptLayer:
    """根据 snippet 文件名推导职责层。"""
    normalized = _PREFIX_RE.sub("", snippet_name)
    return _NAME_LAYER_MAP.get(normalized, PromptLayer.STYLE)


def priority_for_snippet(snippet_name: str) -> int:
    """根据职责层和文件名前缀计算稳定排序权重。"""
    layer = layer_for_snippet(snippet_name)
    prefix_match = _PREFIX_RE.match(snippet_name)
    prefix_priority = int(prefix_match.group(1)) if prefix_match else 99
    return _LAYER_PRIORITY[layer] + prefix_priority
