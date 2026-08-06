"""评测基线模型。"""

from dataclasses import dataclass, field

from app.platforms.evaluation.metrics.models import EvaluationMetrics


@dataclass
class EvaluationBaseline:
    """可用于 CI 七道门的轻量基线。"""

    name: str
    prompt_version: str
    metrics: EvaluationMetrics
    min_pass_rate: float = 0.8
    max_avg_latency_ms: float | None = None
    max_token_cost: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)
