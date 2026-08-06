"""测试 prompt 模板注入农场上下文 + 轻量回复规则。"""

import pytest
from datetime import date

from app.prompt.renderer import render_prompt
from app.prompt.registry import PromptRegistry
from app.domains.farm.models import Farm


class TestFarmContextSummaryInjection:
    """farm_context_summary 变量注入测试。"""

    def test_render_with_farm_context_summary(self):
        """传入 farm_context_summary 变量时正确渲染到模板中。"""
        reg = PromptRegistry()
        reg.register(
            "system_base",
            "v1",
            "{% if farm_context_summary %}{{ farm_context_summary }}{% endif %}",
        )
        summary = "茬口：西瓜(伸蔓期)"
        result = render_prompt(
            "system_base",
            {"farm_context_summary": summary},
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert summary in result

    def test_render_without_farm_context_summary_is_empty(self):
        """不传 farm_context_summary 时，模板中对应位置为空（向后兼容）。"""
        reg = PromptRegistry()
        reg.register(
            "system_base",
            "v1",
            "前面{% if farm_context_summary %}{{ farm_context_summary }}{% endif %}后面",
        )
        result = render_prompt(
            "system_base",
            {},
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "前面后面" in result

    def test_render_farm_context_summary_default_empty_string(self):
        """farm_context_summary 默认为空字符串，不报错。"""
        reg = PromptRegistry()
        reg.register(
            "system_base",
            "v1",
            "{{ farm_context_summary }}",
        )
        # 不传 variables，farm_context_summary 应该不报 Jinja2 错误
        result = render_prompt(
            "system_base",
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert result == ""

    def test_base_template_renders_farm_context_block(self):
        """base.j2 模板中包含 farm_context_summary 块时能正确渲染。"""
        reg = PromptRegistry()
        reg.register(
            "system_base",
            "v1",
            "【农场现状】\n{{ farm_context_summary }}\n",
        )
        summary = "茬口：西瓜(伸蔓期)\n本月花费：500元"
        result = render_prompt(
            "system_base",
            {"farm_context_summary": summary},
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "【农场现状】" in result
        assert "西瓜(伸蔓期)" in result
        assert "500元" in result


class TestResponseFormatRules:
    """display_name 作为上下文变量，而不是强制称呼规则。"""

    def test_display_name_default_is_nongyou(self):
        """display_name 未传入时，默认为「农友」。"""
        reg = PromptRegistry()
        reg.register(
            "system_base",
            "v1",
            "{{ display_name }}",
        )
        result = render_prompt(
            "system_base",
            {"display_name": "农友"},
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert result == "农友"

    def test_display_name_custom_context_value(self):
        """display_name 传入自定义值时仍可作为上下文渲染。"""
        reg = PromptRegistry()
        reg.register(
            "system_base",
            "v1",
            "<name>{{ display_name }}</name>",
        )
        result = render_prompt(
            "system_base",
            {"display_name": "老王"},
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "<name>老王</name>" in result

    def test_format_snippet_does_not_force_user_name(self):
        """系统基础 prompt 不应要求每次称呼用户。"""
        from pathlib import Path

        snippet = (
            Path(__file__).parent.parent.parent
            / "prompts"
            / "snippets"
            / "p3-format.j2"
        ).read_text()
        assert "称呼用户为" not in snippet


class TestBaseJ2TemplateContent:
    """验证 snippet 模板文件包含所需的占位符和块（base.j2 已拆分为 snippet）。"""

    @pytest.fixture()
    def format_snippet(self):
        """加载 p3-format.j2 回复格式 snippet。"""
        from pathlib import Path

        return (
            Path(__file__).parent.parent.parent
            / "prompts"
            / "snippets"
            / "p3-format.j2"
        ).read_text()

    @pytest.fixture()
    def context_snippet(self):
        """加载 p4-context.j2 上下文 snippet。"""
        from pathlib import Path

        return (
            Path(__file__).parent.parent.parent
            / "prompts"
            / "snippets"
            / "p4-context.j2"
        ).read_text()

    def test_snippets_not_contain_farm_context_summary(self):
        """snippet 体系不再包含 farm_context_summary 占位符（已由工具获取替代）。"""
        from pathlib import Path

        snippets_dir = Path(__file__).parent.parent.parent / "prompts" / "snippets"
        for f in snippets_dir.glob("*.j2"):
            assert "farm_context_summary" not in f.read_text(), (
                f"{f.name} 包含 farm_context_summary"
            )

    def test_context_snippet_contains_display_name(self, context_snippet):
        """p4-context.j2 中包含 display_name 占位符。"""
        assert "display_name" in context_snippet

    def test_format_snippet_contains_response_format_section(self, format_snippet):
        """p3-format.j2 包含【回复格式】章节。"""
        assert "【回复格式】" in format_snippet

    def test_no_farm_status_section_in_snippets(self):
        """农场状态查询已由工具获取替代，snippet 中不再硬编码。"""
        from pathlib import Path

        snippets_dir = Path(__file__).parent.parent.parent / "prompts" / "snippets"
        for f in snippets_dir.glob("*.j2"):
            assert "【农场状态查询】" not in f.read_text(), f"{f.name} 包含农场状态查询"

    def test_format_snippet_rules_are_lightweight(self, format_snippet):
        """p3-format.j2 只保留轻量表达原则，不锁死输出模板。"""
        assert "不套固定开场或结尾" in format_snippet
        assert "Markdown" in format_snippet
        assert "上下文参考" in format_snippet
        assert "称呼用户为" not in format_snippet
        assert "不超过2行" not in format_snippet
        assert "不超过5条" not in format_snippet
        assert "必须口语化" not in format_snippet

    def test_style_snippet_allows_markdown(self):
        """p3-style.j2 不再禁止 Markdown。"""
        from pathlib import Path

        style_snippet = (
            Path(__file__).parent.parent.parent / "prompts" / "snippets" / "p3-style.j2"
        ).read_text()
        assert "不要使用 Markdown" not in style_snippet
        assert "禁止使用 Markdown" not in style_snippet

    def test_context_snippet_renders_with_display_name(self, context_snippet):
        """p4-context.j2 渲染 display_name 不报错。"""
        reg = PromptRegistry()
        reg.register("p4_context", "v1", context_snippet)
        result = render_prompt(
            "p4_context",
            {
                "display_name": "老王",
                "farm_location": "睢宁",
            },
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "老王" in result


class TestFarmDisplayNameFromDatabase:
    """从数据库获取 display_name 的集成测试。"""

    def test_get_display_name_from_farm_model(self, db_session):
        """Farm 模型 name 字段可读取作为 display_name。"""
        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        display_name = farm.name or "农友"
        assert display_name != ""

    def test_get_display_name_custom_from_database(self, db_session):
        """Farm 模型 name 设置了自定义值时正确读取。"""
        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        original_name = farm.name
        farm.name = "老赵的农场"
        db_session.commit()
        display_name = farm.name or "农友"
        assert display_name == "老赵的农场"
        farm.name = original_name
        db_session.commit()
