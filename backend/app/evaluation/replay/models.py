"""Agent 回放结果模型。"""

from dataclasses import dataclass, field
from typing import Any

from app.evaluation.cases.schemas import ExpectedSkillCall, ExpectedWriteOperation


@dataclass
class ActualSkillCall:
    """实际 skill/tool 调用。"""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "success"


@dataclass
class ReplayRunConfig:
    """回放运行配置。"""

    prompt_version: str = "default"
    config_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayResult:
    """单用例回放结果。"""

    case_id: str
    passed: bool
    reply: str = ""
    errors: list[str] = field(default_factory=list)
    expected_skill_calls: list[ExpectedSkillCall] = field(default_factory=list)
    actual_skill_calls: list[ActualSkillCall] = field(default_factory=list)
    expected_writes: list[ExpectedWriteOperation] = field(default_factory=list)
    actual_writes: list[dict[str, Any]] = field(default_factory=list)
    write_confirmations_hit: int = 0
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    token_cost: float = 0.0
    required_context_facts: list[str] = field(default_factory=list)
    hit_context_facts: list[str] = field(default_factory=list)
    context_drop_reasons: list[str] = field(default_factory=list)
    context_budget_used: int = 0
    context_budget_limit: int = 0
    retrieval_results_count: int = 0
    retrieval_results_used: int = 0
