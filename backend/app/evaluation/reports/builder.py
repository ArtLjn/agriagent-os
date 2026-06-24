"""结构化评测报告生成器。"""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from app.evaluation.metrics.context_quality import compute_context_quality
from app.evaluation.metrics.models import EvaluationMetrics
from app.evaluation.metrics.skill_quality import compute_skill_quality
from app.evaluation.replay.models import ReplayResult
from app.evaluation.reports.models import EvaluationCaseResult, EvaluationReport


class EvaluationReportBuilder:
    """生成可接入 CI 的结构化评测报告。"""

    def build(
        self,
        run_id: str,
        results: list[ReplayResult],
        prompt_version: str,
        config_summary: dict[str, Any] | None = None,
        code_version: str | None = None,
    ) -> EvaluationReport:
        total = len(results)
        passed = sum(1 for result in results if result.passed)
        avg_latency_ms = (
            sum(result.latency_ms for result in results) / total if total else 0.0
        )
        metrics = EvaluationMetrics(
            total_cases=total,
            passed_cases=passed,
            pass_rate=passed / total if total else 0.0,
            avg_latency_ms=avg_latency_ms,
            token_cost=sum(result.token_cost for result in results),
            context=compute_context_quality(results),
            skill=compute_skill_quality(results),
        )
        return EvaluationReport(
            run_id=run_id,
            created_at=datetime.now(),
            code_version=code_version or "unknown",
            prompt_version=prompt_version,
            config_summary=config_summary or {},
            metrics=metrics,
            cases=[
                EvaluationCaseResult(
                    case_id=result.case_id,
                    passed=result.passed,
                    errors=result.errors,
                    latency_ms=result.latency_ms,
                    token_cost=result.token_cost,
                    skill_calls=[call.name for call in result.actual_skill_calls],
                    drilldown_links=result.drilldown_links,
                    failure_stage=self._failure_stage(result),
                )
                for result in results
            ],
            coverage=self._build_coverage(results),
        )

    def to_dict(self, report: EvaluationReport) -> dict[str, Any]:
        """转换为 JSON 友好的 dict。"""
        data = asdict(report)
        data["created_at"] = report.created_at.isoformat()
        return data

    def _build_coverage(self, results: list[ReplayResult]) -> dict[str, Any]:
        coverage = {
            "by_skill": {},
            "by_business_domain": {},
            "by_permission_level": {},
            "by_confirmation_path": {},
            "by_context_dependency": {},
            "by_failure_stage": {},
            "semantic_planning_failures": 0,
        }
        for result in results:
            metadata = result.case_metadata
            self._count(coverage["by_business_domain"], metadata.get("business_domain"))
            self._count(
                coverage["by_permission_level"], metadata.get("permission_level")
            )
            self._count(
                coverage["by_confirmation_path"],
                metadata.get("confirmation_path"),
            )
            for dependency in metadata.get("context_dependencies", []):
                self._count(coverage["by_context_dependency"], dependency)
            for expected in result.expected_skill_calls:
                self._count(coverage["by_skill"], expected.name)
            failure_stage = self._failure_stage(result)
            self._count(coverage["by_failure_stage"], failure_stage)
            if failure_stage == "planning":
                coverage["semantic_planning_failures"] += 1
        return coverage

    @staticmethod
    def _count(bucket: dict[str, int], key: Any) -> None:
        if not key:
            return
        bucket[str(key)] = bucket.get(str(key), 0) + 1

    @staticmethod
    def _failure_stage(result: ReplayResult) -> str:
        stage = result.case_metadata.get("failure_stage")
        if stage:
            return str(stage)
        for error in result.errors:
            if "planning" in error or "语义" in error or "意图" in error:
                return "planning"
            if "validation" in error or "missing" in error:
                return "validation"
            if "pending" in error:
                return "pending_creation"
            if "execution" in error or "工具调用失败" in error:
                return "execution"
            if "bad_reply" in error:
                return "response_quality"
        return ""
