"""PromptRegistry 测试。"""

from datetime import date

import pytest


def test_system_base_prompt_contains_tool_calling_rule():
    """p1-tool-guardrails snippet 包含工具调用硬约束规则。"""
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
    snippet = prompts_dir / "snippets" / "p1-tool-guardrails.j2"
    if snippet.exists():
        content = snippet.read_text()
        assert "实时数据必须先调用工具" in content
        assert "写操作必须通过工具完成" in content


def test_system_base_prompt_guides_planting_planning_dialogue():
    """种植意向应先规划和澄清，不把裸意向当作写入完成。"""
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
    snippet = prompts_dir / "snippets" / "p1-tool-guardrails.j2"
    content = snippet.read_text()

    assert "用户只是表达种植意向" in content
    assert "不要直接创建茬口或模板" in content
    assert "没有调用作物模板工具" in content
    assert "不要说已找到或未找到模板" in content


class TestUserContextInPrompt:
    """用户上下文（farm_location / display_name / current_season）注入测试。"""

    @pytest.fixture()
    def _composer(self):
        """从 prompts/ 目录初始化的 PromptComposer。"""
        from pathlib import Path

        from app.prompt.composer import PromptComposer
        from app.prompt.registry import PromptRegistry

        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        reg = PromptRegistry()
        reg.reload(prompts_dir)
        return PromptComposer(reg, prompts_dir)

    def test_base_j2_contains_user_context_section(self):
        """p4-context snippet 包含 user_context 区块。"""
        from pathlib import Path

        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        content = (prompts_dir / "snippets" / "p4-context.j2").read_text()
        assert "user_context" in content

    def test_compose_renders_with_farm_location(self, _composer):
        """system_base 组合后包含 farm_location / display_name / current_season。"""
        result = _composer.compose(
            "system_base",
            variables={
                "display_name": "张三",
                "farm_location": "云南昆明",
                "current_season": "夏季",
            },
            current_date=date(2026, 5, 29),
        )
        assert "云南昆明" in result
        assert "张三" in result
        assert "夏季" in result

    def test_compose_skips_location_when_empty(self, _composer):
        """farm_location 为空时不输出 <location> 标签。"""
        result = _composer.compose(
            "system_base",
            variables={
                "display_name": "张三",
                "farm_location": "",
                "current_season": "夏季",
            },
            current_date=date(2026, 5, 29),
        )
        assert "<location>" not in result

    def test_compose_skips_entire_section_when_no_location_and_no_season(
        self, _composer
    ):
        """farm_location 和 current_season 都为空时不输出用户信息区块。"""
        result = _composer.compose(
            "system_base",
            variables={
                "display_name": "张三",
                "farm_location": "",
                "current_season": "",
            },
            current_date=date(2026, 5, 29),
        )
        assert "user_context" not in result

    def test_compose_renders_season_only(self, _composer):
        """仅有 current_season 时也输出用户信息区块。"""
        result = _composer.compose(
            "system_base",
            variables={
                "display_name": "李四",
                "farm_location": "",
                "current_season": "春季",
            },
            current_date=date(2026, 5, 29),
        )
        assert "春季" in result
        assert "李四" in result
        assert "<location>" not in result


class TestPromptRegistry:
    """PromptRegistry 核心方法测试。"""

    def test_list_names_returns_registered_templates(self):
        """list_names 返回所有已注册模板名称。"""
        from app.prompt.registry import PromptRegistry

        reg = PromptRegistry()
        reg.register("cost_parse", "1.0", "test content")
        reg.register("report", "1.0", "report content")

        names = reg.list_names()
        assert sorted(names) == ["cost_parse", "report"]

    def test_list_names_returns_empty_when_no_templates(self):
        """list_names 在无模板时返回空列表。"""
        from app.prompt.registry import PromptRegistry

        reg = PromptRegistry()
        assert reg.list_names() == []


class TestGetSeason:
    """_get_season 季节计算函数测试。"""

    @pytest.mark.parametrize(
        "test_date, expected",
        [
            (date(2026, 3, 1), "春季"),
            (date(2026, 4, 15), "春季"),
            (date(2026, 5, 31), "春季"),
            (date(2026, 6, 1), "夏季"),
            (date(2026, 7, 15), "夏季"),
            (date(2026, 8, 31), "夏季"),
            (date(2026, 9, 1), "秋季"),
            (date(2026, 10, 15), "秋季"),
            (date(2026, 11, 30), "秋季"),
            (date(2026, 12, 1), "冬季"),
            (date(2026, 1, 15), "冬季"),
            (date(2026, 2, 28), "冬季"),
        ],
    )
    def test_season_by_month(self, test_date, expected):
        from app.agent.runtime.llm_support import _get_season

        assert _get_season(test_date) == expected

    def test_season_default_uses_today(self):
        from app.agent.runtime.llm_support import _get_season

        result = _get_season()
        assert result in ("春季", "夏季", "秋季", "冬季")
