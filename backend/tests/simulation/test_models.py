"""测试 simulation 数据模型。"""

from datetime import datetime

from app.simulation.models import Claim, DbDiff, SimulationReport, SimulationResult, SimulationTestCase


class TestClaim:
    def test_claim_creation(self):
        claim = Claim(
            op_type="create_cost",
            description="已记账化肥200元",
            keywords_matched=["已记账"],
        )
        assert claim.op_type == "create_cost"
        assert claim.description == "已记账化肥200元"
        assert claim.keywords_matched == ["已记账"]


class TestDbDiff:
    def test_has_changes_for_table_with_changes(self):
        diff = DbDiff(
            added=[{"id": 1, "__table__": "cost_records", "amount": 200}],
        )
        assert diff.has_changes_for_table("cost_records") is True

    def test_has_changes_for_table_without_changes(self):
        diff = DbDiff(
            added=[{"id": 1, "__table__": "cost_records"}],
        )
        assert diff.has_changes_for_table("farm_logs") is False

    def test_has_changes_for_table_empty(self):
        diff = DbDiff()
        assert diff.has_changes_for_table("cost_records") is False

    def test_has_changes_for_table_removed(self):
        diff = DbDiff(
            removed=[{"id": 1, "__table__": "cost_records"}],
        )
        assert diff.has_changes_for_table("cost_records") is True

    def test_has_changes_for_table_modified(self):
        diff = DbDiff(
            modified=[{"id": 1, "__table__": "cost_records"}],
        )
        assert diff.has_changes_for_table("cost_records") is True


class TestSimulationTestCase:
    def test_default_category(self):
        case = SimulationTestCase(
            case_id="tc-001",
            description="测试记账",
            user_input="买化肥花了200",
            expected_response_matches=["已记账"],
            expected_db_changes={"cost_records": {"added": 1}},
            verify_tables=["cost_records"],
        )
        assert case.category == "basic"
        assert case.precondition == {}


class TestSimulationResult:
    def test_default_values(self):
        result = SimulationResult(case_id="tc-001", passed=True)
        assert result.agent_reply == ""
        assert result.errors == []
        assert result.db_diff == DbDiff()
        assert result.extracted_claims == []
        assert result.latency_ms == 0
        assert result.category == "basic"
        assert result.run_id == ""
        assert isinstance(result.created_at, datetime)


class TestSimulationReport:
    def test_report_creation(self):
        report = SimulationReport(
            run_id="run-001",
            total=10,
            passed=8,
            failed=2,
            accuracy=0.8,
            avg_latency_ms=120.5,
        )
        assert report.run_id == "run-001"
        assert report.total == 10
        assert report.passed == 8
        assert report.failed == 2
        assert report.accuracy == 0.8
        assert report.avg_latency_ms == 120.5
        assert report.failure_breakdown == {}
        assert report.results == []
        assert isinstance(report.created_at, datetime)
