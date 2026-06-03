"""Context 质量指标。"""

from collections import Counter

from app.evaluation.metrics.models import ContextQualityMetrics
from app.evaluation.replay.models import ReplayResult


def compute_context_quality(results: list[ReplayResult]) -> ContextQualityMetrics:
    """统计上下文命中率、丢弃原因、预算使用和检索使用情况。"""
    required_total = 0
    hit_total = 0
    budget_used = 0
    budget_limit = 0
    retrieval_total = 0
    retrieval_used = 0
    dropped: Counter[str] = Counter()

    for result in results:
        required_total += len(result.required_context_facts)
        hit_total += len(result.hit_context_facts)
        budget_used += result.context_budget_used
        budget_limit += result.context_budget_limit
        retrieval_total += result.retrieval_results_count
        retrieval_used += result.retrieval_results_used
        dropped.update(result.context_drop_reasons)

    hit_rate = hit_total / required_total if required_total else 1.0
    budget_usage_rate = budget_used / budget_limit if budget_limit else 0.0
    retrieval_usage_rate = retrieval_used / retrieval_total if retrieval_total else 0.0
    return ContextQualityMetrics(
        hit_rate=hit_rate,
        drop_reasons=dict(dropped),
        budget_usage_rate=budget_usage_rate,
        retrieval_usage_rate=retrieval_usage_rate,
    )
