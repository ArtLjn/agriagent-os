"""结构化评测报告。"""

from app.platforms.evaluation.reports.builder import EvaluationReportBuilder
from app.platforms.evaluation.reports.models import EvaluationCaseResult, EvaluationReport

__all__ = ["EvaluationCaseResult", "EvaluationReport", "EvaluationReportBuilder"]
