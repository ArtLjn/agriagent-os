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
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records"}])
        errors = _check_hallucination(claims, diff)
        assert errors == []

    def test_claim_without_db_change_fails(self):
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
        diff = DbDiff()
        errors = _check_hallucination(claims, diff)
        assert len(errors) == 1
        assert "hallucination" in errors[0]
        assert "cost_records" in errors[0]

    def test_unknown_op_type_ignored(self):
        claims = [
            Claim(op_type="unknown_op", description="xxx", keywords_matched=["xxx"])
        ]
        diff = DbDiff()
        errors = _check_hallucination(claims, diff)
        assert errors == []

    def test_execution_failure_with_skill_trace(self):
        """有 skill trace 但 DB 无变化 → execution_failure。"""
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
        diff = DbDiff()
        skill_traces = [{"node_name": "create_cost_record", "status": "error"}]
        errors = _check_hallucination(claims, diff, skill_traces)
        assert len(errors) == 1
        assert "execution_failure" in errors[0]
        assert "skill 已被调用但数据库写入失败" in errors[0]

    def test_hallucination_without_skill_trace(self):
        """无 skill trace 且 DB 无变化 → 仍报 hallucination（原有行为）。"""
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
        diff = DbDiff()
        errors = _check_hallucination(claims, diff, [])
        assert len(errors) == 1
        assert "hallucination" in errors[0]

    def test_execution_failure_all_op_types(self):
        """测试所有 op_type 到 skill_name 的映射。"""
        from app.simulation.consistency_checker import _OP_TYPE_TO_SKILL_NAME

        for op_type, skill_name in _OP_TYPE_TO_SKILL_NAME.items():
            claims = [
                Claim(op_type=op_type, description="test", keywords_matched=["test"])
            ]
            diff = DbDiff()
            skill_traces = [{"node_name": skill_name, "status": "error"}]
            errors = _check_hallucination(claims, diff, skill_traces)
            assert len(errors) == 1, f"op_type={op_type} 应报 execution_failure"
            assert "execution_failure" in errors[0], (
                f"op_type={op_type} 错误类型应为 execution_failure"
            )

    def test_skill_trace_mismatch_skill_name(self):
        """skill trace 中的 skill_name 不匹配 → 仍报 hallucination。"""
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
        diff = DbDiff()
        skill_traces = [{"node_name": "wrong_skill", "status": "error"}]
        errors = _check_hallucination(claims, diff, skill_traces)
        assert len(errors) == 1
        assert "hallucination" in errors[0]


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
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
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
        diff = DbDiff(
            added=[{"id": 1, "__table__": "cost_records", "category": "化肥"}]
        )
        expected = {"cost_records": {"added": 1, "match_fields": {"category": "化肥"}}}
        errors = _check_expected_changes(diff, expected)
        assert errors == []

    def test_expected_match_fields_not_found(self):
        diff = DbDiff(
            added=[{"id": 1, "__table__": "cost_records", "category": "农药"}]
        )
        expected = {"cost_records": {"added": 1, "match_fields": {"category": "化肥"}}}
        errors = _check_expected_changes(diff, expected)
        assert len(errors) == 1
        assert "state_mismatch" in errors[0]

    def test_match_fields_substring_match(self):
        """子串匹配：预期 '番茄' 匹配实际 '番茄销售'。"""
        diff = DbDiff(
            added=[{"id": 1, "__table__": "cost_records", "category": "番茄销售"}]
        )
        expected = {"cost_records": {"added": 1, "match_fields": {"category": "番茄"}}}
        errors = _check_expected_changes(diff, expected)
        assert errors == []

    def test_match_fields_substring_reverse_no_match(self):
        """反向不匹配：预期 '番茄销售' 不能匹配实际 '番茄'。"""
        diff = DbDiff(
            added=[{"id": 1, "__table__": "cost_records", "category": "番茄"}]
        )
        expected = {
            "cost_records": {"added": 1, "match_fields": {"category": "番茄销售"}}
        }
        errors = _check_expected_changes(diff, expected)
        assert len(errors) == 1
        assert "state_mismatch" in errors[0]

    def test_match_fields_int_float_equality(self):
        """数字等值匹配：预期 int 200 匹配实际 float 200.0。"""
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records", "amount": 200.0}])
        expected = {"cost_records": {"added": 1, "match_fields": {"amount": 200}}}
        errors = _check_expected_changes(diff, expected)
        assert errors == []

    def test_match_fields_int_float_mismatch(self):
        """数字不匹配：预期 200 不能匹配实际 300.0。"""
        diff = DbDiff(added=[{"id": 1, "__table__": "cost_records", "amount": 300.0}])
        expected = {"cost_records": {"added": 1, "match_fields": {"amount": 200}}}
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
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
        diff = DbDiff(
            added=[{"id": 1, "__table__": "cost_records", "category": "化肥"}]
        )
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
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
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

    def test_cancel_scenario_skips_hallucination(self):
        """TC-ADV-002: 取消操作场景不判 hallucination。"""
        case = SimulationTestCase(
            case_id="tc-adv-002",
            description="取消后模板不应入库",
            user_input="创建新作物模板",
            expected_response_matches=[],
            expected_db_changes={},
            verify_tables=["crop_templates"],
        )
        claims = [
            Claim(
                op_type="create_template",
                description="已创建模板",
                keywords_matched=["已创建"],
            )
        ]
        diff = DbDiff()
        pending = {"action_id": "act-123", "skill_name": "create_crop_template"}
        errors = check_consistency("已创建模板", claims, diff, case, pending)
        assert not any("hallucination" in e for e in errors)

    def test_no_pending_still_checks_hallucination(self):
        """TC-ADV-003: 无 pending 的幻觉场景仍应报 hallucination。"""
        case = SimulationTestCase(
            case_id="tc-adv-003",
            description="幻觉检测",
            user_input="买化肥200",
            expected_response_matches=[],
            expected_db_changes={},
            verify_tables=["cost_records"],
        )
        claims = [
            Claim(
                op_type="create_cost", description="已记账", keywords_matched=["已记账"]
            )
        ]
        diff = DbDiff()
        errors = check_consistency("已记账化肥200元", claims, diff, case)
        assert any("hallucination" in e for e in errors)
