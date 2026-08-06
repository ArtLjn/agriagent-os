"""Tests for PromptRegistry."""

from pathlib import Path

import pytest

from app.prompt.registry import PromptRegistry


class TestPromptRegistry:
    def test_register_and_get(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "hello {{ name }}")
        assert reg.get("test", "v1") == "hello {{ name }}"

    def test_get_default_version(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "hello")
        assert reg.get("test") == "hello"

    def test_get_missing_raises(self):
        reg = PromptRegistry()
        with pytest.raises(KeyError):
            reg.get("missing")

    def test_switch_version(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "hello v1")
        reg.register("test", "v2", "hello v2")
        assert reg.get("test") == "hello v1"
        reg.switch_version("test", "v2")
        assert reg.get("test") == "hello v2"

    def test_list_versions(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "a")
        reg.register("test", "v2", "b")
        assert reg.list_versions("test") == ["v1", "v2"]

    def test_reload_clears_and_reloads(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "old")
        reg.reload()
        with pytest.raises(KeyError):
            reg.get("test")

    def test_reload_registers_memory_running_summary_prompt(self):
        prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
        reg = PromptRegistry()

        reg.reload(prompts_dir)

        content = reg.get("memory.running_summary")
        assert "当前摘要" in content
        assert "追加段落" in content

    def test_get_fallback_removed(self):
        """get_fallback 方法已被删除。"""
        reg = PromptRegistry()
        assert not hasattr(reg, "get_fallback")
