"""Tests for PromptRegistry."""

import pytest

from app.agent.prompt_registry import PromptRegistry


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

    def test_get_fallback_removed(self):
        """get_fallback 方法已被删除。"""
        reg = PromptRegistry()
        assert not hasattr(reg, "get_fallback")
