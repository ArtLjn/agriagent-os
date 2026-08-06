"""Skill Router 数据模型。"""

from dataclasses import asdict, dataclass, field
from typing import Literal

RiskLevel = Literal["none", "read", "write_confirm", "write_high"]


@dataclass(frozen=True)
class DisclosureBudget:
    """工具 schema 暴露预算。

    朴素全量注入模式(默认):
        max_tools_default / max_schema_tokens 是 safety guard 上限保护,
        防止未来 skill 数暴涨时 bind_tools 超 LLM 上下文。
        详见 docs/specs/2026-07-31-agent-harness-design.md §5.0。
    legacy 召回模式(settings.router.legacy_recall_mode=true):
        max_tools_default / max_schema_tokens 兼任召回预算,
        由 trim_candidates_by_budget 在 _model_choice_read_decision 中使用。
    """

    max_tools_default: int = 30
    max_tools_complex: int = 5
    max_write_tools: int = 1
    max_schema_tokens: int = 9000
    max_retrieved_tools_default: int = 3


@dataclass(frozen=True)
class ToolCandidate:
    """Catalog 中的一条 Skill 候选。"""

    name: str
    domain: str
    intents: list[str]
    risk: RiskLevel
    capability: str | None = None
    operation: str | None = None
    legacy_alias: str | None = None
    operation_risk: str | None = None
    entities: list[str] = field(default_factory=list)
    trigger_examples: list[str] = field(default_factory=list)
    anti_examples: list[str] = field(default_factory=list)
    context_dependencies: list[str] = field(default_factory=list)
    candidate_group: str = ""
    schema_token_estimate: int = 0
    enabled: bool = True
    score: float = 0.0
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class IntentFrame:
    """用户输入中的一个意图帧。"""

    domain: str
    intent: str
    risk: RiskLevel
    capability: str | None = None
    operation: str | None = None
    operation_hint: str | None = None
    entities: list[str] = field(default_factory=list)
    candidate_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0
    score: float = 0.0
    evidence: dict = field(default_factory=dict)
    params_hint: dict | None = None
    planning_evidence: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    requires_confirmation: bool = False


@dataclass(frozen=True)
class RouterDecision:
    """Router 输出给 runtime 的结构化决策。"""

    frames: list[IntentFrame] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    selected_operations: dict[str, list[str]] = field(default_factory=dict)
    context_dependencies: list[str] = field(default_factory=list)
    fallback: str | None = None
    fallback_reason: str | None = None
    reason: str = ""
    rejected_tools: list[str] = field(default_factory=list)
    rejected_candidates: list[dict] = field(default_factory=list)
    schema_token_estimate: int = 0
    policy_violations: list[str] = field(default_factory=list)
    clarification: str | None = None
    tool_choice: str = "auto"
    force_binding: tuple[str, ...] = ()
    scores: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def to_trace_payload(self) -> dict:
        return asdict(self)
