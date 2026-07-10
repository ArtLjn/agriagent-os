"""Tests for PromptRenderer."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.prompt.renderer import render_prompt
from app.prompt.registry import PromptRegistry


class TestPromptRenderer:
    def test_render_with_variables(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "Hello {{ name }}, today is {{ current_date }}")
        result = render_prompt(
            "test", {"name": "world"}, registry=reg, current_date=date(2026, 5, 25)
        )
        assert "Hello world, today is 2026-05-25" in result

    def test_render_injects_builtin_variables(self):
        reg = PromptRegistry()
        reg.register(
            "test", "v1", "{{ current_date }} {{ current_time }} {{ current_weekday }}"
        )
        result = render_prompt("test", {}, registry=reg, current_date=date(2026, 5, 25))
        assert "2026-05-25" in result
        assert "星期" in result

    def test_render_raises_on_template_syntax_error(self):
        """模板语法错误时抛出 TemplateError。"""
        from jinja2 import TemplateError

        reg = PromptRegistry()
        reg.register("test", "v1", "bad {{ unclosed")
        with pytest.raises(TemplateError):
            render_prompt("test", {}, registry=reg, current_date=date(2026, 5, 25))

    def test_render_raises_on_unregistered_template(self):
        """模板未注册时抛出 KeyError，不再静默回退。"""
        reg = PromptRegistry()
        with pytest.raises(KeyError, match="system_base"):
            render_prompt(
                "system_base", {}, registry=reg, current_date=date(2026, 5, 25)
            )

    def test_render_relative_dates(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "{{ yesterday }} {{ day_before_yesterday }}")
        result = render_prompt("test", {}, registry=reg, current_date=date(2026, 5, 25))
        assert "2026-05-24" in result
        assert "2026-05-23" in result

    def test_render_defaults_to_beijing_clock(self, monkeypatch):
        fixed_utc = datetime(2026, 6, 8, 16, 30, tzinfo=timezone.utc)

        monkeypatch.setattr(
            "app.prompt.renderer.beijing_now",
            lambda: fixed_utc.astimezone(ZoneInfo("Asia/Shanghai")),
        )
        reg = PromptRegistry()
        reg.register("test", "v1", "{{ current_date }} {{ current_time }}")

        result = render_prompt("test", {}, registry=reg)

        assert "2026-06-09" in result
        assert "00:30" in result
