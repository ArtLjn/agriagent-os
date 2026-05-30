## Context

当前 LLM 调用架构：

```
config.yaml                    model_list.json
  ai.api_key                     Ollama (2 keys, 9 models)
  ai.base_url                    NVIDIA (1 key, 9 models)
  ai.model                       DashScope (1 key, 3 models)
       │                              │
       │         ← 运行时不读取 ──────┘
       ▼
  settings.ai_api_key / ai_base_url / ai_model
       │
       ├─▶ llm.py         → ChatOpenAI(settings.ai_api_key, ...)
       ├─▶ graph.py       → LLMIntentClassifier(settings.ai_api_key, ...)
       ├─▶ tool_selector  → OpenAI(settings.ai_api_key, ...)  (在 graph.py 的 _get_classifier 中)
       └─▶ skills/__init__→ AsyncOpenAI(settings.ai_api_key, ...)
```

4 个调用点各自独立实例化，硬绑 DashScope 单一 provider，无 fallback。

所有 LLM provider 均兼容 OpenAI 协议，切换只需改 `api_key` / `base_url` / `model` 三个参数。

## Goals / Non-Goals

**Goals:**
- 重新设计 `providers.json` 作为运行时配置，定义 provider 优先级、模型列表、API key 轮换
- 实现 `LLMClientManager` 统一管理所有 LLM 客户端
- 智能错误分类 fallback：Provider 级错误跳 provider，模型级错误先换模型
- 指数退避 cooldown（base=2min，max=24h），成功重置
- 4 个调用点全部接入 Manager
- config.yaml 作为兜底（providers.json 不存在或所有 provider 不可用时）

**Non-Goals:**
- 不做 Admin CRUD 端点（单用户场景，改配置文件重启即可）
- 不做数据库存储（配置文件足够）
- 不做密钥加密（单用户本地部署，gitignore 管理即可）
- 不管理天气/非 LLM 第三方 API（QWeather 等接口定制，放 DB 也无法通用）
- 不做 Admin 路由鉴权修复（独立问题，单独处理）

## Decisions

### D1: 配置文件格式

**选择**: 新建 `providers.json`，运行时读取。

```json
{
  "default_provider": "ollama",
  "providers": [
    {
      "name": "ollama",
      "base_url": "https://ollama.com/v1",
      "api_keys": ["key1", "key2"],
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
      "api_keys": ["nvapi-xxx"],
      "priority": 2,
      "models": [
        {"id": "meta/llama-3.1-70b-instruct", "priority": 1},
        {"id": "zhipuai/glm-5.1", "priority": 2}
      ]
    }
  ]
}
```

**备选方案**:
- A) 继续用 `model_list.json` → 格式冗余（notes/status/recommended），不适合运行时
- B) YAML 格式 → JSON 解析更简单，避免 PyYAML 依赖
- C) 放入 config.yaml → config.yaml 已有太多职责，敏感 key 混入不安全

**理由**: JSON 是最简单的结构化配置格式，Python 标准库直接支持。`api_keys` 数组天然支持轮换。`priority` 数值排序天然表达 fallback 链。`.gitignore` 排除 `providers.json` 防止 key 泄露。

### D2: 错误分类策略

**选择**: 按 HTTP 状态码分类，决定 fallback 方向。

```
错误分类:
┌─────────────────────┬────────┬──────────────────────────┐
│ 异常类型            │ 级别   │ Fallback 动作             │
├─────────────────────┼────────┼──────────────────────────┤
│ ConnectionError     │ Provider│ 跳过整个 provider         │
│ APIConnectionError  │ Provider│ 跳过整个 provider         │
│ 401 Unauthorized    │ Provider│ 跳过整个 provider         │
│ 403 Forbidden       │ Provider│ 跳过整个 provider         │
│ 429 Rate Limit      │ 模型   │ 同 provider 换下一个模型   │
│ 404 Not Found       │ 模型   │ 同 provider 换下一个模型   │
│ 400 Bad Request     │ 模型   │ 同 provider 换下一个模型   │
│ 其他                │ 未知   │ 当作 Provider 级处理       │
└─────────────────────┴────────┴──────────────────────────┘
```

**备选方案**:
- A) 不分类，统一 provider 级 fallback → 浪费同 provider 内其他可用模型
- B) 全部模型级 fallback → provider 挂了还傻试其他模型，浪费时间

**理由**: 错误分类让 fallback 更精准。Provider 级错误意味着该 provider 所有模型都不可用，直接跳。模型级错误只影响单个模型，同 provider 其他模型还能用。

### D3: 指数退避 Cooldown

**选择**: `cooldown = min(base × 2^(failures - 1), max_cooldown)`，base=2min, max=24h。

```
退避序列 (base=2min):
1st:  2min  → 2nd:  4min  → 3rd:  8min  → 4th: 16min
5th: 32min  → 6th:  1h   → 7th:  2h   → ...  → 11th+: 24h (封顶)

成功调用 → failures 计数归零，cooldown 清除
```

Cooldown 粒度：
- Provider 级 cooldown：按 provider name 索引，整个 provider 被跳过
- 模型级 cooldown：按 `{provider_name}/{model_id}` 索引，只跳过该模型

**备选方案**:
- A) 固定 30min cooldown → 不够灵活，短时错误等太久，长时错误重试太快
- B) 线性递增（每次+5min）→ 退避太慢，限额场景下频繁重试浪费

**理由**: 指数退避是业界标准（TCP/AWS SDK 均采用）。短时错误快速恢复，持续失败自动拉长间隔。24h 封顶覆盖"日限额"场景。

### D4: API Key 轮换策略

**选择**: 简单轮询（Round-Robin），每次调用切换到下一个 key。

```python
key_index = request_count % len(api_keys)
current_key = api_keys[key_index]
```

**备选方案**:
- A) 随机选择 → 分布不均匀
- B) Key 级别健康检查 → 过于复杂，cooldown 机制已覆盖

**理由**: 只有 Ollama 有 2 个 key，轮询足够。不需要额外的 key 级健康检查，如果一个 key 失败了会触发 fallback 机制自动切换。

### D5: 统一管理器接口设计

**选择**: `LLMClientManager` 提供 3 个接口，对应 3 种客户端类型。

```python
class LLMClientManager:
    def get_chat_model(self, **kwargs) -> ChatOpenAI
        """给 llm.py / graph.py 使用，LangChain ChatOpenAI 实例"""

    def get_sync_client(self) -> OpenAI
        """给 tool_selector.py 的 LLMIntentClassifier 使用"""

    def get_async_client(self) -> AsyncOpenAI
        """给 skills/__init__.py 的 build_skill_context 使用"""

    def get_model_info(self) -> dict
        """返回当前使用的 provider/model 信息，供日志输出"""
```

Manager 内部维护状态：
- `_chain`: fallback 链 `[ProviderConfig, ModelConfig]`
- `_cooldowns`: cooldown 状态 `dict[str, CooldownEntry]`
- `_key_counters`: key 轮询计数器 `dict[str, int]`

**备选方案**:
- A) 只暴露一个 `invoke()` 方法 → 调用方无法使用 `bind_tools()` 等 LangChain 特性
- B) 每个 provider 独立 Manager → 状态分散，无法统一 fallback

**理由**: 3 个接口覆盖所有现有调用场景。Manager 管理状态（链路、cooldown、key 轮询），调用方只管拿客户端。`ChatOpenAI` 支持 `bind_tools()`，`get_chat_model()` 保持 LangGraph 兼容。

### D6: 4 个调用点改造方式

```
改造前 → 改造后:

llm.py: get_llm()
  硬编码 settings.ai_api_key
  → get_llm() 调用 manager.get_chat_model()
     providers.json 存在 → Manager 提供
     providers.json 不存在 → config.yaml 兜底

graph.py: _get_classifier()
  LLMIntentClassifier(settings.ai_api_key, ...)
  → LLMIntentClassifier 从 manager.get_sync_client() 获取参数

skills/__init__.py: build_skill_context()
  AsyncOpenAI(api_key=settings.ai_api_key, ...)
  → manager.get_async_client()

tool_selector.py: LLMIntentClassifier
  在 graph.py _get_classifier 中实例化
  → 已被 graph.py 改造覆盖
```

**关键约束**: 所有改造必须保留 config.yaml 兜底，确保 providers.json 不存在时系统照常运行。

## Risks / Trade-offs

- **[providers.json 泄露]** → 加入 `.gitignore`，和 `model_list.json` 同级管理。`.gitignore` 已排除 `model_list.json`
- **[错误分类不完整]** → 未知错误统一按 Provider 级处理（保守策略）。可迭代补充更多错误类型
- **[cooldown 状态内存中]** → 服务重启清空，正好重试。不需要持久化
- **[providers.json 格式变更]** → 首次需手动从 `model_list.json` 迁移。格式简单，一次性工作
- **[单次 fallback 延迟]** → 429 后尝试下一个模型有网络延迟。可接受，比直接报错好
