"""测试 LLM 加权路由、分级熔断、Provider 健康、enabled 字段。"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from app.core.llm_client_manager import LLMCircuitState, CircuitEntry, LLMClientManager


def _write_cfg(path: Path, data: dict):
    path.write_text(json.dumps(data))


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


class TestWeightEnabledFields:
    """测试 weight 和 enabled 字段解析。"""

    def test_provider_weight_parsed(self, tmp_path):
        cfg = {
            "providers": [{
                "name": "ollama",
                "base_url": "http://test",
                "api_keys": ["k"],
                "priority": 1,
                "weight": 8,
                "models": [{"id": "m1", "priority": 1}],
            }]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        mgr = LLMClientManager(config_path=str(p))
        assert mgr.chain[0][0].weight == 8

    def test_provider_weight_default_is_1(self, tmp_path):
        cfg = {
            "providers": [{
                "name": "test",
                "base_url": "http://test",
                "api_keys": ["k"],
                "priority": 1,
                "models": [{"id": "m1", "priority": 1}],
            }]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        mgr = LLMClientManager(config_path=str(p))
        assert mgr.chain[0][0].weight == 1

    def test_provider_enabled_false_skipped(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "disabled",
                    "base_url": "http://d",
                    "api_keys": ["k"],
                    "priority": 1,
                    "enabled": False,
                    "models": [{"id": "m1", "priority": 1}],
                },
                {
                    "name": "enabled",
                    "base_url": "http://e",
                    "api_keys": ["k"],
                    "priority": 2,
                    "models": [{"id": "m2", "priority": 1}],
                },
            ]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        mgr = LLMClientManager(config_path=str(p))
        assert len(mgr.chain) == 1
        assert mgr.chain[0][0].name == "enabled"

    def test_model_enabled_false_skipped(self, tmp_path):
        cfg = {
            "providers": [{
                "name": "test",
                "base_url": "http://test",
                "api_keys": ["k"],
                "priority": 1,
                "models": [
                    {"id": "m1", "priority": 1, "enabled": False},
                    {"id": "m2", "priority": 2},
                ],
            }]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        mgr = LLMClientManager(config_path=str(p))
        assert len(mgr.chain) == 1
        assert mgr.chain[0][1].id == "m2"


class TestTieredCircuit:
    """测试 COOLING → WARMING → DEAD 状态升级。"""

    def _make_manager(self, tmp_path) -> LLMClientManager:
        cfg = {
            "providers": [{
                "name": "test",
                "base_url": "http://test",
                "api_keys": ["k"],
                "priority": 1,
                "weight": 1,
                "models": [{"id": "m1", "priority": 1}],
            }]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        return LLMClientManager(config_path=str(p))

    def test_1_to_3_failures_are_cooling(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        key = "test/m1"
        for i in range(1, 4):
            mgr.record_failure(key)
            entry = mgr._cooldowns[key]
            assert entry.state == LLMCircuitState.COOLING, f"第{i}次失败应保持 COOLING"

    def test_4_to_9_failures_are_warming(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        key = "test/m1"
        for _ in range(3):
            mgr.record_failure(key)
        for i in range(4, 10):
            mgr.record_failure(key)
            entry = mgr._cooldowns[key]
            assert entry.state == LLMCircuitState.WARMING, f"第{i}次失败应为 WARMING"

    def test_10_failures_is_dead(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        key = "test/m1"
        for _ in range(10):
            mgr.record_failure(key)
        entry = mgr._cooldowns[key]
        assert entry.state == LLMCircuitState.DEAD

    def test_dead_is_permanently_cooled_down(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        key = "test/m1"
        for _ in range(10):
            mgr.record_failure(key)
        mgr._cooldowns[key].until = datetime.now() - timedelta(hours=48)
        assert mgr.is_cooled_down(key) is True

    def test_cooling_cooldown_exponential(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        key = "test/m1"
        mgr.record_failure(key)
        assert mgr._cooldowns[key].cooldown_minutes == 2
        mgr.record_failure(key)
        assert mgr._cooldowns[key].cooldown_minutes == 4
        mgr.record_failure(key)
        assert mgr._cooldowns[key].cooldown_minutes == 8

    def test_warming_cooldown_is_24h(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        key = "test/m1"
        for _ in range(4):
            mgr.record_failure(key)
        assert mgr._cooldowns[key].cooldown_minutes == 1440
        assert mgr._cooldowns[key].state == LLMCircuitState.WARMING


class TestWeightedRouting:
    """测试加权随机路由。"""

    def _make_multi_manager(self, tmp_path) -> LLMClientManager:
        cfg = {
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "http://ollama",
                    "api_keys": ["k1"],
                    "priority": 1,
                    "weight": 8,
                    "models": [{"id": "gemma3:12b", "priority": 1}],
                },
                {
                    "name": "nvidia",
                    "base_url": "http://nvidia",
                    "api_keys": ["k2"],
                    "priority": 2,
                    "weight": 2,
                    "models": [{"id": "llama-3.1-70b", "priority": 1}],
                },
                {
                    "name": "dashscope",
                    "base_url": "http://dashscope",
                    "api_keys": ["k3"],
                    "priority": 3,
                    "weight": 1,
                    "models": [{"id": "qwen", "priority": 1}],
                },
            ]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        return LLMClientManager(config_path=str(p))

    def test_weighted_distribution(self, tmp_path):
        """1000 次调用统计 provider 分布。"""
        mgr = self._make_multi_manager(tmp_path)
        random.seed(42)
        counts = {"ollama": 0, "nvidia": 0, "dashscope": 0}
        n = 1000
        for _ in range(n):
            result = mgr._get_next_available()
            assert result is not None
            provider, model, _ = result
            counts[provider.name] += 1
        assert 630 < counts["ollama"] < 830, f"ollama: {counts['ollama']}"
        assert 100 < counts["nvidia"] < 300, f"nvidia: {counts['nvidia']}"
        assert 50 < counts["dashscope"] < 200, f"dashscope: {counts['dashscope']}"

    def test_skips_dead_models(self, tmp_path):
        mgr = self._make_multi_manager(tmp_path)
        for _ in range(10):
            mgr.record_failure("ollama/gemma3:12b")
        assert mgr._cooldowns["ollama/gemma3:12b"].state == LLMCircuitState.DEAD
        for _ in range(20):
            result = mgr._get_next_available()
            assert result is not None
            assert result[0].name != "ollama"

    def test_skips_cooled_down_models(self, tmp_path):
        mgr = self._make_multi_manager(tmp_path)
        mgr.record_failure("nvidia/llama-3.1-70b")
        assert mgr.is_cooled_down("nvidia/llama-3.1-70b")
        for _ in range(20):
            result = mgr._get_next_available()
            assert result is not None
            assert result[0].name != "nvidia"

    def test_all_dead_returns_none(self, tmp_path):
        mgr = self._make_multi_manager(tmp_path)
        for key in ["ollama/gemma3:12b", "nvidia/llama-3.1-70b", "dashscope/qwen"]:
            for _ in range(10):
                mgr.record_failure(key)
        assert mgr._get_next_available() is None

    def test_returns_none_when_no_api_keys(self, tmp_path):
        cfg = {
            "providers": [{
                "name": "empty",
                "base_url": "http://test",
                "api_keys": [],
                "priority": 1,
                "weight": 1,
                "models": [{"id": "m1", "priority": 1}],
            }]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        mgr = LLMClientManager(config_path=str(p))
        assert mgr._get_next_available() is None


class TestProviderHealth:
    """测试 Provider 级别健康检查。"""

    def test_unhealthy_when_half_models_down(self, tmp_path):
        cfg = {
            "providers": [{
                "name": "test",
                "base_url": "http://test",
                "api_keys": ["k"],
                "priority": 1,
                "weight": 1,
                "models": [
                    {"id": "m1", "priority": 1},
                    {"id": "m2", "priority": 2},
                ],
            }]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        mgr = LLMClientManager(config_path=str(p))
        for _ in range(10):
            mgr.record_failure("test/m1")
        assert mgr._is_provider_healthy("test") is False
