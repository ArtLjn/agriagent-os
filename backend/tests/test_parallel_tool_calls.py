"""并行 tool calling 配置与 bind_tools 行为测试。"""

from app.core.config import AIConfig


class TestAIConfigParallel:
    """AIConfig.parallel_tool_calls 默认值与配置。"""

    def test_default_is_true(self):
        config = AIConfig()
        assert config.parallel_tool_calls is True

    def test_can_set_false(self):
        config = AIConfig(parallel_tool_calls=False)
        assert config.parallel_tool_calls is False
