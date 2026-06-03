"""仿真测试报告生成器。"""

import logging
from collections import Counter

from app.simulation.models import SimulationResult, SimulationReport

logger = logging.getLogger(__name__)


class SimulationReporter:
    """仿真测试报告生成器。"""

    def generate(
        self, results: list[SimulationResult], run_id: str = ""
    ) -> SimulationReport:
        """
        根据执行结果生成汇总报告。
        统计：总数、通过数、失败数、准确率、平均延迟、失败分类 breakdown。
        """
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        accuracy = passed / total if total > 0 else 0.0
        avg_latency_ms = (
            sum(r.latency_ms for r in results) / total if total > 0 else 0.0
        )
        failure_breakdown = self._analyze_failures([r for r in results if not r.passed])

        logger.info(
            "仿真报告: 总计 %d, 通过 %d, 失败 %d, 准确率 %.2f%%",
            total,
            passed,
            failed,
            accuracy * 100,
        )

        return SimulationReport(
            run_id=run_id,
            total=total,
            passed=passed,
            failed=failed,
            accuracy=accuracy,
            avg_latency_ms=avg_latency_ms,
            failure_breakdown=failure_breakdown,
            results=results,
        )

    def _analyze_failures(self, results: list[SimulationResult]) -> dict[str, int]:
        """
        分析失败原因分布。
        从 errors 列表中提取错误类型（hallucination, attribution_error 等），统计数量。
        """
        counter: Counter = Counter()
        for result in results:
            for error in result.errors:
                error_type = self._extract_error_type(error)
                counter[error_type] += 1
        return dict(counter)

    @staticmethod
    def _extract_error_type(error: str) -> str:
        """从错误字符串前缀提取错误类型。"""
        if ":" in error:
            return error.split(":", 1)[0].strip()
        return "unknown"
