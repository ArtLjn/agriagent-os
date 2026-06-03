"""上下文工程集成验证测试。

验证三步改造的整体效果：
1. get_farm_status Skill 被 skillify 自动发现
2. system_base 由 Composer snippets 组合渲染，不含 farm_context_summary
3. TOOL_CHAIN_MAP + expand_by_chain 正确扩展工具链
4. sliding_window_compact 函数存在且可调用
"""

from datetime import date
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@pytest.fixture()
def _composer():
    """从 prompts/ 目录初始化的 PromptComposer。"""
    from app.agent.prompt_composer import PromptComposer
    from app.agent.prompt_registry import PromptRegistry

    reg = PromptRegistry()
    reg.reload(_PROMPTS_DIR)
    return PromptComposer(reg, _PROMPTS_DIR)


class TestSkillRegistration:
    """验证 get_farm_status Skill 注册。"""

    def test_get_farm_status_skill_registered(self):
        """get_farm_status Skill 被 skillify 自动发现。"""
        from app.agent.skills import get_skill_manager

        manager = get_skill_manager()
        names = [s.name for s in manager.list_skills()]
        assert "get_farm_status" in names

    def test_get_farm_status_has_no_required_params(self):
        """get_farm_status Skill 无必填参数。"""
        import importlib

        _mod = importlib.import_module("app.agent.skills.farm-status.scripts.main")
        skill = _mod.FarmStatusSkill()
        schema = skill.parameters_schema()
        assert schema.get("required") == []


class TestBasePromptNoFarmContext:
    """验证 Composer 组合的 system prompt 不再嵌入 farm_context_summary。"""

    def test_base_prompt_no_farm_context_variable(self, _composer):
        """Composer 组合后不包含 farm_context_summary 占位文本。"""
        text = _composer.compose(
            "system_base",
            variables={
                "display_name": "农友",
                "farm_location": "苏州",
                "current_season": "夏季",
            },
            current_date=date(2026, 5, 29),
        )
        assert "farm_context_summary" not in text

    def test_base_prompt_contains_tool_routing(self, _composer):
        """Composer 组合结果包含工具路由引导，且不含旧 farm_context_summary。"""
        text = _composer.compose(
            "system_base",
            variables={
                "display_name": "农友",
                "farm_location": "苏州",
                "current_season": "夏季",
            },
            current_date=date(2026, 5, 29),
        )
        assert "get_farm_status" in text
        assert "get_weather_forecast" in text
        assert "farm_context_summary" not in text

    def test_base_prompt_renders_with_minimal_vars(self, _composer):
        """Composer 组合结果仅用最少变量即可正常渲染。"""
        text = _composer.compose(
            "system_base",
            variables={"display_name": "农友"},
            current_date=date(2026, 5, 29),
        )
        assert len(text) > 100
        assert "农友" in text


class TestSlidingWindowCompact:
    """验证 sliding_window_compact 函数。"""

    def test_function_exists(self):
        """sliding_window_compact 可以导入。"""
        from app.agent.graph import sliding_window_compact

        assert callable(sliding_window_compact)

    def test_short_history_unchanged(self):
        """短对话不做压缩。"""
        from app.agent.graph import sliding_window_compact

        msgs = [
            HumanMessage(content="问题1"),
            AIMessage(content="回答1"),
            HumanMessage(content="问题2"),
            AIMessage(content="回答2"),
        ]
        result = sliding_window_compact(msgs, keep_rounds=5)
        assert len(result) == len(msgs)

    def test_long_history_compressed(self):
        """超过 keep_rounds 的对话压缩旧 ToolMessage。"""
        from app.agent.graph import sliding_window_compact

        # 构建 6 轮完整对话，超过 keep_rounds=3
        expanded = []
        for i in range(6):
            expanded.append(HumanMessage(content=f"第{i + 1}轮问题"))
            expanded.append(
                AIMessage(
                    content="",
                    tool_calls=[{"name": f"tool_{i}", "args": {}, "id": f"tc{i}"}],
                )
            )
            expanded.append(
                ToolMessage(
                    content=f"工具返回结果第{i + 1}轮，包含很长的数据内容" * 10,
                    tool_call_id=f"tc{i}",
                )
            )
            expanded.append(AIMessage(content=f"第{i + 1}轮回答"))

        result = sliding_window_compact(expanded, keep_rounds=3)
        assert len(result) == len(expanded)
        # 旧 ToolMessage 应被截断
        old_tool_msgs = [m for m in result[:12] if isinstance(m, ToolMessage)]
        for m in old_tool_msgs:
            assert len(m.content) < 50


class TestToolChainExpansion:
    """验证 TOOL_CHAIN_MAP + expand_by_chain。"""

    def test_map_is_dict(self):
        from app.agent.tool_selector import TOOL_CHAIN_MAP

        assert isinstance(TOOL_CHAIN_MAP, dict)

    def test_weather_expands_to_farm_status(self):
        """get_weather_forecast 链式扩展包含 get_farm_status。"""
        from app.agent.tool_selector import expand_by_chain

        result = expand_by_chain({"get_weather_forecast"})
        assert "get_farm_status" in result
        assert "get_weather_forecast" in result

    def test_cost_summary_expands_to_farm_status(self):
        """get_cost_summary 链式扩展包含 get_farm_status。"""
        from app.agent.tool_selector import expand_by_chain

        result = expand_by_chain({"get_cost_summary"})
        assert "get_farm_status" in result

    def test_write_skills_no_chain(self):
        """写操作 Skill 不会被扩展。"""
        from app.agent.tool_selector import expand_by_chain

        write_tools = [
            "create_cost_record",
            "create_crop_cycle",
            "log_farm_activity",
            "update_crop_stage",
            "settle_debt",
        ]
        for tool in write_tools:
            result = expand_by_chain({tool})
            assert result == {tool}, f"{tool} 不应有工具链扩展"

    def test_get_farm_status_no_chain(self):
        """get_farm_status 自身无链式扩展。"""
        from app.agent.tool_selector import expand_by_chain

        result = expand_by_chain({"get_farm_status"})
        assert result == {"get_farm_status"}

    def test_empty_input(self):
        """空输入返回空集合。"""
        from app.agent.tool_selector import expand_by_chain

        result = expand_by_chain(set())
        assert result == set()

    def test_original_tools_preserved(self):
        """扩展后保留所有原始工具。"""
        from app.agent.tool_selector import expand_by_chain

        original = {"get_weather_forecast", "get_cost_summary"}
        result = expand_by_chain(original)
        for tool in original:
            assert tool in result


class TestCrossCuttingIntegration:
    """跨模块集成验证：三个改造点协同工作。"""

    def test_all_query_tools_have_farm_status_access(self):
        """所有查询类工具都有途径获取农场状态。"""
        from app.agent.tool_selector import TOOL_CHAIN_MAP, expand_by_chain

        query_tools = [
            "get_weather_forecast",
            "get_cost_summary",
            "get_cost_analytics",
            "get_crop_cycle_info",
            "get_recent_farm_logs",
        ]
        for tool in query_tools:
            # 通过 TOOL_CHAIN_MAP 直接关联
            assert "get_farm_status" in TOOL_CHAIN_MAP.get(tool, []), (
                f"{tool} 应通过 TOOL_CHAIN_MAP 关联 get_farm_status"
            )
            # 通过 expand_by_chain 扩展
            expanded = expand_by_chain({tool})
            assert "get_farm_status" in expanded

    def test_tool_chain_handles_farm_status_routing(self, _composer):
        """get_farm_status 路由由 TOOL_CHAIN_MAP 自动处理，prompt 保留工具引导。"""
        from app.agent.tool_selector import expand_by_chain

        text = _composer.compose(
            "system_base",
            variables={"display_name": "农友"},
            current_date=date(2026, 5, 29),
        )
        # prompt 保留工具引导，但不再使用旧 farm_context_summary。
        assert "get_farm_status" in text
        assert "farm_context_summary" not in text
        # TOOL_CHAIN_MAP 确保查询工具能获取农场状态
        for tool in ["get_weather_forecast", "get_cost_summary", "get_crop_cycle_info"]:
            expanded = expand_by_chain({tool})
            assert "get_farm_status" in expanded

    def test_sliding_window_preserves_recent_context(self):
        """sliding_window_compact 保留最近 N 轮完整上下文。"""
        from app.agent.graph import sliding_window_compact

        # 构建 4 轮对话，保留 2 轮
        msgs = []
        for i in range(4):
            msgs.append(HumanMessage(content=f"Q{i}"))
            msgs.append(
                AIMessage(
                    content="",
                    tool_calls=[{"name": f"tool_{i}", "args": {}, "id": f"tc{i}"}],
                )
            )
            msgs.append(
                ToolMessage(
                    content=f"详细结果数据{i}" * 20,
                    tool_call_id=f"tc{i}",
                )
            )
            msgs.append(AIMessage(content=f"A{i}"))

        result = sliding_window_compact(msgs, keep_rounds=2)
        # 最近 2 轮的 ToolMessage 应保留完整内容
        recent_tool_msgs = [m for m in result[-8:] if isinstance(m, ToolMessage)]
        for m in recent_tool_msgs:
            assert "详细结果数据" in m.content
