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

    def test_select_tools_is_deterministic_for_query_intent(self, case, fake_tool_factory):
        """select_tools 对 query intent 应是确定性的（不依赖外部 ContextBundle）。

        select_tools 只看 user_message，不读外部 ContextBundle，
        因此理论上"有污染 ContextBundle"与"无污染 ContextBundle"结果一致。
        本测试不构造污染上下文（select_tools 根本不消费 ContextBundle），
        而是通过两次确定性调用验证：相同输入产出相同 force_binding 与 tools，
        且都包含 expected_skill。

        注：这是一个确定性测试（deterministic），不是真正的"污染对照"测试。
        真正的污染对照需在更高层（trace / end-to-end）跑，见 Layer 2 trace 测试。
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
    """B_QUERY 用例：select_tools 输出不受外部污染影响。

    强断言：所有 B_QUERY 用例必须 force_bind expected_skill（与 Task 8 baseline 一致）。
    如果 force_binding 未触发，明确 fail（不 silent pass）。

    注：当前有 8 个 baseline 失败用例（q-weather-3, q-cycle-2, q-cycle-4, q-workers-4,
    q-payables-4, q-debt-2, q-debt-3, q-debt-4），原因是 QUERY_INTENT_FORCE_BINDING
    字典未覆盖这些同义表达；将在 Task 11 修复字典覆盖度。
    """

    def test_force_binding_independent_of_context(self, case, fake_tool_factory):
        if not case.expected_skill:
            pytest.skip(f"{case.case_id}: no expected_skill")

        tools = [fake_tool_factory(case.expected_skill)]
        result = select_tools(case.user_message, tools)

        # 强断言：expected_skill 必须在 force_binding（与 Task 8 baseline 一致）
        assert case.expected_skill in result.force_binding, (
            f"{case.case_id}: expected {case.expected_skill} in force_binding, "
            f"got force_binding={result.force_binding}. "
            f"This case is a known baseline failure (QUERY_INTENT_FORCE_BINDING "
            f"dictionary gap); will be fixed in Task 11."
        )

        # 确定性验证：跑两次结果一致（select_tools 不依赖外部 ContextBundle）
        result_again = select_tools(case.user_message, tools)
        assert result.force_binding == result_again.force_binding
        assert result.tools == result_again.tools
