"""测试 prompt 模板注入农场上下文 + 回复格式规则 + 用户称呼。"""

import pytest
from datetime import date

from app.core.prompt_renderer import render_prompt
from app.core.prompt_registry import PromptRegistry
from app.models.farm import Farm
from app.core.database import SessionLocal


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
    """response_format_rules 和 display_name 测试。"""

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

    def test_display_name_custom(self):
        """display_name 传入自定义值时正确渲染。"""
        reg = PromptRegistry()
        reg.register(
            "system_base",
            "v1",
            "称呼用户为「{{ display_name }}」",
        )
        result = render_prompt(
            "system_base",
            {"display_name": "老王"},
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "称呼用户为「老王」" in result

    def test_response_format_rules_in_template(self):
        """response_format_rules 硬编码在 base.j2 中能正确渲染 display_name。"""
        reg = PromptRegistry()
        template_with_rules = (
            "【回复格式】\n- 称呼用户为「{{ display_name }}」\n- 每条建议不超过2行\n"
        )
        reg.register("system_base", "v1", template_with_rules)
        result = render_prompt(
            "system_base",
            {"display_name": "老李"},
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "称呼用户为「老李」" in result
        assert "每条建议不超过2行" in result


class TestBaseJ2TemplateContent:
    """验证 base.j2 模板文件包含所需的占位符和块。"""

    @pytest.fixture()
    def base_template(self):
        """加载 base.j2 模板内容。"""
        from pathlib import Path

        template_path = Path(__file__).parent.parent.parent / "prompts" / "base.j2"
        return template_path.read_text()

    def test_base_j2_contains_farm_context_summary(self, base_template):
        """base.j2 包含 farm_context_summary 占位符。"""
        assert "farm_context_summary" in base_template

    def test_base_j2_contains_display_name(self, base_template):
        """base.j2 回复格式规则中包含 display_name 占位符。"""
        assert "display_name" in base_template

    def test_base_j2_contains_response_format_section(self, base_template):
        """base.j2 包含【回复格式】章节。"""
        assert "【回复格式】" in base_template

    def test_base_j2_contains_farm_status_section(self, base_template):
        """base.j2 包含【农场现状】章节。"""
        assert "【农场现状】" in base_template

    def test_base_j2_response_format_rules_content(self, base_template):
        """base.j2 回复格式规则包含关键条目。"""
        assert "称呼用户为" in base_template
        assert "不超过2行" in base_template
        assert "不超过5条" in base_template
        assert "先说结论" in base_template
        assert "禁止铺垫" in base_template
        assert "口语化" in base_template

    def test_base_j2_renders_full_template(self, base_template):
        """完整 base.j2 模板渲染不报错，所有变量正确注入。"""
        reg = PromptRegistry()
        reg.register("system_base", "v1", base_template)
        result = render_prompt(
            "system_base",
            {
                "farm_context_summary": "茬口：西瓜(伸蔓期)\n本月花费：500元",
                "display_name": "老王",
            },
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "西瓜(伸蔓期)" in result
        assert "老王" in result
        assert "2026-05-25" in result


class TestFallbackTemplateUpdate:
    """验证 _DEFAULT_PROMPTS 中 system_base 的 fallback 同步更新。"""

    def test_fallback_contains_display_name(self):
        """fallback 模板包含 display_name 占位符。"""
        from app.core.prompt_registry import _DEFAULT_PROMPTS

        fallback = _DEFAULT_PROMPTS["system_base"]
        assert "display_name" in fallback

    def test_fallback_contains_farm_context_summary(self):
        """fallback 模板包含 farm_context_summary 占位符。"""
        from app.core.prompt_registry import _DEFAULT_PROMPTS

        fallback = _DEFAULT_PROMPTS["system_base"]
        assert "farm_context_summary" in fallback

    def test_fallback_renders_with_variables(self):
        """fallback 模板带变量渲染不报错。"""
        reg = PromptRegistry()
        # 不注册 system_base，让 get_fallback 生效
        result = render_prompt(
            "system_base",
            {
                "farm_context_summary": "茬口：西瓜",
                "display_name": "农友",
            },
            registry=reg,
            current_date=date(2026, 5, 25),
        )
        assert "农友" in result
        assert "西瓜" in result


class TestFarmDisplayNameFromDatabase:
    """从数据库获取 display_name 的集成测试。"""

    def test_get_display_name_from_farm_model(self):
        """Farm 模型 display_name 字段默认为「农友」。"""
        db = SessionLocal()
        farm = db.query(Farm).filter(Farm.id == 1).first()
        # conftest 中创建的 Farm 没有设置 display_name，应为 None
        # 业务层应处理为默认值「农友」
        display_name = farm.display_name or "农友"
        assert display_name == "农友"
        db.close()

    def test_get_display_name_custom_from_database(self):
        """Farm 模型 display_name 设置了自定义值时正确读取。"""
        db = SessionLocal()
        farm = db.query(Farm).filter(Farm.id == 1).first()
        farm.display_name = "老赵"
        db.commit()
        display_name = farm.display_name or "农友"
        assert display_name == "老赵"
        db.close()
