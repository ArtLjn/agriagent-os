# Multi LLM Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现配置文件驱动的多 LLM Provider 路由，支持错误分类 fallback、指数退避 cooldown、API key 轮换，统一管理 4 个调用点。

**Architecture:** `providers.json` 定义 provider 优先级和模型列表。`LLMClientManager` 启动时读取配置构建 fallback 链，按错误类型（Provider 级 vs 模型级）决定 fallback 方向。指数退避 cooldown 防止重复请求失败的模型。config.yaml 作为兜底。

**Tech Stack:** Python 3.12, langchain-openai (ChatOpenAI), openai (OpenAI/AsyncOpenAI), json (标准库), pytest

---

## File Structure

```
新增:
  backend/providers.json                        # 运行时 LLM provider 配置
  backend/app/core/llm_client_manager.py        # LLMClientManager 核心
  backend/tests/test_llm_client_manager.py      # 测试

修改:
  backend/.gitignore                            # 排除 providers.json
  backend/app/agent/llm.py                      # get_llm() 接入 Manager
  backend/app/agent/graph.py                    # _get_classifier() 接入 Manager
  backend/app/agent/skills/__init__.py           # build_skill_context() 接入 Manager
```

---

### Task 1: 创建 providers.json + 更新 .gitignore

**Files:**
- Create: `backend/providers.json`
- Modify: `backend/.gitignore`

- [ ] **Step 1: 创建 providers.json**

从 `model_list.json` 迁移，去掉 notes/status/recommended，加入 priority：

```json
{
  "default_provider": "ollama",
  "providers": [
    {
      "name": "ollama",
      "base_url": "https://ollama.com/v1",
      "api_keys": [
        "09437a9e878f481fb4d14034d806143f.51eK2q98YjFdeu3ce62USw0q",
        "5e0fe7c7b4d0421cbc96f22b16fd963c.IWKW59wdP2fihQhHdZlTxluM"
      ],
      "priority": 1,
      "models": [
        {"id": "gemma3:12b", "priority": 1},
        {"id": "glm-5.1", "priority": 2},
        {"id": "deepseek-v4-flash", "priority": 3}
      ]
    },
    {
      "name": "nvidia",
      "base_url": "https://integrate.api.nvidia.com/v1",
      "api_keys": [
        "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"
      ],
      "priority": 2,
      "models": [
        {"id": "meta/llama-3.1-70b-instruct", "priority": 1},
        {"id": "zhipuai/glm-5.1", "priority": 2}
      ]
    },
    {
      "name": "dashscope",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_keys": [
        "sk-test-placeholder"
      ],
      "priority": 3,
      "models": [
        {"id": "qwen3.6-flash-2026-04-16", "priority": 1}
      ]
    }
  ]
}
```

- [ ] **Step 2: 更新 .gitignore**

在 `backend/.gitignore` 末尾添加：

```
providers.json
```

- [ ] **Step 3: Commit**

```bash
cd backend && git add providers.json .gitignore
git commit -m "chore: add providers.json for LLM multi-provider routing"
```

---

### Task 2: 实现 LLMClientManager 核心 + 测试

**Files:**
- Create: `backend/app/core/llm_client_manager.py`
- Create: `backend/tests/test_llm_client_manager.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/test_llm_client_manager.py
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.llm_client_manager import (
    CooldownEntry,
    ErrorLevel,
    LLMClientManager,
    ProviderConfig,
    ModelConfig,
    classify_error,
    get_llm_manager,
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
        for _ in range(20):
            manager.record_failure(key)
        assert manager._cooldowns[key].cooldown_minutes == 1440

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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_llm_client_manager.py -v`
Expected: FAIL (ModuleNotFoundError: app.core.llm_client_manager)

- [ ] **Step 3: 实现 LLMClientManager**

```python
# backend/app/core/llm_client_manager.py
"""LLM Client Manager — 多 Provider 路由、错误分类 fallback、指数退避 cooldown。"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_COOLDOWN_MINUTES = 2
_MAX_COOLDOWN_MINUTES = 1440  # 24h


class ErrorLevel(Enum):
    PROVIDER = "provider"
    MODEL = "model"


@dataclass
class ModelConfig:
    id: str
    priority: int = 1


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_keys: list[str]
    priority: int = 99
    models: list[ModelConfig] = field(default_factory=list)


@dataclass
class CooldownEntry:
    failures: int = 0
    until: datetime = field(default_factory=datetime.now)
    cooldown_minutes: int = 0


def classify_error(exc: Exception) -> ErrorLevel:
    """根据异常类型判断错误级别。"""
    from openai import APIConnectionError, AuthenticationError, RateLimitError

    if isinstance(exc, (APIConnectionError, ConnectionError)):
        return ErrorLevel.PROVIDER

    status_code = getattr(
        getattr(exc, "response", None), "status_code", None
    )
    if status_code in (401, 403):
        return ErrorLevel.PROVIDER
    if status_code in (429, 404, 400):
        return ErrorLevel.MODEL
    if isinstance(exc, AuthenticationError):
        return ErrorLevel.PROVIDER
    if isinstance(exc, RateLimitError):
        return ErrorLevel.MODEL

    return ErrorLevel.PROVIDER


class LLMClientManager:
    """统一 LLM 客户端管理器。"""

    def __init__(self, config_path: str | None = None):
        self._chain: list[tuple[ProviderConfig, ModelConfig]] = []
        self._cooldowns: dict[str, CooldownEntry] = {}
        self._key_counters: dict[str, int] = {}
        self.fallback_mode: bool = False

        path = config_path or str(
            Path(__file__).parent.parent.parent / "providers.json"
        )
        self._load_config(path)

    def _load_config(self, path: str) -> None:
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("providers.json 加载失败，使用 config.yaml 兜底 | error=%s", e)
            self.fallback_mode = True
            return

        providers_raw = data.get("providers", [])
        if not providers_raw:
            logger.warning("providers.json 中无 provider，使用 config.yaml 兜底")
            self.fallback_mode = True
            return

        for p_raw in providers_raw:
            provider = ProviderConfig(
                name=p_raw["name"],
                base_url=p_raw["base_url"],
                api_keys=p_raw.get("api_keys", []),
                priority=p_raw.get("priority", 99),
                models=[
                    ModelConfig(id=m["id"], priority=m.get("priority", 1))
                    for m in p_raw.get("models", [])
                ],
            )
            for model in sorted(provider.models, key=lambda m: m.priority):
                self._chain.append((provider, model))

        self._chain.sort(key=lambda item: (item[0].priority, item[1].priority))
        logger.info(
            "LLMClientManager 初始化 | providers=%d | models=%d",
            len({p.name for p, _ in self._chain}),
            len(self._chain),
        )

    @property
    def chain(self) -> list[tuple[ProviderConfig, ModelConfig]]:
        return self._chain

    def _get_api_key(self, provider: ProviderConfig) -> str:
        idx = self._key_counters.get(provider.name, 0)
        key = provider.api_keys[idx % len(provider.api_keys)]
        self._key_counters[provider.name] = idx + 1
        return key

    def _get_first_available(self) -> tuple[ProviderConfig, ModelConfig, str] | None:
        """获取第一个未 cooldown 的 provider+model+key 组合。"""
        for provider, model in self._chain:
            model_key = f"{provider.name}/{model.id}"
            if self.is_cooled_down(model_key):
                continue
            api_key = self._get_api_key(provider)
            if not api_key:
                continue
            return provider, model, api_key
        return None

    def get_chat_model(self, **kwargs) -> ChatOpenAI:
        """获取 ChatOpenAI 实例（给 llm.py / graph.py 使用）。"""
        result = self._get_first_available()
        if not result:
            raise RuntimeError("所有 LLM Provider 均不可用或处于 cooldown 中")
        provider, model, api_key = result

        extra_body = kwargs.pop("extra_body", None)
        if not settings.ai.enable_thinking:
            extra_body = {**(extra_body or {}), "enable_thinking": False}

        return ChatOpenAI(
            model=model.id,
            api_key=api_key,
            base_url=provider.base_url,
            temperature=kwargs.pop("temperature", 0.7),
            extra_body=extra_body if extra_body else None,
            **kwargs,
        )

    def get_sync_client(self) -> OpenAI:
        """获取同步 OpenAI 客户端（给 tool_selector 的 LLMIntentClassifier 使用）。"""
        result = self._get_first_available()
        if not result:
            raise RuntimeError("所有 LLM Provider 均不可用或处于 cooldown 中")
        provider, model, api_key = result
        return OpenAI(api_key=api_key, base_url=provider.base_url)

    def get_async_client(self) -> AsyncOpenAI:
        """获取异步 OpenAI 客户端（给 skills 使用）。"""
        result = self._get_first_available()
        if not result:
            raise RuntimeError("所有 LLM Provider 均不可用或处于 cooldown 中")
        provider, model, api_key = result
        return AsyncOpenAI(api_key=api_key, base_url=provider.base_url)

    def get_model_info(self) -> dict:
        """返回当前使用的 provider/model 信息。"""
        result = self._get_first_available()
        if not result:
            return {"provider": "", "model": "", "base_url": ""}
        provider, model, _ = result
        return {
            "provider": provider.name,
            "model": model.id,
            "base_url": provider.base_url,
        }

    def record_failure(self, key: str) -> None:
        """记录失败并计算 cooldown。"""
        entry = self._cooldowns.get(key, CooldownEntry())
        entry.failures += 1
        entry.cooldown_minutes = min(
            _BASE_COOLDOWN_MINUTES * (2 ** (entry.failures - 1)),
            _MAX_COOLDOWN_MINUTES,
        )
        entry.until = datetime.now() + timedelta(minutes=entry.cooldown_minutes)
        self._cooldowns[key] = entry
        logger.info(
            "cooldown | key=%s | failures=%d | cooldown=%dmin",
            key, entry.failures, entry.cooldown_minutes,
        )

    def record_success(self, key: str) -> None:
        """记录成功，清除 cooldown。"""
        self._cooldowns.pop(key, None)

    def is_cooled_down(self, key: str) -> bool:
        """检查是否仍在 cooldown 期内。"""
        entry = self._cooldowns.get(key)
        if not entry:
            return False
        return datetime.now() < entry.until


_manager: LLMClientManager | None = None


def get_llm_manager() -> LLMClientManager:
    """获取全局 LLMClientManager 单例。"""
    global _manager
    if _manager is None:
        _manager = LLMClientManager()
    return _manager
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_llm_client_manager.py -v`
Expected: 20+ passed

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/core/llm_client_manager.py tests/test_llm_client_manager.py
git commit -m "feat: add LLMClientManager with multi-provider routing and cooldown"
```

---

### Task 3: 改造 llm.py — 接入 Manager

**Files:**
- Modify: `backend/app/agent/llm.py:40-68`

- [ ] **Step 1: 修改 get_llm()**

将 `backend/app/agent/llm.py` 中的 `get_llm()` 函数（第 40-68 行）替换为：

```python
def get_llm() -> BaseChatModel:
    """获取全局 LLM 实例（优先 Manager，兜底 config.yaml）。"""
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        cb = settings.circuit_breaker_config
        extra_body: dict = {}
        if not settings.ai.enable_thinking:
            extra_body["enable_thinking"] = False

        # 优先从 LLMClientManager 获取
        try:
            from app.core.llm_client_manager import get_llm_manager

            manager = get_llm_manager()
            if not manager.fallback_mode:
                LLM_INSTANCE = manager.get_chat_model(
                    temperature=0.7,
                    max_retries=cb.retry_max,
                    timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
                    extra_body=extra_body if extra_body else None,
                )
                info = manager.get_model_info()
                logger.info(
                    "LLM 客户端初始化(Manager) | provider=%s | model=%s",
                    info["provider"],
                    info["model"],
                )
                return LLM_INSTANCE
        except Exception as e:
            logger.warning("LLMClientManager 失败，回退 config.yaml | error=%s", e)

        # 兜底: config.yaml
        if not settings.ai_api_key:
            raise LlmNotConfiguredError(
                "AI API key 未配置。请在 providers.json 或 config.yaml 中设置。"
            )

        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
            max_retries=cb.retry_max,
            timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
            extra_body=extra_body if extra_body else None,
        )
        logger.info(
            "LLM 客户端初始化(config.yaml兜底) | model=%s", settings.ai_model
        )
    return LLM_INSTANCE
```

- [ ] **Step 2: 运行现有测试**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: PASSED（测试 mock 了 settings，走兜底路径）

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/agent/llm.py
git commit -m "feat: integrate LLMClientManager into get_llm()"
```

---

### Task 4: 改造 graph.py — _get_classifier 接入 Manager

**Files:**
- Modify: `backend/app/agent/graph.py:46-56`

- [ ] **Step 1: 修改 _get_classifier()**

将 `backend/app/agent/graph.py` 中的 `_get_classifier()` 函数（第 46-56 行）替换为：

```python
def _get_classifier() -> LLMIntentClassifier | None:
    global _classifier
    if _classifier is not None:
        return _classifier

    api_key = settings.ai_api_key
    base_url = settings.ai_base_url
    model = settings.ai_model

    # 优先从 Manager 获取
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            info = manager.get_model_info()
            client = manager.get_sync_client()
            api_key = client.api_key
            base_url = client.base_url
            model = info["model"]
    except Exception as e:
        logger.debug("从 Manager 获取 classifier 参数失败 | error=%s", e)

    if api_key:
        with _classifier_lock:
            if _classifier is None:
                _classifier = LLMIntentClassifier(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                )
    return _classifier
```

- [ ] **Step 2: Commit**

```bash
cd backend && git add app/agent/graph.py
git commit -m "feat: integrate LLMClientManager into _get_classifier()"
```

---

### Task 5: 改造 skills/__init__.py — build_skill_context 接入 Manager

**Files:**
- Modify: `backend/app/agent/skills/__init__.py:136-151`

- [ ] **Step 1: 修改 build_skill_context()**

将 `backend/app/agent/skills/__init__.py` 中的 `build_skill_context()` 函数（第 136-151 行）替换为：

```python
def build_skill_context(farm_id: int) -> SkillContext:
    """构建 skillify SkillContext，优先从 Manager 获取 LLM 配置。"""
    from openai import AsyncOpenAI

    from app.core.config import settings

    api_key = settings.ai_api_key
    base_url = settings.ai_base_url
    model = settings.ai_model

    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            info = manager.get_model_info()
            client = manager.get_async_client()
            api_key = client.api_key
            base_url = client.base_url
            model = info["model"]
    except Exception:
        pass

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return SkillContext(
        user_id=str(farm_id),
        farm_id=farm_id,
        llm_model=model,
        llm_client=client,
    )
```

- [ ] **Step 2: Commit**

```bash
cd backend && git add app/agent/skills/__init__.py
git commit -m "feat: integrate LLMClientManager into build_skill_context()"
```

---

### Task 6: 全量测试 + Lint

**Files:** 无新增

- [ ] **Step 1: 运行全量测试**

Run: `cd backend && python -m pytest -v --tb=short 2>&1 | tail -40`
Expected: 所有测试通过

- [ ] **Step 2: Lint 检查**

Run: `cd backend && ruff check app/core/llm_client_manager.py app/agent/llm.py app/agent/graph.py app/agent/skills/__init__.py && ruff format app/core/llm_client_manager.py app/agent/llm.py app/agent/graph.py app/agent/skills/__init__.py`
Expected: 无错误

- [ ] **Step 3: Commit（如有格式修正）**

```bash
cd backend && git add -A && git commit -m "style: lint fixes for LLM router integration"
```
