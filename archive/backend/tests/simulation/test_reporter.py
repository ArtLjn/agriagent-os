"""测试仿真测试报告生成器。"""

from datetime import datetime

from app.platforms.simulation.models import SimulationResult
from app.platforms.simulation.reporter import SimulationReporter


class TestSimulationReporterGenerate:
    def test_empty_results(self):
        reporter = SimulationReporter()
        report = reporter.generate([], run_id="run-001")

        assert report.run_id == "run-001"
        assert report.total == 0
        assert report.passed == 0
        assert report.failed == 0
        assert report.accuracy == 0.0
        assert report.avg_latency_ms == 0.0
        assert report.failure_breakdown == {}
        assert report.results == []
        assert isinstance(report.created_at, datetime)

    def test_all_passed(self):
        reporter = SimulationReporter()
        results = [
            SimulationResult(
                case_id="tc-001", passed=True, latency_ms=100, category="basic"
            ),
            SimulationResult(
                case_id="tc-002", passed=True, latency_ms=200, category="basic"
            ),
        ]
        report = reporter.generate(results, run_id="run-002")

        assert report.total == 2
        assert report.passed == 2
        assert report.failed == 0
        assert report.accuracy == 1.0
        assert report.avg_latency_ms == 150.0
        assert report.failure_breakdown == {}

    def test_all_failed(self):
        reporter = SimulationReporter()
        results = [
            SimulationResult(
                case_id="tc-001",
                passed=False,
                latency_ms=100,
                errors=["hallucination: xxx"],
            ),
            SimulationResult(
                case_id="tc-002",
                passed=False,
                latency_ms=200,
                errors=["attribution_error: yyy"],
            ),
        ]
        report = reporter.generate(results, run_id="run-003")

        assert report.total == 2
        assert report.passed == 0
        assert report.failed == 2
        assert report.accuracy == 0.0
        assert report.avg_latency_ms == 150.0
        assert report.failure_breakdown == {
            "hallucination": 1,
            "attribution_error": 1,
        }

    def test_mixed_results(self):
        reporter = SimulationReporter()
        results = [
            SimulationResult(case_id="tc-001", passed=True, latency_ms=100),
            SimulationResult(
                case_id="tc-002",
                passed=False,
                latency_ms=200,
                errors=["hallucination: aaa", "state_mismatch: bbb"],
            ),
            SimulationResult(
                case_id="tc-003",
                passed=False,
                latency_ms=150,
                errors=["hallucination: ccc"],
            ),
        ]
        report = reporter.generate(results, run_id="run-004")

        assert report.total == 3
        assert report.passed == 1
        assert report.failed == 2
        assert report.accuracy == 1 / 3
        assert report.avg_latency_ms == (100 + 200 + 150) / 3
        assert report.failure_breakdown == {
            "hallucination": 2,
            "state_mismatch": 1,
        }
        assert report.results == results

    def test_error_without_prefix(self):
        reporter = SimulationReporter()
        results = [
            SimulationResult(
                case_id="tc-001",
                passed=False,
                latency_ms=100,
                errors=["some random error without prefix"],
            ),
        ]
        report = reporter.generate(results, run_id="run-005")

        assert report.failure_breakdown == {"unknown": 1}

    def test_multiple_errors_same_case(self):
        reporter = SimulationReporter()
        results = [
            SimulationResult(
                case_id="tc-001",
                passed=False,
                latency_ms=100,
                errors=["hallucination: x", "hallucination: y"],
            ),
        ]
        report = reporter.generate(results, run_id="run-006")

        assert report.failure_breakdown == {"hallucination": 2}


class TestAnalyzeFailures:
    def test_analyze_failures(self):
        reporter = SimulationReporter()
        results = [
            SimulationResult(
                case_id="tc-001",
                passed=False,
                errors=["hallucination: x", "state_mismatch: y"],
            ),
            SimulationResult(
                case_id="tc-002",
                passed=False,
                errors=["hallucination: z"],
            ),
        ]
        breakdown = reporter._analyze_failures(results)

        assert breakdown == {
            "hallucination": 2,
            "state_mismatch": 1,
        }

    def test_analyze_failures_empty(self):
        reporter = SimulationReporter()
        assert reporter._analyze_failures([]) == {}

    def test_analyze_failures_no_prefix(self):
        reporter = SimulationReporter()
        results = [
            SimulationResult(
                case_id="tc-001",
                passed=False,
                errors=["random error"],
            ),
        ]
        breakdown = reporter._analyze_failures(results)
        assert breakdown == {"unknown": 1}
