"""评测指标模型。"""

from dataclasses import dataclass, field


@dataclass
class ContextQualityMetrics:
    """上下文质量指标。"""

    hit_rate: float = 0.0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    budget_usage_rate: float = 0.0
    retrieval_usage_rate: float = 0.0


@dataclass
class SkillQualityMetrics:
    """Skill 调用质量指标。"""

    accuracy: float = 0.0
    miss_rate: float = 0.0
    false_positive_rate: float = 0.0
    argument_accuracy: float = 0.0
    write_confirmation_hit_rate: float = 0.0


@dataclass
class EvaluationMetrics:
    """结构化评测汇总指标。"""

    total_cases: int = 0
    passed_cases: int = 0
    pass_rate: float = 0.0
    avg_latency_ms: float = 0.0
    token_cost: float = 0.0
    context: ContextQualityMetrics = field(default_factory=ContextQualityMetrics)
    skill: SkillQualityMetrics = field(default_factory=SkillQualityMetrics)
