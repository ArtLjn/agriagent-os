"""多轮污染测试（Layer 2：多轮 + Trace 层）。

验证第 N 轮（N>=2）查询选择保持确定性，不依赖首轮污染。
同时验证 trace 层能区分数据来源（tool:xxx vs context_bundle）。

设计意图（13_Agent范式规范化设计.md §5.9.5）：
- 多轮场景下，前几轮的污染上下文不应影响第 N 轮工具选择契约
- trace 的 data_source 字段必须能反映数据真实来源
- 当 LLM 调用了 Skill，data_source 必须是 tool:xxx
"""

import pytest

from app.agent.router.tool_selector import select_tools
from tests.agent.eval.cases import E2_MULTITURN_CASES


@pytest.mark.parametrize("case", E2_MULTITURN_CASES, ids=lambda c: c.case_id)
class TestMultiturnPollution:
    """E2 用例：第 N 轮查询仍保持确定性。"""

    def test_nth_turn_does_not_force_bind_query(self, case, fake_tool_factory):
        """第 N 轮查询不再通过规则强制绑定工具。"""
        if not case.expected_skill:
            pytest.skip()

        # 第 N 轮的工具选择 — 即使 previous_turns 里有污染上下文
        # select_tools 不看历史，只看当前 user_message
        tools = [fake_tool_factory(case.expected_skill)]
        result = select_tools(case.user_message, tools)

        assert not result.force_binding
        assert result.tools == select_tools(case.user_message, tools).tools

    def test_tool_call_data_source_can_reach_trace(self, case, fake_tool_factory):
        """工具调用结果能传递到 trace 层（验证可观测性）。"""
        from app.agent.runtime.node_helpers import _build_data_source_payload

        tools = [fake_tool_factory(case.expected_skill)] if case.expected_skill else []
        if not tools:
            pytest.skip()

        # 模拟 Skill 被调用后的 trace payload
        payload = _build_data_source_payload(tool_calls=[{"name": case.expected_skill}])
        assert payload["data_source"] == f"tool:{case.expected_skill}"
        assert payload["has_tool_results"] is True

    def test_pollution_does_not_affect_data_source(self, case):
        """当 LLM 调用了 Skill（trace 显示 tool:xxx），不应被 ContextBundle 污染。

        构造对照：
        - 有 tool_calls → data_source=tool:xxx（数据来自 Skill）
        - 无 tool_calls → data_source=context_bundle（数据可能来自 ContextBundle）

        两个 payload 的 data_source 互斥，说明 trace 能区分数据来源，
        下游可以基于此字段判断回复是否被 ContextBundle 污染。
        """
        if not case.expected_skill:
            pytest.skip()

        from app.agent.runtime.node_helpers import _build_data_source_payload

        # 模拟：LLM 调用了 Skill
        payload_with_tool = _build_data_source_payload(
            tool_calls=[{"name": case.expected_skill}]
        )
        # data_source 必须是 tool:xxx（说明数据来自 Skill）
        assert payload_with_tool["data_source"] == f"tool:{case.expected_skill}"

        # 模拟：LLM 没调用 Skill（数据可能来自 ContextBundle）
        payload_without_tool = _build_data_source_payload(tool_calls=None)
        assert payload_without_tool["data_source"] == "context_bundle"

        # 这两个 payload 互斥，说明 trace 能区分数据来源
        assert payload_with_tool["data_source"] != payload_without_tool["data_source"]
