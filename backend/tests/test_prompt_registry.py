"""PromptRegistry 测试。"""

from app.core.prompt_registry import get_registry


def test_system_base_prompt_contains_tool_calling_rule():
    """内置默认 system_base prompt 包含 tool calling 硬约束。"""
    registry = get_registry()

    # 使用 fallback 获取内置默认
    fallback = registry.get_fallback("system_base")

    assert "禁止凭记忆回答" in fallback
    assert "必须先调用对应工具" in fallback
