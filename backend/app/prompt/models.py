"""Prompt 工程化数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class PromptLayer(StrEnum):
    """Prompt 片段职责层。"""

    SAFETY = "safety"
    ROLE = "role"
    CAPABILITY = "capability"
    TOOL = "tool"
    CONTEXT = "context"
    OUTPUT = "output"
    STYLE = "style"


@dataclass(frozen=True)
class PromptInput:
    """Prompt 渲染结构化输入。

    渲染层只消费已经准备好的变量，不查询数据库或业务服务。
    """

    variables: Mapping[str, Any] = field(default_factory=dict)
    current_date: date | None = None

    def as_variables(self) -> dict[str, Any]:
        return dict(self.variables)


@dataclass(frozen=True)
class PromptSnippet:
    """已加载的 Prompt 片段。"""

    name: str
    layer: PromptLayer
    priority: int
    content: str


@dataclass(frozen=True)
class PromptVersion:
    """Prompt 模板版本元数据。"""

    name: str
    version: str
    content: str
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
