"""测试 LLM 加权路由、分级熔断、Provider 健康、enabled 字段。"""

from app.core.llm_client_manager import LLMCircuitState, CircuitEntry


class TestCircuitEntry:
    """测试 CircuitEntry 数据类。"""

    def test_default_state_is_cooling(self):
        entry = CircuitEntry()
        assert entry.state == LLMCircuitState.COOLING
        assert entry.failures == 0
        assert entry.cooldown_minutes == 0

    def test_circuit_state_values(self):
        assert LLMCircuitState.COOLING.value == "cooling"
        assert LLMCircuitState.WARMING.value == "warming"
        assert LLMCircuitState.DEAD.value == "dead"
