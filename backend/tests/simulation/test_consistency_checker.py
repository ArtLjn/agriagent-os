"""测试一致性检查器。"""


from app.simulation.consistency_checker import (
    _check_attribution_error,
    _check_expected_changes,
    _check_hallucination,
    _check_response_matches,
    _check_silent_mutation,
    check_consistency,
)
from app.simulation.models import Claim, DbDiff, SimulationTestCase


class TestCheckHallucination:
    def test_claim_with_db_change_passes(self):
        claims = [Claim(op_type="create_cost", description="已记账", keywords_matched=["已记账"])]
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        errors = _check_hallucination(claims, diff)
        assert errors == []

    def test_claim_without_db_change_fails(self):
        claims = [Claim(op_type="create_cost", description="已记账", keywords_matched=["已记账"])]
        diff = DbDiff()
        errors = _check_hallucination(claims, diff)
        assert len(errors) == 1
        assert "hallucination" in errors[0]
        assert "cost_records" in errors[0]

    def test_unknown_op_type_ignored(self):
        claims = [Claim(op_type="unknown_op", description="xxx", keywords_matched=["xxx"])]
        diff = DbDiff()
        errors = _check_hallucination(claims, diff)
        assert errors == []


class TestCheckAttributionError:
    def test_failure_words_with_db_changes(self):
        reply = "抱歉，记账失败了"
        claims = []
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        errors = _check_attribution_error(reply, claims, diff)
        assert len(errors) == 1
        assert "attribution_error" in errors[0]

    def test_failure_words_without_db_changes(self):
        reply = "抱歉，记账失败了"
        claims = []
        diff = DbDiff()
        errors = _check_attribution_error(reply, claims, diff)
        assert errors == []

    def test_success_reply_with_db_changes(self):
        reply = "已记账成功"
        claims = []
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        errors = _check_attribution_error(reply, claims, diff)
        assert errors == []


class TestCheckSilentMutation:
    def test_db_change_not_claimed(self):
        reply = "好的"
        claims = []
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        errors = _check_silent_mutation(reply, claims, diff)
        assert len(errors) == 1
        assert "silent_mutation" in errors[0]
        assert "cost_records" in errors[0]

    def test_db_change_claimed(self):
        reply = "已记账"
        claims = [Claim(op_type="create_cost", description="已记账", keywords_matched=["已记账"])]
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        errors = _check_silent_mutation(reply, claims, diff)
        assert errors == []

    def test_no_db_changes(self):
        reply = "好的"
        claims = []
        diff = DbDiff()
        errors = _check_silent_mutation(reply, claims, diff)
        assert errors == []


class TestCheckExpectedChanges:
    def test_expected_added_count_match(self):
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        expected = {"cost_records": {"added": 1}}
        errors = _check_expected_changes(diff, expected)
        assert errors == []

    def test_expected_added_count_mismatch(self):
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        expected = {"cost_records": {"added": 2}}
        errors = _check_expected_changes(diff, expected)
        assert len(errors) == 1
        assert "state_mismatch" in errors[0]

    def test_expected_match_fields_found(self):
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records", "category": "化肥"}])
        expected = {"cost_records": {"added": 1, "match_fields": {"category": "化肥"}}}
        errors = _check_expected_changes(diff, expected)
        assert errors == []

    def test_expected_match_fields_not_found(self):
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records", "category": "农药"}])
        expected = {"cost_records": {"added": 1, "match_fields": {"category": "化肥"}}}
        errors = _check_expected_changes(diff, expected)
        assert len(errors) == 1
        assert "state_mismatch" in errors[0]

    def test_empty_expected(self):
        diff = DbDiff()
        errors = _check_expected_changes(diff, {})
        assert errors == []


class TestCheckResponseMatches:
    def test_all_keywords_present(self):
        reply = "已记账化肥200元"
        errors = _check_response_matches(reply, ["已记账", "化肥"])
        assert errors == []

    def test_keyword_missing(self):
        reply = "已记账化肥200元"
        errors = _check_response_matches(reply, ["已记账", "农药"])
        assert len(errors) == 1
        assert "response_mismatch" in errors[0]
        assert "农药" in errors[0]

    def test_empty_expected(self):
        errors = _check_response_matches("任何回复", [])
        assert errors == []


class TestCheckConsistency:
    def test_all_checks_pass(self):
        case = SimulationTestCase(
            case_id="tc-001",
            description="正常记账",
            user_input="买化肥200",
            expected_response_matches=["已记账"],
            expected_db_changes={"cost_records": {"added": 1}},
            verify_tables=["cost_records"],
        )
        claims = [Claim(op_type="create_cost", description="已记账", keywords_matched=["已记账"])]
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records", "category": "化肥"}])
        errors = check_consistency("已记账化肥200元", claims, diff, case)
        assert errors == []

    def test_multiple_errors(self):
        case = SimulationTestCase(
            case_id="tc-002",
            description="幻觉测试",
            user_input="买化肥200",
            expected_response_matches=["已记账"],
            expected_db_changes={"cost_records": {"added": 1}},
            verify_tables=["cost_records"],
        )
        claims = [Claim(op_type="create_cost", description="已记账", keywords_matched=["已记账"])]
        diff = DbDiff()
        errors = check_consistency("已记账化肥200元", claims, diff, case)
        assert len(errors) >= 2
        assert any("hallucination" in e for e in errors)
        assert any("state_mismatch" in e for e in errors)

    def test_attribution_and_silent_mutation(self):
        case = SimulationTestCase(
            case_id="tc-003",
            description="归因错误",
            user_input="买化肥200",
            expected_response_matches=[],
            expected_db_changes={},
            verify_tables=["cost_records"],
        )
        reply = "抱歉，记账失败了，系统繁忙"
        claims = []
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        errors = check_consistency(reply, claims, diff, case)
        assert any("attribution_error" in e for e in errors)
        assert any("silent_mutation" in e for e in errors)
