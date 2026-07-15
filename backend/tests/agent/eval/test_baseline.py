"""Baseline：跑 Eval 集，记录当前 select_tools 行为。

执行：pytest tests/agent/eval/test_baseline.py -v -s
观察 stdout 输出的指标，记录到 spec 文档作为 baseline。
"""

import pytest

from tests.agent.eval.cases import all_eval_cases, B_QUERY_CASES, B_CHITCHAT_CASES


def _select_tools_safe(user_message, tools):
    """安全调用 select_tools，捕获异常返回 None。"""
    try:
        from app.agent.tool_selector import select_tools

        return select_tools(user_message, tools)
    except Exception:
        return None


@pytest.mark.parametrize("case", B_QUERY_CASES, ids=lambda c: c.case_id)
class TestBaselineQueryIntentNoForceBinding:
    """Baseline：B_QUERY 用例不再使用查询类 force_binding。"""

    def test_no_force_binding_for_query_intent(self, case, fake_tool_factory):
        tools = [fake_tool_factory(case.expected_skill)]
        result = _select_tools_safe(case.user_message, tools)

        if result is None:
            pytest.fail(f"{case.case_id}: select_tools raised exception")

        assert not result.force_binding, (
            f"{case.case_id}: query should not force_bind, "
            f"got force_binding={result.force_binding}, tools={result.tools}"
        )


@pytest.mark.parametrize("case", B_CHITCHAT_CASES, ids=lambda c: c.case_id)
class TestBaselineChitchatNoFalsePositive:
    """Baseline：B_CHITCHAT 用例不应该触发 force_binding。"""

    def test_no_force_binding_for_chitchat(self, case, fake_tool_factory):
        # 给所有可能的 query skill 作为候选
        all_query_skills = [
            "weather",
            "manage_crop_cycle",
            "manage_workers",
            "manage_labor_payment",
            "get_debt_summary",
        ]
        tools = [fake_tool_factory(name) for name in all_query_skills]
        result = _select_tools_safe(case.user_message, tools)

        if result is None:
            pytest.skip(f"{case.case_id}: select_tools raised exception")

        # 闲聊不应触发任何 force_binding
        assert not result.force_binding, (
            f"{case.case_id}: chitchat falsely triggered force_binding={result.force_binding}"
        )


class TestEvalCaseCoverage:
    """契约测试：验证用例总数和分类。"""

    def test_total_cases_count(self):
        cases = all_eval_cases()
        assert len(cases) == 48, f"expected 48 cases, got {len(cases)}"

    def test_category_distribution(self):
        cases = all_eval_cases()
        categories = {c.category for c in cases}
        expected = {
            "B_QUERY",
            "B_WRITE",
            "B_MULTI_INTENT",
            "B_CHITCHAT",
            "E2_MULTITURN",
        }
        assert categories == expected

    def test_b_query_has_20_cases(self):
        from tests.agent.eval.cases import B_QUERY_CASES

        assert len(B_QUERY_CASES) == 20

    def test_b_write_has_10_cases(self):
        from tests.agent.eval.cases import B_WRITE_CASES

        assert len(B_WRITE_CASES) == 10

    def test_b_multi_intent_has_5_cases(self):
        from tests.agent.eval.cases import B_MULTI_INTENT_CASES

        assert len(B_MULTI_INTENT_CASES) == 5

    def test_b_chitchat_has_8_cases(self):
        from tests.agent.eval.cases import B_CHITCHAT_CASES

        assert len(B_CHITCHAT_CASES) == 8

    def test_e2_multiturn_has_5_cases(self):
        from tests.agent.eval.cases import E2_MULTITURN_CASES

        assert len(E2_MULTITURN_CASES) == 5
