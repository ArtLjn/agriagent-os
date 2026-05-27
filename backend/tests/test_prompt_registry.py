"""PromptRegistry 测试。"""

from datetime import date

import pytest

from app.agent.prompt_renderer import render_prompt


def test_system_base_prompt_contains_tool_calling_rule():
    """system_base 模板包含工具调用硬约束规则。"""
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
    base_j2 = prompts_dir / "base.j2"
    if base_j2.exists():
        content = base_j2.read_text()
        assert "禁止凭记忆回答" in content
        assert "必须先调用对应工具" in content


class TestUserContextInPrompt:
    """用户上下文（farm_location / display_name / current_season）注入测试。"""

    @pytest.fixture()
    def _registry_with_base(self):
        """从 prompts/ 目录加载 base.j2 的 registry，同时注册 system_base 别名。"""
        from pathlib import Path

        from app.agent.prompt_registry import PromptRegistry

        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        reg = PromptRegistry()
        reg.reload(prompts_dir)
        # config.yaml 中 templates key 是 base，但应用代码通过 system_base 调用
        # 这里同步注册 system_base 别名，与 app 启动时的行为一致
        base_content = reg.get("base")
        reg.register("system_base", "1.0", base_content)
        return reg

    def test_base_j2_contains_user_context_section(self):
        """base.j2 模板文件包含 user_context 区块。"""
        from pathlib import Path

        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        content = (prompts_dir / "base.j2").read_text()
        assert "user_context" in content

    def test_prompt_renders_with_farm_location(self, _registry_with_base):
        """模板渲染后包含 farm_location / display_name / current_season。"""
        result = render_prompt(
            "system_base",
            variables={
                "farm_context_summary": "",
                "display_name": "张三",
                "farm_location": "云南昆明",
                "current_season": "夏季",
            },
            registry=_registry_with_base,
        )
        assert "云南昆明" in result
        assert "张三" in result
        assert "夏季" in result

    def test_prompt_skips_location_when_empty(self, _registry_with_base):
        """farm_location 为空时不输出 <location> 标签。"""
        result = render_prompt(
            "system_base",
            variables={
                "farm_context_summary": "",
                "display_name": "张三",
                "farm_location": "",
                "current_season": "夏季",
            },
            registry=_registry_with_base,
        )
        assert "<location>" not in result

    def test_prompt_skips_entire_section_when_no_location_and_no_season(
        self, _registry_with_base
    ):
        """farm_location 和 current_season 都为空时不输出用户信息区块。"""
        result = render_prompt(
            "system_base",
            variables={
                "farm_context_summary": "",
                "display_name": "张三",
                "farm_location": "",
                "current_season": "",
            },
            registry=_registry_with_base,
        )
        assert "user_context" not in result

    def test_prompt_renders_season_only(self, _registry_with_base):
        """仅有 current_season 时也输出用户信息区块。"""
        result = render_prompt(
            "system_base",
            variables={
                "farm_context_summary": "",
                "display_name": "李四",
                "farm_location": "",
                "current_season": "春季",
            },
            registry=_registry_with_base,
        )
        assert "春季" in result
        assert "李四" in result
        assert "<location>" not in result


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
        from app.agent.graph import _get_season

        assert _get_season(test_date) == expected

    def test_season_default_uses_today(self):
        from app.agent.graph import _get_season

        result = _get_season()
        assert result in ("春季", "夏季", "秋季", "冬季")
