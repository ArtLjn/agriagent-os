"""PromptComposer 测试。"""

from datetime import date
from pathlib import Path

import pytest

from app.agent.prompt_composer import PromptComposer
from app.agent.prompt_registry import PromptRegistry

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@pytest.fixture()
def _composer():
    """从 prompts/ 目录初始化的 PromptComposer。"""
    reg = PromptRegistry()
    reg.reload(_PROMPTS_DIR)
    return PromptComposer(reg, _PROMPTS_DIR)


class TestComposerLoadSnippets:
    """Snippet 加载测试。"""

    def test_loads_all_p1_to_p4_snippets(self, _composer):
        """Composer 加载 snippets/ 目录下所有 snippet。"""
        names = _composer.list_snippets()
        assert "p1-language" in names
        assert "p1-tool-guardrails" in names
        assert "p2-role" in names
        assert "p4-context" in names

    def test_snippet_file_not_found_logs_warning(self):
        """snippets/ 目录不存在时不崩溃，记录警告。"""
        reg = PromptRegistry()
        composer = PromptComposer(reg, Path("/nonexistent"))
        assert composer.list_snippets() == []


class TestComposerCompose:
    """场景组合测试。"""

    def test_system_base_compose(self, _composer):
        """system_base 场景组合包含所有必要段。"""
        result = _composer.compose(
            "system_base",
            variables={
                "display_name": "老李",
                "farm_location": "苏州",
                "current_season": "夏季",
            },
            current_date=date(2026, 5, 29),
        )
        assert "【语言规则】" in result
        assert "【安全护栏】" in result
        assert "【角色定义】" in result
        assert "芽芽" in result
        assert "轻松闲聊" in result
        assert "老李" in result
        assert "苏州" in result
        assert "2026-05-29" in result

    def test_system_base_contains_tool_guidance(self, _composer):
        """system_base 组合结果包含工具引导，且不含旧上下文变量。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "农友"},
            current_date=date(2026, 5, 29),
        )
        assert "get_farm_status" in result
        assert "get_weather_forecast" in result
        assert "farm_context_summary" not in result

    def test_system_base_contains_current_labor_skill_capabilities(self, _composer):
        """system_base 能力范围包含当前已接入的用工 Skill。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "农友"},
            current_date=date(2026, 5, 29),
        )

        assert "get_workers" in result
        assert "manage_workers" in result
        assert "manage_wages" in result
        assert "settle_labor_payment" in result
        assert "作业单" in result

    def test_cost_parse_compose(self, _composer):
        """cost_parse 场景组合：snippet + template。"""
        result = _composer.compose(
            "cost_parse",
            variables={"description": "人工费300"},
            current_date=date(2026, 5, 29),
        )
        assert "【语言规则】" in result
        assert "人工费300" in result
        assert "record_type" in result

    def test_cost_parse_no_duplicate_language_rules(self, _composer):
        """cost_parse 组合结果中语言规则只出现一次（去重）。"""
        result = _composer.compose(
            "cost_parse",
            variables={"description": "测试"},
            current_date=date(2026, 5, 29),
        )
        assert result.count("【语言规则】") == 1

    def test_unknown_scene_raises(self, _composer):
        """未配置的场景抛出 KeyError。"""
        with pytest.raises(KeyError, match="nonexistent"):
            _composer.compose("nonexistent")


class TestPriorityStack:
    """Priority Stack 排序测试。"""

    def test_p1_before_p3(self, _composer):
        """P1 Safety 段在 P3 Format 段之前。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "农友"},
            current_date=date(2026, 5, 29),
        )
        p1_pos = result.index("【语言规则】")
        p3_pos = result.index("【回复格式】")
        assert p1_pos < p3_pos

    def test_p2_before_p4(self, _composer):
        """P2 Accuracy 段在 P4 Context 段之前。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "农友", "farm_location": "苏州"},
            current_date=date(2026, 5, 29),
        )
        p2_pos = result.index("【角色定义】")
        p4_pos = result.index("【时间信息】")
        assert p2_pos < p4_pos
