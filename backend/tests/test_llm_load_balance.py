"""测试 LLM 加权路由、分级熔断、Provider 健康、enabled 字段。"""

import json
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
