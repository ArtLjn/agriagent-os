"""Skill Router 数据模型。"""

from dataclasses import asdict, dataclass, field
from typing import Literal

RiskLevel = Literal["none", "read", "write_confirm", "write_high"]


@dataclass(frozen=True)
class DisclosureBudget:
    """工具 schema 暴露预算。"""

    max_tools_default: int = 3
    max_tools_complex: int = 5
    max_write_tools: int = 1
    max_schema_tokens: int = 1800


@dataclass(frozen=True)
class ToolCandidate:
    """Catalog 中的一条 Skill 候选。"""

    name: str
    domain: str
    intents: list[str]
    risk: RiskLevel
    entities: list[str] = field(default_factory=list)
    trigger_examples: list[str] = field(default_factory=list)
    anti_examples: list[str] = field(default_factory=list)
    context_dependencies: list[str] = field(default_factory=list)
    candidate_group: str = ""
    schema_token_estimate: int = 0
    enabled: bool = True


@dataclass(frozen=True)
class IntentFrame:
    """用户输入中的一个意图帧。"""

    domain: str
    intent: str
    risk: RiskLevel
    entities: list[str] = field(default_factory=list)
    candidate_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0
    params_hint: dict | None = None
    depends_on: list[str] = field(default_factory=list)
    requires_confirmation: bool = False


@dataclass(frozen=True)
class RouterDecision:
    """Router 输出给 runtime 的结构化决策。"""

    frames: list[IntentFrame] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    context_dependencies: list[str] = field(default_factory=list)
    fallback: str | None = None
    reason: str = ""
    rejected_tools: list[str] = field(default_factory=list)
    schema_token_estimate: int = 0
    policy_violations: list[str] = field(default_factory=list)
    clarification: str | None = None

    def to_trace_payload(self) -> dict:
        return asdict(self)
