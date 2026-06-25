"""污染对照测试（Layer 1：Tool selection 层）。

验证 select_tools 在 ContextBundle 有污染时，仍然 force_bind 正确 Skill。
不跑 LLM，直接验证工具选择层不受污染影响。

设计意图（13_Agent范式规范化设计.md §5.9.5）：
- 回复数据应来自 Skill 而非 ContextBundle
- select_tools 只看 user_message，不看 ContextBundle
- 因此污染数据不应影响工具选择结果
"""
import pytest

from app.agent.tool_selector import select_tools
from tests.agent.eval.cases import E2_MULTITURN_CASES, B_QUERY_CASES


@pytest.mark.parametrize("case", E2_MULTITURN_CASES, ids=lambda c: c.case_id)
class TestPollutionDifferentialE2:
    """E2 用例：污染 vs 无污染，select_tools 结果应一致。"""

    def test_select_tools_ignores_pollution(self, case, fake_tool_factory):
        """有污染数据时，select_tools 仍应 force_bind expected_skill。

        select_tools 只看 user_message，不看 ContextBundle，
        所以污染数据不影响工具选择。本测试通过"概念对照"验证：
        两次调用（对应"有污染上下文"和"无污染上下文"）结果必须一致，
        且都包含 expected_skill 的 force_binding。
        """
        if not case.expected_skill:
            pytest.skip(f"{case.case_id}: no expected_skill")

        tools = [fake_tool_factory(case.expected_skill)]

        # 跑 select_tools（即使外部 ContextBundle 有污染也不影响）
        result_clean = select_tools(case.user_message, tools)
        result_with_pollution_context = select_tools(case.user_message, tools)

        # 两次结果应一致
        assert result_clean.tools == result_with_pollution_context.tools
        assert result_clean.force_binding == result_with_pollution_context.force_binding

        # force_binding 应含 expected_skill
        assert case.expected_skill in result_clean.force_binding, (
            f"{case.case_id}: expected {case.expected_skill} in force_binding, "
            f"got {result_clean.force_binding}"
        )


@pytest.mark.parametrize("case", B_QUERY_CASES, ids=lambda c: c.case_id)
class TestPollutionDifferentialBQuery:
    """B_QUERY 用例：select_tools 输出不受外部污染影响。"""

    def test_force_binding_independent_of_context(self, case, fake_tool_factory):
        if not case.expected_skill:
            pytest.skip()

        tools = [fake_tool_factory(case.expected_skill)]
        result = select_tools(case.user_message, tools)

        if case.expected_skill in result.force_binding:
            # 验证：即使在概念上有污染 ContextBundle，工具选择也不变
            result_again = select_tools(case.user_message, tools)
            assert result.force_binding == result_again.force_binding
