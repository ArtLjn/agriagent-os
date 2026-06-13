"""每日建议 v2 校验模型和修复指令。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.daily_advice_models import DailyAdviceCandidate

FORBIDDEN_DAILY_ADVICE_TERMS = (
    "结算工人欠款",
    "催收人工工资",
    "未结人工",
    "未付人工",
    "欠薪",
    "无到期日欠款",
    "诸葛四郎",
    "李海",
    "朱7",
)


@dataclass(frozen=True, slots=True)
class DailyAdviceValidationIssue:
    """每日建议校验问题。"""

    code: str
    message: str
    path: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DailyAdviceValidationResult:
    """每日建议校验结果。"""

    valid: bool
    issues: list[DailyAdviceValidationIssue]
    repair_instruction: str


def build_validation_result(
    issues: list[DailyAdviceValidationIssue],
    candidates: list[DailyAdviceCandidate],
) -> DailyAdviceValidationResult:
    """构造校验结果并生成修复指令。"""
    return DailyAdviceValidationResult(
        valid=not issues,
        issues=issues,
        repair_instruction=_build_repair_instruction(issues, candidates),
    )


def _build_repair_instruction(
    issues: list[DailyAdviceValidationIssue],
    candidates: list[DailyAdviceCandidate],
) -> str:
    if not issues:
        return ""

    allowed_ids = ", ".join(candidate.id for candidate in candidates) or "无"
    lines = [
        "请修复 DailyAdvice v2 JSON 后重试：",
        f"- 只能使用 selected candidate id：{allowed_ids}。",
        "- 保留 candidate 的 category/source_type/source_id，priority 不得小于候选 priority。",
        "- compact.subtitle 至少 15 字，detail_view.description 至少 20 字。",
        "- detail_view.steps 至少 2 条，detail_view.actions 必须包含 ask_agent。",
        "- 普通非 empty/fallback item 的 detail_view.evidence 至少 1 条。",
        "- 不要输出禁止主题或禁止词。",
    ]
    for index, issue in enumerate(issues, start=1):
        detail = f"{index}. {issue.code}"
        if issue.path:
            detail += f" at {issue.path}"
        detail += f": {issue.message}"
        if issue.evidence:
            detail += f" evidence={issue.evidence}"
        lines.append(detail)
    return "\n".join(lines)
