"""测试 LLMClientManager -- 多 Provider 路由、fallback 链、cooldown、key 轮换。"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from app.core.llm_client_manager import (
    ErrorLevel,
    LLMCircuitState,
    LLMClientManager,
    classify_error,
)


def _write_providers_json(path: Path, data: dict):
    path.write_text(json.dumps(data))


class TestProviderConfig:
    """测试配置加载和 fallback 链构建。"""

    def test_load_providers_json(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "https://ollama.com/v1",
                    "api_keys": ["key1"],
                    "priority": 1,
                    "models": [{"id": "gemma3:12b", "priority": 1}],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)

        manager = LLMClientManager(config_path=str(p))
        assert len(manager.chain) == 1
        provider, model = manager.chain[0]
        assert provider.name == "ollama"
        assert model.id == "gemma3:12b"

    def test_chain_ordered_by_priority(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "low",
                    "base_url": "http://low",
                    "api_keys": ["k"],
                    "priority": 10,
                    "models": [{"id": "low-model", "priority": 1}],
                },
                {
                    "name": "high",
                    "base_url": "http://high",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [{"id": "high-model", "priority": 1}],
                },
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)

        manager = LLMClientManager(config_path=str(p))
        assert manager.chain[0][0].name == "high"
        assert manager.chain[1][0].name == "low"

    def test_models_ordered_by_priority_within_provider(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "http://test",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [
                        {"id": "model-b", "priority": 2},
                        {"id": "model-a", "priority": 1},
                    ],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)

        manager = LLMClientManager(config_path=str(p))
        assert manager.chain[0][1].id == "model-a"
        assert manager.chain[1][1].id == "model-b"

    def test_missing_providers_json_falls_back(self, tmp_path):
        manager = LLMClientManager(config_path=str(tmp_path / "nonexistent.json"))
        assert len(manager.chain) == 0
        assert manager.fallback_mode is True

    def test_invalid_json_falls_back(self, tmp_path):
        p = tmp_path / "providers.json"
        p.write_text("{invalid json")
        manager = LLMClientManager(config_path=str(p))
        assert manager.fallback_mode is True

    def test_empty_providers_array(self, tmp_path):
        p = tmp_path / "providers.json"
        _write_providers_json(p, {"providers": []})
        manager = LLMClientManager(config_path=str(p))
        assert manager.fallback_mode is True

    def test_default_provider_moves_to_front(self, tmp_path):
        cfg = {
            "default_provider": "nvidia",
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "http://ollama",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [{"id": "gemma3:12b", "priority": 1}],
                },
                {
                    "name": "nvidia",
                    "base_url": "http://nvidia",
                    "api_keys": ["k"],
                    "priority": 2,
                    "models": [{"id": "llama-3.1-70b", "priority": 1}],
                },
                {
                    "name": "dashscope",
                    "base_url": "http://dashscope",
                    "api_keys": ["k"],
                    "priority": 3,
                    "models": [{"id": "qwen", "priority": 1}],
                },
            ],
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        assert manager.chain[0][0].name == "nvidia"
        assert manager.chain[1][0].name == "ollama"
        assert manager.chain[2][0].name == "dashscope"

    def test_default_provider_preserves_model_order(self, tmp_path):
        cfg = {
            "default_provider": "nvidia",
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "http://ollama",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [{"id": "gemma", "priority": 1}],
                },
                {
                    "name": "nvidia",
                    "base_url": "http://nvidia",
                    "api_keys": ["k"],
                    "priority": 2,
                    "models": [
                        {"id": "model-b", "priority": 2},
                        {"id": "model-a", "priority": 1},
                    ],
                },
            ],
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        assert manager.chain[0][1].id == "model-a"
        assert manager.chain[1][1].id == "model-b"

    def test_no_default_provider_uses_priority(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "low",
                    "base_url": "http://low",
                    "api_keys": ["k"],
                    "priority": 10,
                    "models": [{"id": "m1", "priority": 1}],
                },
                {
                    "name": "high",
                    "base_url": "http://high",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [{"id": "m2", "priority": 1}],
                },
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        assert manager.chain[0][0].name == "high"


class TestErrorClassification:
    """测试错误分类逻辑。"""

    def test_connection_error_is_provider_level(self):
        from openai import APIConnectionError

        err = APIConnectionError(request=MagicMock())
        assert classify_error(err) == ErrorLevel.PROVIDER

    def test_401_is_provider_level(self):
        from openai import AuthenticationError

        err = AuthenticationError(
            message="bad key", response=MagicMock(status_code=401), body=None
        )
        assert classify_error(err) == ErrorLevel.PROVIDER

    def test_429_is_model_level(self):
        from openai import RateLimitError

        err = RateLimitError(
            message="rate limited", response=MagicMock(status_code=429), body=None
        )
        assert classify_error(err) == ErrorLevel.MODEL

    def test_404_is_model_level(self):
        from openai import NotFoundError

        err = NotFoundError(
            message="not found", response=MagicMock(status_code=404), body=None
        )
        assert classify_error(err) == ErrorLevel.MODEL

    def test_generic_error_is_provider_level(self):
        err = RuntimeError("something unexpected")
        assert classify_error(err) == ErrorLevel.PROVIDER

    def test_error_level_has_quota_exhausted(self):
        assert hasattr(ErrorLevel, "QUOTA_EXHAUSTED")
        assert ErrorLevel.QUOTA_EXHAUSTED.value == "quota_exhausted"


class TestCooldown:
    """测试指数退避 cooldown。"""

    def _make_manager(self, tmp_path) -> LLMClientManager:
        cfg = {
            "providers": [
                {
                    "name": "test",
                    "base_url": "http://test",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [{"id": "m1", "priority": 1}],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        return LLMClientManager(config_path=str(p))

    def test_first_failure_cooldown_2min(self, tmp_path):
        manager = self._make_manager(tmp_path)
        key = "test/m1"
        manager.record_failure(key)
        entry = manager._cooldowns[key]
        assert entry.failures == 1
        assert entry.cooldown_minutes == 2

    def test_third_failure_cooldown_8min(self, tmp_path):
        manager = self._make_manager(tmp_path)
        key = "test/m1"
        for _ in range(3):
            manager.record_failure(key)
        assert manager._cooldowns[key].cooldown_minutes == 8

    def test_cooldown_caps_at_24h(self, tmp_path):
        manager = self._make_manager(tmp_path)
        key = "test/m1"
        for _ in range(9):
            manager.record_failure(key)
        assert manager._cooldowns[key].cooldown_minutes == 1440
        assert manager._cooldowns[key].state == LLMCircuitState.WARMING

    def test_success_resets_cooldown(self, tmp_path):
        manager = self._make_manager(tmp_path)
        key = "test/m1"
        manager.record_failure(key)
        manager.record_failure(key)
        assert manager._cooldowns[key].failures == 2

        manager.record_success(key)
        assert key not in manager._cooldowns

    def test_is_cooled_down_returns_true_during_cooldown(self, tmp_path):
        manager = self._make_manager(tmp_path)
        key = "test/m1"
        manager.record_failure(key)
        assert manager.is_cooled_down(key) is True

    def test_is_cooled_down_returns_false_after_expiry(self, tmp_path):
        manager = self._make_manager(tmp_path)
        key = "test/m1"
        manager.record_failure(key)
        # 手动设置 cooldown 为过去时间
        manager._cooldowns[key].until = datetime.now() - timedelta(minutes=1)
        assert manager.is_cooled_down(key) is False


class TestKeyRotation:
    """测试 API key 轮询。"""

    def test_round_robin(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "test",
                    "base_url": "http://test",
                    "api_keys": ["key-a", "key-b"],
                    "priority": 1,
                    "models": [{"id": "m1", "priority": 1}],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        provider = manager.chain[0][0]
        assert manager._get_api_key(provider) == "key-a"
        assert manager._get_api_key(provider) == "key-b"
        assert manager._get_api_key(provider) == "key-a"

    def test_single_key(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "test",
                    "base_url": "http://test",
                    "api_keys": ["only-key"],
                    "priority": 1,
                    "models": [{"id": "m1", "priority": 1}],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        provider = manager.chain[0][0]
        assert manager._get_api_key(provider) == "only-key"
        assert manager._get_api_key(provider) == "only-key"


class TestGetModelInfo:
    """测试 get_model_info。"""

    def test_returns_current_provider_model(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "https://ollama.com/v1",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [{"id": "gemma3:12b", "priority": 1}],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        info = manager.get_model_info()
        assert info["provider"] == "ollama"
        assert info["model"] == "gemma3:12b"
        assert info["base_url"] == "https://ollama.com/v1"

    def test_returns_empty_when_fallback(self, tmp_path):
        manager = LLMClientManager(config_path=str(tmp_path / "none.json"))
        info = manager.get_model_info()
        assert info["provider"] == ""
        assert info["model"] == ""
