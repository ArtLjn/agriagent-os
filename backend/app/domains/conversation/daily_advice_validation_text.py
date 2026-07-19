"""每日建议文本边界校验工具。"""

from __future__ import annotations

from typing import Any


def collect_text_bounds_reasons(
    checks: tuple[tuple[str, Any, int, int], ...],
) -> list[dict[str, Any]]:
    """收集文本必填、最短和最长边界问题。"""
    reasons: list[dict[str, Any]] = []
    for field, value, min_length, max_length in checks:
        length = len(value) if isinstance(value, str) else 0
        is_blank = isinstance(value, str) and not value.strip()
        if (
            not isinstance(value, str)
            or is_blank
            or length < min_length
            or length > max_length
        ):
            reasons.append(
                {
                    "field": field,
                    "min_length": min_length,
                    "max_length": max_length,
                    "actual_length": length,
                }
            )
    return reasons
