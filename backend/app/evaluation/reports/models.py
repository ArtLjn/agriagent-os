"""结构化评测报告模型。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.evaluation.metrics.models import EvaluationMetrics


@dataclass
class EvaluationCaseResult:
    """单个用例报告。"""

    case_id: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    latency_ms: int = 0
    token_cost: float = 0.0
    skill_calls: list[str] = field(default_factory=list)
    drilldown_links: dict[str, str] = field(default_factory=dict)
    failure_stage: str = ""


@dataclass
class EvaluationReport:
    """评测运行报告。"""

    run_id: str
    created_at: datetime
    code_version: str
    prompt_version: str
    config_summary: dict[str, Any]
    metrics: EvaluationMetrics
    cases: list[EvaluationCaseResult] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
