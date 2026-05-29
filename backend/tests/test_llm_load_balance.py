"""测试 LLM 加权路由、分级熔断、Provider 健康、enabled 字段。"""

import json
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
