# LLM 并发与负载均衡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决 LLM 调用链路的三个生产阻塞问题 — 同步阻塞事件循环、请求集中到单一模型、死模型无限重试。

**Architecture:** 三阶段改造：(1) LLMClientManager 加权路由+分级熔断, (2) `_llm_node` 异步化+Semaphore 并发控制, (3) 去掉 LLM 单例缓存实现真正的负载均衡。

**Tech Stack:** Python 3.12 / asyncio / LangGraph / LangChain ChatOpenAI / pytest + pytest-asyncio

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/core/llm_client_manager.py` | 修改 | 加权路由、分级熔断、enabled/weight 字段 |
| `backend/app/agent/llm.py` | 修改 | 去掉 LLM_INSTANCE 单例缓存、删除死代码 |
| `backend/app/agent/graph.py` | 修改 | `_llm_node` 异步化 + Semaphore |
| `backend/app/agent/report.py` | 修改 | 去掉 `_REPORT_LLM` 缓存 |
| `backend/providers.json` | 修改 | 添加 weight 和 enabled 字段 |
| `backend/tests/test_llm_client_manager.py` | 修改 | 适配新数据结构、新增测试 |
| `backend/tests/test_llm.py` | 修改 | 适配非缓存 get_llm() |
| `backend/tests/test_graph_user_setting.py` | 修改 | 适配异步 _llm_node |
| `backend/tests/test_llm_load_balance.py` | 创建 | 加权路由、分级熔断、provider 健康、enabled 专项测试 |

---

### Task 1: LLMCircuitState 枚举与 CircuitEntry 数据类

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:29-53`
- Test: `backend/tests/test_llm_load_balance.py`

- [ ] **Step 1: 写失败测试 — LLMCircuitState 枚举与 CircuitEntry**

```python
# backend/tests/test_llm_load_balance.py
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py -v`
Expected: FAIL — `ImportError: cannot import name 'LLMCircuitState'`

- [ ] **Step 3: 实现 LLMCircuitState 枚举与 CircuitEntry**

在 `backend/app/core/llm_client_manager.py` 中，在 `ErrorLevel` 枚举之后（约 line 33）添加：

```python
class LLMCircuitState(Enum):
    """LLM Provider/Model 熔断状态。"""
    COOLING = "cooling"
    WARMING = "warming"
    DEAD = "dead"


@dataclass
class CircuitEntry:
    """熔断条目 — 替代旧的 CooldownEntry。"""
    failures: int = 0
    until: datetime = field(default_factory=datetime.now)
    cooldown_minutes: int = 0
    state: LLMCircuitState = LLMCircuitState.COOLING
```

同时保留旧的 `CooldownEntry` 不删除（后续 Task 会替换引用后删除）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestCircuitEntry -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm_client_manager.py backend/tests/test_llm_load_balance.py
git commit -m "feat(llm): 新增 LLMCircuitState 枚举与 CircuitEntry 数据类"
```

---

### Task 2: ProviderConfig/ModelConfig 新增 weight 和 enabled 字段

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:34-47`
- Test: `backend/tests/test_llm_load_balance.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_llm_load_balance.py` 追加：

```python
import json
from pathlib import Path

from app.core.llm_client_manager import LLMClientManager


def _write_cfg(path: Path, data: dict):
    path.write_text(json.dumps(data))


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestWeightEnabledFields -v`
Expected: FAIL — `AttributeError: 'ProviderConfig' has no attribute 'weight'`

- [ ] **Step 3: 实现 weight 和 enabled 字段**

修改 `backend/app/core/llm_client_manager.py` 中的数据类：

```python
@dataclass
class ModelConfig:
    id: str
    priority: int = 1
    enabled: bool = True


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_keys: list[str]
    priority: int = 99
    weight: int = 1
    enabled: bool = True
    models: list[ModelConfig] = field(default_factory=list)
```

在 `_load_config` 方法中（约 line 109-121），解析新字段并过滤 disabled：

```python
    def _load_config(self, path: str) -> None:
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(
                "providers.json 加载失败，使用 config.yaml 兜底 | error=%s", e
            )
            self.fallback_mode = True
            return

        providers_raw = data.get("providers", [])
        if not providers_raw:
            logger.warning("providers.json 中无 provider，使用 config.yaml 兜底")
            self.fallback_mode = True
            return

        default_name = data.get("default_provider", "")

        for p_raw in providers_raw:
            if not p_raw.get("enabled", True):
                continue
            provider = ProviderConfig(
                name=p_raw["name"],
                base_url=p_raw["base_url"],
                api_keys=p_raw.get("api_keys", []),
                priority=p_raw.get("priority", 99),
                weight=p_raw.get("weight", 1),
                enabled=p_raw.get("enabled", True),
                models=[
                    ModelConfig(
                        id=m["id"],
                        priority=m.get("priority", 1),
                        enabled=m.get("enabled", True),
                    )
                    for m in p_raw.get("models", [])
                    if m.get("enabled", True)
                ],
            )
            for model in sorted(provider.models, key=lambda m: m.priority):
                self._chain.append((provider, model))

        self._chain.sort(key=lambda item: (item[0].priority, item[1].priority))

        if default_name:
            default_chain = [
                pair for pair in self._chain if pair[0].name == default_name
            ]
            rest_chain = [
                pair for pair in self._chain if pair[0].name != default_name
            ]
            self._chain = default_chain + rest_chain
        logger.info(
            "LLMClientManager 初始化 | providers=%d | models=%d",
            len({p.name for p, _ in self._chain}),
            len(self._chain),
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestWeightEnabledFields -v`
Expected: PASS

- [ ] **Step 5: 确认已有测试不回归**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_client_manager.py -v`
Expected: PASS（向后兼容，缺省值正确）

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/llm_client_manager.py backend/tests/test_llm_load_balance.py
git commit -m "feat(llm): ProviderConfig/ModelConfig 新增 weight/enabled 字段"
```

---

### Task 3: 分级熔断 — record_failure 状态升级

**Files:**
- Modify: `backend/app/core/llm_client_manager.py` (`record_failure`, `is_cooled_down`)
- Test: `backend/tests/test_llm_load_balance.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_llm_load_balance.py` 追加：

```python
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
        # 即使时间过去，DEAD 也应返回 True
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestTieredCircuit -v`
Expected: FAIL — 现有 `record_failure` 使用 `CooldownEntry` 而非 `CircuitEntry`

- [ ] **Step 3: 实现分级熔断逻辑**

替换 `backend/app/core/llm_client_manager.py` 中的 `record_failure` 和 `is_cooled_down`：

```python
    def record_failure(self, key: str) -> None:
        """记录失败并分级升级熔断状态。"""
        entry = self._cooldowns.get(key, CircuitEntry())
        entry.failures += 1

        if entry.failures >= 10:
            entry.state = LLMCircuitState.DEAD
            entry.cooldown_minutes = 0
        elif entry.failures >= 4:
            entry.state = LLMCircuitState.WARMING
            entry.cooldown_minutes = 1440  # 24h
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

    def is_cooled_down(self, key: str) -> bool:
        """检查是否仍在 cooldown 期内（DEAD 永久返回 True）。"""
        entry = self._cooldowns.get(key)
        if not entry:
            return False
        if entry.state == LLMCircuitState.DEAD:
            return True
        return datetime.now() < entry.until
```

注意：将 `self._cooldowns` 字典中的值类型从 `CooldownEntry` 统一替换为 `CircuitEntry`。`_cooldowns` 类型保持 `dict[str, CircuitEntry]`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestTieredCircuit -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm_client_manager.py backend/tests/test_llm_load_balance.py
git commit -m "feat(llm): 分级熔断 COOLING→WARMING→DEAD 状态升级"
```

---

### Task 4: Provider 健康检查与加权路由

**Files:**
- Modify: `backend/app/core/llm_client_manager.py` (`_is_provider_healthy`, `_weighted_random_choice`, `_get_next_available`)
- Test: `backend/tests/test_llm_load_balance.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_llm_load_balance.py` 追加：

```python
import random


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
        # ollama weight=8/11≈73%, 允许 ±10%
        assert 630 < counts["ollama"] < 830, f"ollama: {counts['ollama']}"
        assert 100 < counts["nvidia"] < 300, f"nvidia: {counts['nvidia']}"
        assert 50 < counts["dashscope"] < 200, f"dashscope: {counts['dashscope']}"

    def test_skips_dead_models(self, tmp_path):
        """DEAD 模型被永久跳过。"""
        mgr = self._make_multi_manager(tmp_path)
        # 将 ollama 标记为 DEAD
        mgr.record_failure("ollama/gemma3:12b")
        for _ in range(9):
            mgr.record_failure("ollama/gemma3:12b")
        assert mgr._cooldowns["ollama/gemma3:12b"].state == LLMCircuitState.DEAD

        for _ in range(20):
            result = mgr._get_next_available()
            assert result is not None
            assert result[0].name != "ollama"

    def test_skips_cooled_down_models(self, tmp_path):
        """COOLING 中的模型被跳过。"""
        mgr = self._make_multi_manager(tmp_path)
        mgr.record_failure("nvidia/llama-3.1-70b")
        assert mgr.is_cooled_down("nvidia/llama-3.1-70b")

        for _ in range(20):
            result = mgr._get_next_available()
            assert result is not None
            assert result[0].name != "nvidia"

    def test_all_dead_returns_none(self, tmp_path):
        """所有模型 DEAD 时返回 None。"""
        mgr = self._make_multi_manager(tmp_path)
        for key in ["ollama/gemma3:12b", "nvidia/llama-3.1-70b", "dashscope/qwen"]:
            for _ in range(10):
                mgr.record_failure(key)
        assert mgr._get_next_available() is None

    def test_returns_none_when_no_api_keys(self, tmp_path):
        """Provider 无 API key 时返回 None。"""
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
        """Provider 下 ≥50% 模型 WARMING/DEAD 时整个 provider 被跳过。"""
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
        # m1 标记为 DEAD
        for _ in range(10):
            mgr.record_failure("test/m1")
        # 2 个模型中 1 个 DEAD = 50%，provider 不健康
        assert mgr._is_provider_healthy("test") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestWeightedRouting tests/test_llm_load_balance.py::TestProviderHealth -v`
Expected: FAIL — `AttributeError: 'LLMClientManager' has no attribute '_get_next_available'`

- [ ] **Step 3: 实现 _is_provider_healthy、_weighted_random_choice、_get_next_available**

在 `backend/app/core/llm_client_manager.py` 的 `LLMClientManager` 类中添加新方法，并替换 `_get_first_available`：

```python
    def _is_provider_healthy(self, provider_name: str) -> bool:
        """检查 provider 是否健康（<50% 模型处于 WARMING/DEAD）。"""
        provider_models = [
            m for p, m in self._chain if p.name == provider_name
        ]
        if not provider_models:
            return True
        bad_count = 0
        for m in provider_models:
            key = f"{provider_name}/{m.id}"
            entry = self._cooldowns.get(key)
            if entry and entry.state in (LLMCircuitState.WARMING, LLMCircuitState.DEAD):
                bad_count += 1
        return bad_count < len(provider_models) / 2

    def _weighted_random_choice(
        self, candidates: list[tuple[ProviderConfig, ModelConfig, str, int]]
    ) -> tuple[ProviderConfig, ModelConfig, str] | None:
        """按权重随机选择一个候选。"""
        if not candidates:
            return None
        total = sum(w for _, _, _, w in candidates)
        r = __import__("random").random() * total
        cumulative = 0
        for provider, model, api_key, weight in candidates:
            cumulative += weight
            if r <= cumulative:
                return provider, model, api_key
        return candidates[-1][:3]

    def _get_next_available(
        self,
    ) -> tuple[ProviderConfig, ModelConfig, str] | None:
        """获取下一个可用的 provider+model+key（加权随机）。"""
        seen_providers: set[str] = set()
        candidates: list[tuple[ProviderConfig, ModelConfig, str, int]] = []

        for provider, model in self._chain:
            if not provider.enabled or not model.enabled:
                continue
            if not provider.api_keys:
                continue
            model_key = f"{provider.name}/{model.id}"
            if self.is_cooled_down(model_key):
                continue
            if not self._is_provider_healthy(provider.name):
                continue
            # 每个 provider 只取第一个可用模型（按 priority 已排序）
            if provider.name in seen_providers:
                continue
            seen_providers.add(provider.name)
            api_key = self._get_api_key(provider)
            if not api_key:
                continue
            candidates.append((provider, model, api_key, provider.weight))

        return self._weighted_random_choice(candidates)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestWeightedRouting tests/test_llm_load_balance.py::TestProviderHealth -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm_client_manager.py backend/tests/test_llm_load_balance.py
git commit -m "feat(llm): 加权随机路由 + Provider 健康检查 + _get_next_available"
```

---

### Task 5: 将 get_chat_model/get_sync_client/get_async_client/get_model_info 接入 _get_next_available

**Files:**
- Modify: `backend/app/core/llm_client_manager.py:165-211`
- Test: `backend/tests/test_llm_load_balance.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_llm_load_balance.py` 追加：

```python
class TestGetMethodIntegration:
    """测试 get_chat_model / get_sync_client / get_async_client 使用 _get_next_available。"""

    def _make_manager(self, tmp_path) -> LLMClientManager:
        cfg = {
            "providers": [
                {
                    "name": "p1",
                    "base_url": "http://p1",
                    "api_keys": ["k1"],
                    "priority": 1,
                    "weight": 1,
                    "models": [{"id": "m1", "priority": 1}],
                },
                {
                    "name": "p2",
                    "base_url": "http://p2",
                    "api_keys": ["k2"],
                    "priority": 2,
                    "weight": 1,
                    "models": [{"id": "m2", "priority": 1}],
                },
            ]
        }
        p = tmp_path / "providers.json"
        _write_cfg(p, cfg)
        return LLMClientManager(config_path=str(p))

    def test_get_model_info_uses_next_available(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        __import__("random").seed(42)
        info = mgr.get_model_info()
        # 应该是 p1 或 p2 之一（不再总是第一个）
        assert info["provider"] in ("p1", "p2")
```

- [ ] **Step 2: 运行测试确认失败或通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestGetMethodIntegration -v`
Expected: 可能 PASS（如果旧 `_get_first_available` 恰好也命中 p1），但需确认代码确实调用了 `_get_next_available`

- [ ] **Step 3: 替换所有 get_* 方法中的 `_get_first_available` → `_get_next_available`**

在 `backend/app/core/llm_client_manager.py` 中，将以下 4 个方法中的 `_get_first_available()` 全部替换为 `_get_next_available()`：

- `get_chat_model()` (line ~165)
- `get_sync_client()` (line ~185)
- `get_async_client()` (line ~193)
- `get_model_info()` (line ~201)

用 Edit 工具做 `replace_all`：
- 旧: `self._get_first_available()`
- 新: `self._get_next_available()`

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_client_manager.py tests/test_llm_load_balance.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm_client_manager.py backend/tests/test_llm_load_balance.py
git commit -m "refactor(llm): get_* 方法接入 _get_next_available 加权路由"
```

---

### Task 6: reload() 重置 DEAD 状态 + 清理旧 CooldownEntry

**Files:**
- Modify: `backend/app/core/llm_client_manager.py` (`reload`, 删除 `CooldownEntry`)
- Test: `backend/tests/test_llm_load_balance.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_llm_load_balance.py` 追加：

```python
class TestReloadResetsDead:
    """测试 reload() 重置 DEAD 状态。"""

    def test_reload_clears_dead_state(self, tmp_path):
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
        mgr = LLMClientManager(config_path=str(p))

        # 标记为 DEAD
        for _ in range(10):
            mgr.record_failure("test/m1")
        assert mgr._cooldowns["test/m1"].state == LLMCircuitState.DEAD

        mgr.reload()
        assert "test/m1" not in mgr._cooldowns
        assert mgr._get_next_available() is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestReloadResetsDead -v`
Expected: FAIL — `reload()` 只清 `_chain` 和 `_key_counters`，不清 `_cooldowns`

- [ ] **Step 3: 修改 reload() 清空 _cooldowns**

在 `backend/app/core/llm_client_manager.py` 的 `reload()` 方法中（约 line 241-249），添加 `self._cooldowns.clear()`：

```python
    def reload(self) -> None:
        """热更新：重新加载 providers.json，重置熔断状态。"""
        path = str(Path(__file__).parent.parent.parent / "providers.json")
        self._chain.clear()
        self._key_counters.clear()
        self._cooldowns.clear()
        self.fallback_mode = False
        self._load_config(path)
        logger.info("LLMClientManager 热更新完成 | providers=%d | models=%d",
                     len({p.name for p, _ in self._chain}), len(self._chain))
```

同时删除旧的 `CooldownEntry` dataclass（如果不再被任何地方引用）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestReloadResetsDead -v`
Expected: PASS

- [ ] **Step 5: 运行已有测试确认不回归**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_client_manager.py -v`
Expected: PASS（旧的 `TestCooldown` 中 `test_first_failure_cooldown_2min` 等会因 `CooldownEntry` 被替换需要检查，如果仍使用 `entry.failures`/`entry.cooldown_minutes` 属性则 `CircuitEntry` 兼容）

如果 `TestCooldown` 中访问了 `CooldownEntry` 类型，需将 import 更新为 `CircuitEntry`。在 `test_llm_client_manager.py` 中：

```python
# 将 from app.core.llm_client_manager import (..., CooldownEntry) 替换：
# 如果 test_llm_client_manager.py 没有直接 import CooldownEntry，则无需改动
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/llm_client_manager.py backend/tests/test_llm_load_balance.py backend/tests/test_llm_client_manager.py
git commit -m "feat(llm): reload() 重置 DEAD 熔断状态，清理旧 CooldownEntry"
```

---

### Task 7: 去掉 get_llm() 的 LLM_INSTANCE 单例缓存 + 删除死代码

**Files:**
- Modify: `backend/app/agent/llm.py`
- Modify: `backend/app/core/llm_client_manager.py` (watcher/reload_llm_config 中 `LLM_INSTANCE = None` 引用)
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_llm.py` 中添加测试：

```python
class TestGetLlmNoCaching:
    """验证 get_llm() 不再缓存 LLM_INSTANCE。"""

    @patch("app.core.llm_client_manager.get_llm_manager")
    @patch("app.agent.llm.settings")
    def test_get_llm_returns_fresh_instance_each_call(self, mock_settings, mock_get_manager):
        """每次调用 get_llm() 都返回新实例。"""
        mock_settings.circuit_breaker_config = MagicMock(
            retry_max=1, retry_backoff_base=1
        )
        mock_settings.ai = MagicMock(enable_thinking=True)

        mock_manager = MagicMock()
        mock_manager.fallback_mode = False
        mock_manager.get_model_info.return_value = {
            "provider": "ollama", "model": "m1", "base_url": "http://test"
        }
        mock_llm_1 = MagicMock()
        mock_llm_2 = MagicMock()
        mock_manager.get_chat_model.side_effect = [mock_llm_1, mock_llm_2]
        mock_get_manager.return_value = mock_manager

        _reset_llm_singletons()

        from app.agent.llm import get_llm

        llm_1 = get_llm()
        llm_2 = get_llm()
        assert llm_1 is mock_llm_1
        assert llm_2 is mock_llm_2
        assert mock_manager.get_chat_model.call_count == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm.py::TestGetLlmNoCaching -v`
Expected: FAIL — 第二次调用 `get_llm()` 返回缓存的第一次结果，`call_count` 仍为 1

- [ ] **Step 3: 重写 get_llm() 为非缓存版本 + 删除死代码**

将 `backend/app/agent/llm.py` 整体重写为：

```python
"""LLM 客户端封装，使用 LangChain ChatOpenAI。"""

import logging

import langchain

for _attr in ("verbose", "debug", "llm_cache"):
    if not hasattr(langchain, _attr):
        setattr(langchain, _attr, False)

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from app.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)


class LlmNotConfiguredError(Exception):
    """LLM 未配置错误。"""

    pass


def get_llm() -> BaseChatModel:
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
                temperature=0.7,
                max_retries=cb.retry_max,
                timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
                extra_body=extra_body if extra_body else None,
            )
            info = manager.get_model_info()
            logger.debug(
                "LLM 客户端(Manager) | provider=%s | model=%s",
                info["provider"],
                info["model"],
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
        max_retries=cb.retry_max,
        timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
        extra_body=extra_body if extra_body else None,
    )
    logger.debug("LLM 客户端(config.yaml兜底) | model=%s", settings.ai_model)
    return llm


__all__ = ["get_llm"]
```

关键变更：
- 删除 `LLM_INSTANCE` 全局变量
- 删除 `_BREAKER`、`_get_breaker()`、`llm_invoke_with_breaker()`
- 删除 `from app.infra.circuit_breaker import CircuitBreaker, call_with_retry`
- `get_llm()` 不再缓存，每次返回新实例
- 日志从 `info` 降为 `debug`（高频调用时避免日志洪泛）

- [ ] **Step 4: 清理 llm_client_manager.py 中对 LLM_INSTANCE 的引用**

在 `backend/app/core/llm_client_manager.py` 的 `start_file_watcher`（约 line 271-272）和 `reload_llm_config`（约 line 302-303）中，删除 `llm_module.LLM_INSTANCE = None` 行。

`start_file_watcher` 中的 `_watch` 函数简化为：

```python
        def _watch():
            logger.info("providers.json 文件监听已启动 | path=%s", config_path)
            for changes in _watchfiles_watch(config_path.parent):
                for _change_type, changed_path in changes:
                    if Path(changed_path).name == config_path.name:
                        logger.info("检测到 providers.json 变化，执行热更新")
                        self.reload()
```

`reload_llm_config` 简化为：

```python
def reload_llm_config() -> dict:
    """热更新 LLM 配置。"""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.reload()
        else:
            _manager = LLMClientManager()

    info = _manager.get_model_info()
    logger.info("LLM 配置热更新 | provider=%s | model=%s", info["provider"], info["model"])
    return info
```

- [ ] **Step 5: 更新 test_llm.py 的 _reset_llm_singletons**

在 `backend/tests/test_llm.py` 中，`_reset_llm_singletons` 不再需要重置 `LLM_INSTANCE`：

```python
def _reset_llm_singletons():
    """重置 llm_client_manager.py 的单例。"""
    import app.core.llm_client_manager as mgr_module
    mgr_module._manager = None
```

同时删除 `test_llm.py` 中对 `LLM_INSTANCE` 的任何直接引用。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/agent/llm.py backend/app/core/llm_client_manager.py backend/tests/test_llm.py
git commit -m "refactor(llm): 去掉 LLM_INSTANCE 单例缓存，删除死代码 llm_invoke_with_breaker"
```

---

### Task 8: _llm_node 异步化 + Semaphore

**Files:**
- Modify: `backend/app/agent/graph.py` (`_llm_node`, `compile_advisor_graph`)
- Modify: `backend/tests/test_graph_user_setting.py`
- Test: `backend/tests/test_llm_load_balance.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_llm_load_balance.py` 追加：

```python
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock


class TestLlmNodeAsync:
    """测试 _llm_node 异步化。"""

    @pytest.mark.asyncio
    async def test_llm_node_is_async(self, tmp_path):
        """_llm_node 应该是协程函数。"""
        from app.agent.graph import _llm_node
        assert asyncio.iscoroutinefunction(_llm_node)

    @pytest.mark.asyncio
    async def test_llm_node_calls_ainvoke(self):
        """_llm_node 应调用 llm.ainvoke 而非 llm.invoke。"""
        with (
            patch("app.agent.graph.get_llm") as mock_get_llm,
            patch("app.agent.graph.get_langchain_tools", return_value=[]),
            patch("app.agent.graph.get_registry"),
            patch("app.agent.graph.render_prompt", return_value="sys"),
            patch("app.agent.graph.get_collector") as mock_collector,
            patch("app.agent.graph.get_request_date", return_value=__import__("datetime").date(2026, 5, 29)),
            patch("app.agent.graph.check_quota", return_value=True),
            patch("app.agent.graph.select_tools", return_value=[]),
            patch("app.agent.graph._get_classifier", return_value=None),
            patch("app.agent.graph.SessionLocal") as mock_session,
            patch("app.agent.graph.farm_context_service"),
        ):
            mock_collector.return_value = MagicMock()
            mock_session.return_value = MagicMock()

            llm = AsyncMock()
            llm.model_name = "test"
            llm.bind_tools.return_value = llm
            llm.ainvoke = AsyncMock(return_value=MagicMock(
                content="回复",
                tool_calls=[],
                response_metadata={"token_usage": {"total_tokens": 10}},
            ))
            mock_get_llm.return_value = llm

            from app.agent.graph import _llm_node
            state = {"messages": [], "farm_id": 1}
            result = await _llm_node(state)

            llm.ainvoke.assert_called_once()
            assert "messages" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestLlmNodeAsync -v`
Expected: FAIL — `_llm_node` 不是 async

- [ ] **Step 3: 将 _llm_node 改为 async + Semaphore**

在 `backend/app/agent/graph.py` 中：

1. 在文件顶部（约 line 40-41 附近）添加信号量：

```python
_LLM_SEMAPHORE = asyncio.Semaphore(5)
```

2. 将 `_llm_node` 函数签名改为 `async def`，并将 `llm.invoke([system] + messages)` 改为 `await llm.ainvoke([system] + messages)`：

```python
async def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — async，带 Semaphore 并发控制。"""
    messages = state["messages"]

    pending_msgs = [m for m in messages if is_pending_tool_message(m)]
    if pending_msgs:
        confirm = pending_msgs[-1].content.replace(PENDING_MARKER, "").strip()
        logger.info("检测到 pending ToolMessage，跳过 LLM 直接确认 | text=%s", confirm)
        return {"messages": [AIMessage(content=confirm)]}

    tools = get_langchain_tools()
    raw_llm = get_llm()
    has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
    if has_tool_results:
        selected_tools = tools
    else:
        user_msg = _find_last_human_message(messages)
        selected_names = select_tools(
            user_msg, tools, intent_classifier=_get_classifier()
        )
        selected_tools = [t for t in tools if t.name in selected_names]
    if selected_tools:
        llm = raw_llm.bind_tools(selected_tools)
    else:
        llm = raw_llm
        logger.info("无匹配工具，LLM 直接回复（闲聊模式）")
    model_name = getattr(raw_llm, "model_name", "unknown")
    _round_idx = increment_round()
    collector = get_collector()

    farm_id = state.get("farm_id", 1)

    # 获取农场上下文摘要和用户称呼
    db = SessionLocal()
    try:
        farm_context_summary = farm_context_service.build_summary(db, farm_id=farm_id)
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        display_name = "农友"
        user_city = ""
        if farm and farm.user_id:
            user = db.query(User).filter(User.id == farm.user_id).first()
            if user:
                display_name = user.nickname
            user_setting = (
                db.query(UserSetting)
                .filter(UserSetting.user_id == farm.user_id)
                .first()
            )
            if user_setting and user_setting.default_city:
                user_city = user_setting.default_city
        farm_location = user_city or (farm.location if farm and farm.location else "")
    except Exception:
        logger.warning("获取农场上下文失败，使用默认值", exc_info=True)
        farm_context_summary = ""
        display_name = "农友"
        farm_location = ""
    finally:
        db.close()

    current_date = get_request_date()
    current_season = _get_season(current_date)
    system_text = render_prompt(
        "system_base",
        variables={
            "farm_context_summary": farm_context_summary,
            "display_name": display_name,
            "farm_location": farm_location,
            "current_season": current_season,
        },
        registry=get_registry(),
        current_date=current_date,
    )

    collector.record(
        node_type="prompt_render",
        node_name="system_prompt",
        input_data={"template": "system_base", "variables_count": 2},
        output_data=system_text[:2000],
    )

    system = HumanMessage(content=system_text)
    messages = micro_compact(state["messages"])
    input_summary = _find_last_human_message(state["messages"])[:200]

    if not check_quota(farm_id=farm_id):
        action = settings.token_quota.over_quota_action
        if action == "reject":
            logger.warning("Token 配额超限，拒绝调用（reject 模式）")
            return {"messages": [AIMessage(content="今日用量已达上限，明天再来吧。")]}
        elif action == "warn":
            logger.warning("Token 配额超限，继续调用（warn 模式）")

    start = _time.perf_counter()
    async with _LLM_SEMAPHORE:
        try:
            response = await llm.ainvoke([system] + messages)
        except Exception as exc:
            duration_ms = int((_time.perf_counter() - start) * 1000)
            collector.record(
                node_type="llm_call",
                node_name=model_name,
                input_data=input_summary,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    duration_ms = int((_time.perf_counter() - start) * 1000)

    tokens = _extract_tokens_used(response)
    token_usage = None
    if tokens is not None:
        usage_meta = response.response_metadata.get("token_usage", {})
        token_usage = {
            "prompt_tokens": usage_meta.get("prompt_tokens", 0),
            "completion_tokens": usage_meta.get("completion_tokens", 0),
            "total_tokens": tokens,
        }

    if response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        logger.info("LLM 工具选择 | tool_calls=%s | model=%s", tool_names, model_name)
        output_summary = f"tool_calls: {tool_names}"
    else:
        content = response.content or ""
        logger.info("LLM 直接回复 | reply_len=%d | model=%s", len(content), model_name)
        output_summary = content[:200]

    collector.record(
        node_type="llm_call",
        node_name=model_name,
        input_data=input_summary,
        output_data=output_summary,
        duration_ms=duration_ms,
        token_usage=token_usage,
    )

    return {"messages": [response]}
```

- [ ] **Step 4: 更新 test_graph_user_setting.py 适配异步**

将 `backend/tests/test_graph_user_setting.py` 中的 `_run_llm_node` 改为异步：

```python
import pytest


async def _run_llm_node(mock_render, *query_results):
    """运行 _llm_node 并返回 render_prompt 的 variables。"""
    mock_session = _build_mock_session(*query_results)
    with patch("app.agent.graph.SessionLocal", return_value=mock_session):
        state = {"messages": [], "farm_id": 1}
        await _llm_node(state)
    _, kwargs = mock_render.call_args
    return kwargs["variables"]
```

所有测试方法加上 `@pytest.mark.asyncio` 并 `await _run_llm_node(...)`：

```python
    @pytest.mark.asyncio
    async def test_user_setting_city_takes_priority(self, mock_env):
        farm = _FakeFarm(user_id="u1", location="旧农场地址")
        user = _FakeUser(nickname="张三")
        user_setting = _FakeUserSetting(default_city="广州")
        variables = await _run_llm_node(mock_env, farm, user, user_setting)
        assert variables["farm_location"] == "广州"
```

（其他测试方法同理加上 `@pytest.mark.asyncio` + `async def` + `await`）

同时 `mock_env` fixture 中的 `llm.invoke.return_value` 需要改为 `llm.ainvoke = AsyncMock(return_value=...)`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_llm_load_balance.py::TestLlmNodeAsync tests/test_graph_user_setting.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/graph.py backend/tests/test_graph_user_setting.py backend/tests/test_llm_load_balance.py
git commit -m "feat(llm): _llm_node 异步化 + Semaphore(5) 并发控制"
```

---

### Task 9: 更新 report.py — 去掉 _REPORT_LLM 缓存

**Files:**
- Modify: `backend/app/agent/report.py:17-26`
- Test: 无需新增（report.py 已有异步 ainvoke，只是去掉缓存）

- [ ] **Step 1: 修改 report.py**

将 `backend/app/agent/report.py` 中 `_REPORT_LLM` 缓存去掉，每次调用获取新的 LLM 实例：

```python
"""报告 Agent 封装，生成种植周期周报/月报。"""

import logging
import time

from langchain_core.messages import HumanMessage

from app.agent.guardrails import filter_output
from app.agent.llm import get_llm
from app.agent.prompt_registry import get_registry
from app.agent.prompt_renderer import render_prompt
from app.core.date_context import get_request_date
from app.agent.skills import get_langchain_tools

logger = logging.getLogger(__name__)


def _get_report_llm():
    """获取绑定了工具的报告 LLM 实例（每次返回新实例）。"""
    tools = get_langchain_tools()
    return get_llm().bind_tools(tools)


async def generate_cycle_report(cycle_id: int) -> str:
    """生成指定种植周期的综合报告。"""
    start = time.perf_counter()
    logger.info("报告生成开始 | type=cycle | cycle_id=%d", cycle_id)
    llm = _get_report_llm()
    prompt = (
        f"请为 ID={cycle_id} 的种植周期生成一份综合报告。"
        "请查询该周期的基本信息、最近农事记录和成本收支，"
        "整理成一份包含进度、成本分析和下一步建议的报告。"
    )
    current_date = get_request_date()
    system_text = render_prompt(
        "report", registry=get_registry(), current_date=current_date
    )
    system = HumanMessage(content=system_text)
    response = await llm.ainvoke(
        [system, HumanMessage(content=prompt)],
        config={"run_name": "cycle_report", "metadata": {"cycle_id": cycle_id}},
    )
    result = filter_output(response.content)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info("报告生成完成 | len=%d | duration_ms=%d", len(result), duration_ms)
    return result


__all__ = ["generate_cycle_report"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agent/report.py
git commit -m "refactor(llm): report.py 去掉 _REPORT_LLM 缓存，每次获取新实例"
```

---

### Task 10: 更新 providers.json 添加 weight 和 enabled 字段

**Files:**
- Modify: `backend/providers.json`

- [ ] **Step 1: 更新 providers.json**

为每个 provider 添加 `weight` 和 `enabled` 字段，为每个 model 添加 `enabled` 字段。

注意：`providers.json` 包含 API keys，不要在 commit message 或输出中暴露。

在 `backend/providers.json` 的每个 provider 对象中添加：
- `"weight": <值>` (ollama: 8, nvidia: 2, dashscope: 1)
- `"enabled": true`
- 每个 model 添加 `"enabled": true`

- [ ] **Step 2: 验证 LLMClientManager 正常加载**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run python -c "from app.core.llm_client_manager import LLMClientManager; m = LLMClientManager(); print(f'providers={len(set(p.name for p,_ in m.chain))} models={len(m.chain)}'); print(m.get_model_info())"`

Expected: 正常输出 provider/model 信息，无报错

- [ ] **Step 3: Commit**

```bash
git add backend/providers.json
git commit -m "feat(llm): providers.json 添加 weight/enabled 字段"
```

---

### Task 11: 全量测试 + 清理

**Files:**
- 可能需要修复的测试文件

- [ ] **Step 1: 运行全量测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/ -v --tb=short 2>&1 | tail -50`
Expected: 全部 PASS

- [ ] **Step 2: 检查是否有其他文件引用 `LLM_INSTANCE` 或 `llm_invoke_with_breaker`**

Run: `cd /Users/ljn/Documents/demo/explore && grep -rn "LLM_INSTANCE\|llm_invoke_with_breaker" backend/ --include="*.py" | grep -v __pycache__ | grep -v ".pyc"`
Expected: 无结果（全部清理干净）

- [ ] **Step 3: 检查 `circuit_breaker.py` 是否仍有调用方**

Run: `cd /Users/ljn/Documents/demo/explore && grep -rn "from app.infra.circuit_breaker import\|circuit_breaker" backend/app/ --include="*.py" | grep -v __pycache__`
Expected: 仅 `circuit_breaker.py` 自身和可能的 `__init__.py` 导出。如果 `llm.py` 已删除引用，不应再有其他调用方。

- [ ] **Step 4: 修复所有失败的测试（如有）**

根据 Step 1 的输出修复。

- [ ] **Step 5: 最终全量测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "test(llm): 全量测试通过，清理残留引用"
```

---

## Self-Review Checklist

### 1. Spec 覆盖度

| Spec 要求 | 对应 Task |
|-----------|----------|
| `_llm_node` 改为 async + Semaphore(5) | Task 8 |
| `get_llm()` 不再缓存，每次返回新实例 | Task 7 |
| 加权随机路由 `_get_next_available()` | Task 4, 5 |
| `_weighted_random_choice()` | Task 4 |
| 分级熔断 COOLING/WARMING/DEAD | Task 3 |
| Provider 健康（≥50% 故障跳过） | Task 4 |
| `enabled` 字段 (provider + model) | Task 2 |
| `weight` 字段 | Task 2 |
| `reload()` 重置 DEAD | Task 6 |
| `report.py` 去缓存 | Task 9 |
| `providers.json` 更新 | Task 10 |
| 删除死代码 `llm_invoke_with_breaker` | Task 7 |
| 全量测试通过 | Task 11 |

### 2. Placeholder 扫描

无 TBD / TODO / "implement later" / "add appropriate error handling" 等。

### 3. 类型一致性

- `CircuitEntry` 在 Task 1 定义，Task 3/4/5/6 统一使用
- `_get_next_available()` 返回 `tuple[ProviderConfig, ModelConfig, str] | None`，所有调用方兼容
- `LLMCircuitState` 枚举值与 `CooldownEntry` 旧字段不冲突（`CircuitEntry` 是新数据类）
- `_llm_node` 从 `def` 变为 `async def`，所有调用方（LangGraph graph + 测试）已适配
