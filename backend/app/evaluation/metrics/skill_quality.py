"""Skill 调用质量指标。"""

from app.evaluation.metrics.models import SkillQualityMetrics
from app.evaluation.replay.models import ReplayResult


def compute_skill_quality(results: list[ReplayResult]) -> SkillQualityMetrics:
    """统计准确率、漏调率、误调率、参数正确率和写确认命中率。"""
    expected_total = 0
    correct_total = 0
    missed_total = 0
    false_positive_total = 0
    argument_total = 0
    argument_correct = 0
    confirmation_total = 0
    confirmation_hit = 0
    unnecessary_clarification_total = 0
    execution_inconsistency_total = 0

    for result in results:
        expected_names = [call.name for call in result.expected_skill_calls]
        actual_names = [call.name for call in result.actual_skill_calls]
        expected_total += len(expected_names)
        errors = set(result.errors)
        if "unnecessary_clarification" in errors:
            unnecessary_clarification_total += 1
        if "execution_inconsistency" in errors:
            execution_inconsistency_total += 1

        for expected in result.expected_skill_calls:
            matching_actual = next(
                (
                    actual
                    for actual in result.actual_skill_calls
                    if actual.name == expected.name
                ),
                None,
            )
            if matching_actual is None:
                missed_total += 1
                continue
            correct_total += 1
            for key, expected_value in expected.arguments.items():
                argument_total += 1
                if matching_actual.arguments.get(key) == expected_value:
                    argument_correct += 1

        false_positive_total += len(
            [name for name in actual_names if name not in expected_names]
        )

        for write in result.expected_writes:
            if write.requires_confirmation:
                confirmation_total += 1
        confirmation_hit += result.write_confirmations_hit

    accuracy = correct_total / expected_total if expected_total else 1.0
    miss_rate = missed_total / expected_total if expected_total else 0.0
    actual_total = sum(len(result.actual_skill_calls) for result in results)
    false_positive_rate = false_positive_total / actual_total if actual_total else 0.0
    argument_accuracy = argument_correct / argument_total if argument_total else 1.0
    write_confirmation_hit_rate = (
        confirmation_hit / confirmation_total if confirmation_total else 1.0
    )
    result_total = len(results)
    unnecessary_clarification_rate = (
        unnecessary_clarification_total / result_total if result_total else 0.0
    )
    execution_consistency_rate = (
        1.0 - execution_inconsistency_total / result_total if result_total else 1.0
    )
    return SkillQualityMetrics(
        accuracy=accuracy,
        miss_rate=miss_rate,
        false_positive_rate=false_positive_rate,
        argument_accuracy=argument_accuracy,
        write_confirmation_hit_rate=write_confirmation_hit_rate,
        unnecessary_clarification_rate=unnecessary_clarification_rate,
        execution_consistency_rate=execution_consistency_rate,
    )
