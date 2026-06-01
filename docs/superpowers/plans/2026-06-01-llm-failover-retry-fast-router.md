# LLM Failover Retry & Fast Router 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LLM 调用失败时在请求内自动切换 provider 重试，工具选择阶段使用轻量模型降低首 token 延迟，403 配额耗尽直接 DEAD。

**Architecture:** 在 `_llm_node` 的 `ainvoke` 处增加重试循环，失败时重新调用 `get_llm(role=...)` 获取新 provider。`LLMClientManager` 新增 `role` 筛选能力，`providers.json` 模型新增 `roles` 字段标记用途。`record_failure()` 支持按 error_level 分级处理，`QUOTA_EXHAUSTED` 直接到 DEAD。

**Tech Stack:** Python 3.12 / FastAPI / LangChain / Pydantic / pytest

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/core/llm_client_manager.py` | 修改 | ErrorLevel 枚举、classify_error、record_failure、ModelConfig roles、get_chat_model/get_sync_client/get_model_info role 参数 |
| `backend/app/agent/llm.py` | 修改 | get_llm() 新增 role 参数 |
| `backend/app/agent/graph.py` | 修改 | _llm_node 重试循环、双阶段模型、_get_classifier 轻量模型、_record_llm_failure 传入 error_level |
| `backend/app/core/config.py` | 修改 | AIConfig 新增 failover_max_retries |
| `backend/providers.json` | 修改 | 模型新增 roles 字段 |
| `backend/tests/test_llm_client_manager.py` | 修改 | 新增测试类覆盖 QUOTA_EXHAUSTED、role 筛选 |

---

### Task 1: ErrorLevel 枚举新增 QUOTA_EXHAUSTED

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:30-33`
- Test: `backend/tests/test_llm_client_manager.py`

- [ ] **Step 1: 写失败测试 — QUOTA_EXHAUSTED 枚举值存在**

在 `test_llm_client_manager.py` 的 `TestErrorClassification` 类中新增：

```python
def test_error_level_has_quota_exhausted(self):
    assert hasattr(ErrorLevel, "QUOTA_EXHAUSTED")
    assert ErrorLevel.QUOTA_EXHAUSTED.value == "quota_exhausted"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestErrorClassification::test_error_level_has_quota_exhausted -v`
Expected: FAIL — `AttributeError: 'QUOTA_EXHAUSTED'`

- [ ] **Step 3: 实现 — ErrorLevel 枚举新增值**

修改 `backend/app/core/llm_client_manager.py`，在 `ErrorLevel` 枚举中新增 `QUOTA_EXHAUSTED`：

```python
class ErrorLevel(Enum):
    PROVIDER = "provider"
    MODEL = "model"
    QUOTA_EXHAUSTED = "quota_exhausted"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestErrorClassification::test_error_level_has_quota_exhausted -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/llm_client_manager.py tests/test_llm_client_manager.py
git commit -m "feat(llm): ErrorLevel 新增 QUOTA_EXHAUSTED 枚举值"
```

---

### Task 2: classify_error 识别配额耗尽错误

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:69-86`
- Test: `backend/tests/test_llm_client_manager.py`

- [ ] **Step 1: 写失败测试 — 403 含 AllocationQuota.FreeTierOnly 返回 QUOTA_EXHAUSTED**

在 `TestErrorClassification` 类中新增：

```python
def test_403_quota_exhausted_is_quota_level(self):
    from openai import PermissionDeniedError

    err = PermissionDeniedError(
        message="AllocationQuota.FreeTierOnly",
        response=MagicMock(status_code=403),
        body=None,
    )
    assert classify_error(err) == ErrorLevel.QUOTA_EXHAUSTED

def test_403_without_quota_exhausted_is_provider_level(self):
    from openai import PermissionDeniedError

    err = PermissionDeniedError(
        message="some other 403 error",
        response=MagicMock(status_code=403),
        body=None,
    )
    assert classify_error(err) == ErrorLevel.PROVIDER
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestErrorClassification::test_403_quota_exhausted_is_quota_level -v`
Expected: FAIL — 返回 `ErrorLevel.PROVIDER` 而非 `QUOTA_EXHAUSTED`

- [ ] **Step 3: 实现 — classify_error 识别配额耗尽**

修改 `backend/app/core/llm_client_manager.py` 中的 `classify_error` 函数：

```python
def classify_error(exc: Exception) -> ErrorLevel:
    """根据异常类型判断错误级别。"""
    from openai import APIConnectionError, AuthenticationError, RateLimitError

    if isinstance(exc, (APIConnectionError, ConnectionError)):
        return ErrorLevel.PROVIDER

    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code == 403:
        err_msg = str(getattr(exc, "message", "")) or str(exc)
        if "AllocationQuota.FreeTierOnly" in err_msg:
            return ErrorLevel.QUOTA_EXHAUSTED
        return ErrorLevel.PROVIDER
    if status_code == 401:
        return ErrorLevel.PROVIDER
    if status_code in (429, 404, 400):
        return ErrorLevel.MODEL
    if isinstance(exc, AuthenticationError):
        return ErrorLevel.PROVIDER
    if isinstance(exc, RateLimitError):
        return ErrorLevel.MODEL

    return ErrorLevel.PROVIDER
```

注意：403 单独拆出来先检查是否是配额耗尽，再走默认 PROVIDER 逻辑。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestErrorClassification -v`
Expected: 全部 PASS（包括原有测试和新增测试）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/llm_client_manager.py tests/test_llm_client_manager.py
git commit -m "feat(llm): classify_error 识别 AllocationQuota.FreeTierOnly 为 QUOTA_EXHAUSTED"
```

---

### Task 3: record_failure 支持按 error_level 分级处理

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:296-324`
- Modify: `backend/app/agent/graph.py:185-198`
- Test: `backend/tests/test_llm_client_manager.py`

- [ ] **Step 1: 写失败测试 — QUOTA_EXHAUSTED 直接设 DEAD**

在 `test_llm_client_manager.py` 的 `TestCooldown` 类中新增：

```python
def test_quota_exhausted_immediate_dead(self, tmp_path):
    manager = self._make_manager(tmp_path)
    key = "test/m1"
    manager.record_failure(key, error_level=ErrorLevel.QUOTA_EXHAUSTED)
    entry = manager._cooldowns[key]
    assert entry.state == LLMCircuitState.DEAD
    assert entry.failures == 1

def test_quota_exhausted_skips_exponential_backoff(self, tmp_path):
    manager = self._make_manager(tmp_path)
    key = "test/m1"
    manager.record_failure(key, error_level=ErrorLevel.QUOTA_EXHAUSTED)
    entry = manager._cooldowns[key]
    assert entry.cooldown_minutes == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestCooldown::test_quota_exhausted_immediate_dead -v`
Expected: FAIL — `record_failure` 不接受 `error_level` 参数

- [ ] **Step 3: 实现 — record_failure 新增 error_level 参数**

修改 `backend/app/core/llm_client_manager.py` 中的 `record_failure` 方法签名和逻辑：

```python
def record_failure(self, key: str, error_level: ErrorLevel | None = None) -> None:
    """记录失败并分级升级熔断状态。"""
    entry = self._cooldowns.get(key, CircuitEntry())
    entry.failures += 1

    if error_level == ErrorLevel.QUOTA_EXHAUSTED:
        entry.state = LLMCircuitState.DEAD
        entry.cooldown_minutes = 0
    elif entry.failures >= 10:
        entry.state = LLMCircuitState.DEAD
        entry.cooldown_minutes = 0
    elif entry.failures >= 4:
        entry.state = LLMCircuitState.WARMING
        entry.cooldown_minutes = 1440
    else:
        entry.state = LLMCircuitState.COOLING
        entry.cooldown_minutes = min(
            _BASE_COOLDOWN_MINUTES * (2 ** (entry.failures - 1)),
            _MAX_COOLDOWN_MINUTES,
        )

    if entry.state != LLMCircuitState.DEAD:
        entry.until = datetime.now() + timedelta(minutes=entry.cooldown_minutes)

    self._cooldowns[key] = entry
    logger.info(
        "circuit | key=%s | failures=%d | state=%s | cooldown=%dmin",
        key,
        entry.failures,
        entry.state.value,
        entry.cooldown_minutes,
    )
```

- [ ] **Step 4: 修改 graph.py 的 _record_llm_failure 传入 error_level**

修改 `backend/app/agent/graph.py` 中的 `_record_llm_failure`：

```python
def _record_llm_failure(circuit_key: str, exc: Exception) -> None:
    """LLM 调用失败，记录到 Manager cooldown。"""
    try:
        from app.core.llm_client_manager import get_llm_manager, classify_error
        manager = get_llm_manager()
        if not manager.fallback_mode:
            level = classify_error(exc)
            manager.record_failure(circuit_key, error_level=level)
            logger.warning(
                "LLM 故障记录 | key=%s | level=%s | error=%s",
                circuit_key, level.value, str(exc)[:120],
            )
    except Exception as e:
        logger.debug("记录 LLM 故障失败 | error=%s", e)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestCooldown -v`
Expected: 全部 PASS（包括原有和新增）

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/core/llm_client_manager.py app/agent/graph.py tests/test_llm_client_manager.py
git commit -m "feat(llm): record_failure 支持 QUOTA_EXHAUSTED 直接设 DEAD 状态"
```

---

### Task 4: ModelConfig roles 字段 + _load_config 解析

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:52-56`
- Modify: `backend/app/core/llm_client_manager.py:103-160`（_load_config）
- Test: `backend/tests/test_llm_client_manager.py`

- [ ] **Step 1: 写失败测试 — roles 字段解析**

在 `test_llm_client_manager.py` 中新增测试类：

```python
class TestModelRoles:
    """测试模型角色配置。"""

    def test_model_with_roles(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "http://test",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [
                        {"id": "gemma3:12b", "priority": 1, "roles": ["tool-selection"]},
                    ],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        _, model = manager.chain[0]
        assert model.roles == ["tool-selection"]

    def test_model_without_roles_defaults_to_all(self, tmp_path):
        cfg = {
            "providers": [
                {
                    "name": "ollama",
                    "base_url": "http://test",
                    "api_keys": ["k"],
                    "priority": 1,
                    "models": [{"id": "gemma3:12b", "priority": 1}],
                }
            ]
        }
        p = tmp_path / "providers.json"
        _write_providers_json(p, cfg)
        manager = LLMClientManager(config_path=str(p))

        _, model = manager.chain[0]
        assert model.roles == ["all"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestModelRoles -v`
Expected: FAIL — `ModelConfig` 没有 `roles` 属性

- [ ] **Step 3: 实现 — ModelConfig 新增 roles + _load_config 解析**

修改 `ModelConfig` dataclass：

```python
@dataclass
class ModelConfig:
    id: str
    priority: int = 1
    enabled: bool = True
    roles: list[str] = field(default_factory=lambda: ["all"])
```

修改 `_load_config` 中的 `ModelConfig` 构造（约第 133-136 行）：

```python
ModelConfig(
    id=m["id"],
    priority=m.get("priority", 1),
    enabled=m.get("enabled", True),
    roles=m.get("roles", ["all"]),
)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestModelRoles -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/llm_client_manager.py tests/test_llm_client_manager.py
git commit -m "feat(llm): ModelConfig 新增 roles 字段，_load_config 解析 roles"
```

---

### Task 5: get_chat_model / get_sync_client / get_model_info 支持 role 筛选

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:204-294`
- Test: `backend/tests/test_llm_client_manager.py`

- [ ] **Step 1: 写失败测试 — role 筛选**

在 `TestModelRoles` 类中新增：

```python
def _make_multi_role_manager(self, tmp_path) -> LLMClientManager:
    cfg = {
        "providers": [
            {
                "name": "ollama",
                "base_url": "http://ollama",
                "api_keys": ["k"],
                "priority": 1,
                "models": [
                    {"id": "gemma3:12b", "priority": 1, "roles": ["tool-selection"]},
                    {"id": "gemma4:31b", "priority": 2, "roles": ["generation"]},
                ],
            },
            {
                "name": "nvidia",
                "base_url": "http://nvidia",
                "api_keys": ["k"],
                "priority": 2,
                "models": [
                    {"id": "glm-4.7", "priority": 1, "roles": ["all"]},
                ],
            },
        ]
    }
    p = tmp_path / "providers.json"
    _write_providers_json(p, cfg)
    return LLMClientManager(config_path=str(p))

def test_get_chat_model_tool_selection(self, tmp_path):
    manager = self._make_multi_role_manager(tmp_path)
    llm = manager.get_chat_model(role="tool-selection")
    assert llm.model_name == "gemma3:12b"

def test_get_chat_model_generation(self, tmp_path):
    manager = self._make_multi_role_manager(tmp_path)
    llm = manager.get_chat_model(role="generation")
    assert llm.model_name in ("gemma4:31b", "glm-4.7")

def test_get_model_info_by_role(self, tmp_path):
    manager = self._make_multi_role_manager(tmp_path)
    info = manager.get_model_info(role="tool-selection")
    assert info["model"] == "gemma3:12b"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestModelRoles::test_get_chat_model_tool_selection -v`
Expected: FAIL — `get_chat_model` 不接受 `role` 参数

- [ ] **Step 3: 实现 — _get_next_available 支持 role 筛选**

修改 `_get_next_available` 方法签名，新增 `role` 参数：

```python
def _get_next_available(
    self,
    role: str | None = None,
) -> tuple[ProviderConfig, ModelConfig, str] | None:
    """获取下一个可用的 provider+model+key（加权随机，可选角色筛选）。"""
    seen_providers: set[str] = set()
    candidates: list[tuple[ProviderConfig, ModelConfig, str, int]] = []

    for provider, model in self._chain:
        if not provider.enabled or not model.enabled:
            continue
        if not provider.api_keys:
            continue
        if role is not None and role not in model.roles and "all" not in model.roles:
            continue
        model_key = f"{provider.name}/{model.id}"
        if self.is_cooled_down(model_key):
            continue
        if not self._is_provider_healthy(provider.name):
            continue
        if provider.name in seen_providers:
            continue
        seen_providers.add(provider.name)
        api_key = self._get_api_key(provider)
        if not api_key:
            continue
        candidates.append((provider, model, api_key, provider.weight))

    return self._weighted_random_choice(candidates)
```

- [ ] **Step 4: 实现 — get_chat_model / get_sync_client / get_model_info 透传 role**

修改 `get_chat_model`：

```python
def get_chat_model(self, *, role: str = "generation", **kwargs) -> ChatOpenAI:
    """获取 ChatOpenAI 实例（给 llm.py / graph.py 使用）。"""
    result = self._get_next_available(role=role)
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
        streaming=True,
        extra_body=extra_body if extra_body else None,
        **kwargs,
    )
```

修改 `get_sync_client`：

```python
def get_sync_client(self, *, role: str = "generation") -> OpenAI:
    """获取同步 OpenAI 客户端（给 tool_selector 使用）。"""
    result = self._get_next_available(role=role)
    if not result:
        raise RuntimeError("所有 LLM Provider 均不可用或处于 cooldown 中")
    provider, model, api_key = result
    return OpenAI(api_key=api_key, base_url=provider.base_url)
```

修改 `get_model_info`：

```python
def get_model_info(self, *, role: str = "generation") -> dict:
    """返回当前使用的 provider/model 信息。"""
    result = self._get_next_available(role=role)
    if not result:
        return {"provider": "", "model": "", "base_url": ""}
    provider, model, _ = result
    return {
        "provider": provider.name,
        "model": model.id,
        "base_url": provider.base_url,
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py::TestModelRoles -v`
Expected: 全部 PASS

- [ ] **Step 6: 运行全量测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_llm_client_manager.py -v`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/core/llm_client_manager.py tests/test_llm_client_manager.py
git commit -m "feat(llm): get_chat_model/get_sync_client/get_model_info 支持 role 筛选"
```

---

### Task 6: get_llm() 支持 role 参数

**Files:**
- Modify: `backend/app/agent/llm.py:25-74`

- [ ] **Step 1: 实现 — get_llm 新增 role 参数**

修改 `backend/app/agent/llm.py` 中的 `get_llm` 函数：

```python
def get_llm(*, role: str = "generation") -> BaseChatModel:
    """获取 LLM 实例（每次返回新实例以支持负载均衡）。"""
    cb = settings.circuit_breaker_config
    extra_body: dict = {}
    if not settings.ai.enable_thinking:
        extra_body["enable_thinking"] = False

    # 优先从 LLMClientManager 获取
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            llm = manager.get_chat_model(
                role=role,
                temperature=0.7,
                max_retries=cb.retry_max,
                timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
                extra_body=extra_body if extra_body else None,
            )
            info = manager.get_model_info(role=role)
            logger.debug(
                "LLM 客户端(Manager) | provider=%s | model=%s | role=%s",
                info["provider"],
                info["model"],
                role,
            )
            return llm
    except Exception as e:
        logger.warning("LLMClientManager 失败，回退 config.yaml | error=%s", e)

    # 兜底: config.yaml
    if not settings.ai_api_key:
        raise LlmNotConfiguredError(
            "AI API key 未配置。请在 providers.json 或 config.yaml 中设置。"
        )

    llm = ChatOpenAI(
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        temperature=0.7,
        streaming=True,
        max_retries=cb.retry_max,
        timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
        extra_body=extra_body if extra_body else None,
    )
    logger.debug("LLM 客户端(config.yaml兜底) | model=%s | role=%s", settings.ai_model, role)
    return llm
```

- [ ] **Step 2: 运行后端测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_tool_selector.py tests/test_llm_client_manager.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd backend && git add app/agent/llm.py
git commit -m "feat(llm): get_llm 支持 role 参数选择不同用途模型"
```

---

### Task 7: AIConfig 新增 failover_max_retries

**Files:**
- Modify: `backend/app/core/config.py:48-54`

- [ ] **Step 1: 实现 — AIConfig 新增字段**

修改 `backend/app/core/config.py` 中的 `AIConfig`：

```python
class AIConfig(BaseModel):
    model: str = "qwen3.6-flash-2026-04-16"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    enable_thinking: bool = False
    parallel_tool_calls: bool = True
    failover_max_retries: int = 3
```

- [ ] **Step 2: 验证配置加载无报错**

Run: `cd backend && poetry run python -c "from app.core.config import settings; print(settings.ai.failover_max_retries)"`
Expected: 输出 `3`

- [ ] **Step 3: 提交**

```bash
cd backend && git add app/core/config.py
git commit -m "feat(config): AIConfig 新增 failover_max_retries 配置项"
```

---

### Task 8: providers.json 添加 roles

**Files:**
- Modify: `backend/providers.json`

- [ ] **Step 1: 修改 providers.json 为模型添加 roles**

为每个模型的用途标记 `roles` 字段：

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
      "weight": 4,
      "enabled": true,
      "models": [
        {"id": "gemma4:31b", "priority": 1, "enabled": true, "roles": ["generation"]},
        {"id": "glm-4.7", "priority": 2, "enabled": true, "roles": ["all"]},
        {"id": "qwen3-next:80b", "priority": 3, "enabled": true, "roles": ["generation"]},
        {"id": "qwen3-coder-next", "priority": 4, "enabled": true, "roles": ["generation"]}
      ]
    },
    {
      "name": "nvidia",
      "base_url": "https://integrate.api.nvidia.com/v1",
      "api_keys": [
        "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"
      ],
      "priority": 2,
      "weight": 3,
      "enabled": true,
      "models": [
        {"id": "meta/llama-3.1-70b-instruct", "priority": 1, "enabled": true, "roles": ["all"]},
        {"id": "nvidia/nemotron-3-super-120b-a12b", "priority": 2, "enabled": true, "roles": ["generation"]},
        {"id": "deepseek-ai/deepseek-v4-flash", "priority": 3, "enabled": true, "roles": ["all"]},
        {"id": "zhipuai/glm-5.1", "priority": 4, "enabled": true, "roles": ["all"]}
      ]
    },
    {
      "name": "dashscope",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_keys": [
        "sk-test-placeholder"
      ],
      "priority": 3,
      "weight": 1,
      "enabled": true,
      "models": [
        {"id": "qwen3.6-flash-2026-04-16", "priority": 1, "enabled": true, "roles": ["all"]}
      ]
    }
  ]
}
```

注意：目前 ollama 没有 gemma3:12b 模型。如果要使用 tool-selection 轻量模型，需要后续在 ollama 中添加一个轻量模型（如 gemma3:12b 或 qwen3:8b），暂时通过 `"roles": ["all"]` 的 glm-4.7 / qwen3.6-flash 兼容 tool-selection 角色。

- [ ] **Step 2: 验证配置加载**

Run: `cd backend && poetry run python -c "from app.core.llm_client_manager import LLMClientManager; m = LLMClientManager(); print([(p.name, mo.id, mo.roles) for p, mo in m.chain])"`
Expected: 输出每个 provider/model 的 roles 配置

- [ ] **Step 3: 提交**

```bash
cd backend && git add providers.json
git commit -m "feat(config): providers.json 模型新增 roles 字段标记用途"
```

---

### Task 9: _get_classifier 使用轻量模型

**Files:**
- Modify: `backend/app/agent/graph.py:45-75`

- [ ] **Step 1: 实现 — _get_classifier 使用 role="tool-selection"**

修改 `backend/app/agent/graph.py` 中的 `_get_classifier` 函数：

```python
def _get_classifier() -> LLMIntentClassifier | None:
    global _classifier
    if _classifier is not None:
        return _classifier

    api_key = settings.ai_api_key
    base_url = settings.ai_base_url
    model = settings.ai_model

    # 优先从 Manager 获取轻量模型（tool-selection 角色）
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            info = manager.get_model_info(role="tool-selection")
            client = manager.get_sync_client(role="tool-selection")
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

- [ ] **Step 2: 运行测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_tool_selector.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd backend && git add app/agent/graph.py
git commit -m "feat(agent): _get_classifier 使用 tool-selection 角色轻量模型"
```

---

### Task 10: _llm_node 双阶段模型 + 重试循环

**Files:**
- Modify: `backend/app/agent/graph.py:243-389`

这是最核心的改动。将 `_llm_node` 中的 LLM 调用改为：
1. 首次调用（工具选择）使用 `role="tool-selection"`
2. 工具执行后的调用（回复生成）使用 `role="generation"`
3. 每次调用带重试循环，失败时自动切换 provider

- [ ] **Step 1: 实现 — _llm_node 双阶段模型**

修改 `backend/app/agent/graph.py` 中 `_llm_node` 的关键部分。将第 282-299 行替换为：

```python
    tools = get_langchain_tools()
    has_tool_results = bool(tool_msgs)

    # 双阶段模型：工具选择用轻量模型，回复生成用高质量模型
    llm_role = "generation" if has_tool_results else "tool-selection"
    raw_llm = get_llm(role=llm_role)
    _circuit_key = _build_circuit_key(raw_llm)
    user_msg = _find_last_human_message(messages)
    selected_names = select_tools(
        user_msg, tools, intent_classifier=_get_classifier(),
        user_location=farm_location,
    )
    if has_tool_results:
        selected_names_set = expand_by_chain(set(selected_names))
        selected_tools = [t for t in tools if t.name in selected_names_set]
    else:
        selected_tools = [t for t in tools if t.name in selected_names]
    if selected_tools:
        parallel = {"parallel_tool_calls": True} if settings.ai.parallel_tool_calls else {}
        llm = raw_llm.bind_tools(selected_tools, **parallel)
    else:
        llm = raw_llm
        logger.info("无匹配工具，LLM 直接回复（闲聊模式）")
```

- [ ] **Step 2: 实现 — LLM 调用改为重试循环**

将 `_llm_node` 中的 LLM 调用部分（约第 339-354 行）替换为重试循环：

```python
    # LLM 调用 + 计时 + 请求内重试
    start = _time.perf_counter()
    max_retries = settings.ai.failover_max_retries
    response = None

    async with _LLM_SEMAPHORE:
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    raw_llm = get_llm(role=llm_role)
                    _circuit_key = _build_circuit_key(raw_llm)
                    if selected_tools:
                        parallel = {"parallel_tool_calls": True} if settings.ai.parallel_tool_calls else {}
                        llm = raw_llm.bind_tools(selected_tools, **parallel)
                    else:
                        llm = raw_llm
                response = await llm.ainvoke([system] + messages)
                _record_llm_success(_circuit_key)
                break
            except Exception as exc:
                duration_ms = int((_time.perf_counter() - start) * 1000)
                model_name = getattr(raw_llm, "model_name", "unknown")
                _record_llm_failure(_circuit_key, exc)

                # 非可恢复错误（400 schema 错误等）不重试，直接抛出
                from app.core.llm_client_manager import classify_error, ErrorLevel
                error_level = classify_error(exc)
                if error_level == ErrorLevel.MODEL:
                    logger.warning(
                        "LLM 不可恢复错误，跳过重试 | key=%s | model=%s | level=%s",
                        _circuit_key, model_name, error_level.value,
                    )
                    collector.record(
                        node_type="llm_call",
                        node_name=model_name,
                        input_data=input_summary,
                        duration_ms=duration_ms,
                        error_message=str(exc),
                    )
                    raise

                logger.warning(
                    "LLM 重试 | attempt=%d/%d | key=%s | model=%s | latency_ms=%d | error=%s",
                    attempt + 1, max_retries, _circuit_key, model_name,
                    duration_ms, str(exc)[:120],
                )
                if attempt == max_retries - 1:
                    collector.record(
                        node_type="llm_call",
                        node_name=model_name,
                        input_data=input_summary,
                        duration_ms=duration_ms,
                        error_message=str(exc),
                    )
                    raise
```

注意：`model_name` 变量在后面的 trace 日志中也被使用（第 302 行和 370-377 行），所以需要确保 `model_name` 在重试循环后仍然可用。将第 302 行的 `model_name` 赋值移到重试循环之后：

```python
    model_name = getattr(raw_llm, "model_name", "unknown")
```

- [ ] **Step 3: 验证语法正确**

Run: `cd backend && poetry run python -c "from app.agent.graph import _llm_node; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 4: 提交**

```bash
cd backend && git add app/agent/graph.py
git commit -m "feat(agent): _llm_node 双阶段模型 + 请求内 LLM 重试循环"
```

---

### Task 11: 端到端验证

**Files:**
- 无新增文件

- [ ] **Step 1: 运行全量后端测试**

Run: `cd backend && poetry run pytest tests/ -v --timeout=30`
Expected: 全部 PASS

- [ ] **Step 2: 启动后端服务验证无启动报错**

Run: `cd backend && poetry run uvicorn app.main:app --reload --port 8000 &`
Expected: 服务正常启动，日志中出现 `LLMClientManager 初始化` 且包含 roles 信息

- [ ] **Step 3: 发送测试请求验证重试逻辑**

发送一个会触发 LLM 调用的请求，观察日志中是否出现：
- 工具选择阶段使用 tool-selection 角色模型
- 回复生成阶段使用 generation 角色模型
- 如有失败，出现 `LLM 重试` 日志

---

## 依赖关系

```
Task 1 (ErrorLevel QUOTA_EXHAUSTED)
  └── Task 2 (classify_error)
        └── Task 3 (record_failure error_level)

Task 4 (ModelConfig roles)
  └── Task 5 (get_chat_model role)
        └── Task 6 (get_llm role)
              ├── Task 9 (_get_classifier)
              └── Task 10 (_llm_node 双阶段 + 重试)

Task 7 (AIConfig failover_max_retries)
  └── Task 10 (_llm_node 重试)

Task 8 (providers.json roles)
  └── 无代码依赖（配置文件）

Task 11 (端到端验证) — 所有 Task 完成后执行
```

可并行的 Task 组：
- Task 1-3 与 Task 4-6 可并行
- Task 7、Task 8 可并行
- Task 9、Task 10 依赖 Task 6
