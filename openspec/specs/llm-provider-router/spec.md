# llm-provider-router Specification

## Purpose
TBD - created by archiving change multi-llm-router. Update Purpose after archive.
## Requirements
### Requirement: 配置文件驱动多 Provider
系统 SHALL 从 `providers.json` 读取 LLM provider 配置，包含 provider 名称、base_url、api_keys 数组、优先级、模型列表。

#### Scenario: 正常加载 providers.json
- **WHEN** `providers.json` 存在且格式正确
- **THEN** 系统构建 fallback 链，按 provider.priority ASC → model.priority ASC 排序

#### Scenario: providers.json 不存在
- **WHEN** `providers.json` 文件不存在
- **THEN** 系统回退到 config.yaml 中的 `ai.api_key` / `ai.base_url` / `ai.model`，行为与改造前一致

#### Scenario: providers.json 格式错误
- **WHEN** `providers.json` JSON 解析失败
- **THEN** 系统 SHALL 记录 warning 日志并回退到 config.yaml 兜底

### Requirement: 错误分类 Fallback
系统 SHALL 根据 LLM 调用错误类型决定 fallback 方向：Provider 级错误跳过整个 provider，模型级错误先在同 provider 内换模型。

#### Scenario: Provider 级错误（连接失败）
- **WHEN** LLM 调用抛出 `APIConnectionError` 或 `ConnectionError`
- **THEN** 系统 SHALL 跳过该 provider 的所有模型，直接尝试下一个 provider

#### Scenario: Provider 级错误（认证失败）
- **WHEN** LLM 调用返回 401 或 403 状态码
- **THEN** 系统 SHALL 跳过该 provider 的所有模型，直接尝试下一个 provider

#### Scenario: 模型级错误（限速）
- **WHEN** LLM 调用返回 429 Rate Limit
- **THEN** 系统 SHALL 先尝试同 provider 内下一个优先级的模型

#### Scenario: 模型级错误（模型不存在）
- **WHEN** LLM 调用返回 404 Not Found
- **THEN** 系统 SHALL 先尝试同 provider 内下一个优先级的模型

#### Scenario: 所有 Provider 均不可用
- **WHEN** fallback 链中所有 provider 和模型都尝试失败
- **THEN** 系统 SHALL 抛出明确的异常信息，列出已尝试的 provider 和错误

### Requirement: 指数退避 Cooldown
系统 SHALL 对失败的 provider/模型实施指数退避 cooldown，base=2min，max=24h，成功调用后重置。

#### Scenario: 首次失败 cooldown
- **WHEN** 某个模型首次调用失败
- **THEN** 该模型在 2 分钟内被跳过

#### Scenario: 连续失败退避递增
- **WHEN** 同一模型连续失败 3 次
- **THEN** cooldown 时间为 8 分钟（2 × 2^(3-1)）

#### Scenario: 成功调用重置 cooldown
- **WHEN** 之前失败的模型调用成功
- **THEN** 该模型的失败计数归零，cooldown 清除

#### Scenario: Cooldown 封顶
- **WHEN** 同一模型连续失败超过 11 次
- **THEN** cooldown 时间封顶为 24 小时，不再增长

### Requirement: API Key 轮换
系统 SHALL 支持每个 provider 配置多个 API key，按轮询方式切换。

#### Scenario: 多 Key 轮询
- **WHEN** provider 配置了 2 个 api_keys
- **THEN** 第 1 次调用使用 key[0]，第 2 次使用 key[1]，第 3 次使用 key[0]

#### Scenario: 单 Key
- **WHEN** provider 只配置了 1 个 api_keys
- **THEN** 每次调用都使用该 key

### Requirement: 统一客户端管理器
系统 SHALL 提供 `LLMClientManager` 单例，统一管理所有 LLM 客户端实例。

#### Scenario: 获取 ChatOpenAI 实例
- **WHEN** 调用 `manager.get_chat_model()`
- **THEN** 返回配置了当前最优 provider/model/key 的 `ChatOpenAI` 实例

#### Scenario: 获取同步 OpenAI 客户端
- **WHEN** 调用 `manager.get_sync_client()`
- **THEN** 返回配置了当前最优 provider/model/key 的 `OpenAI` 实例

#### Scenario: 获取异步 OpenAI 客户端
- **WHEN** 调用 `manager.get_async_client()`
- **THEN** 返回配置了当前最优 provider/model/key 的 `AsyncOpenAI` 实例

#### Scenario: 获取当前模型信息
- **WHEN** 调用 `manager.get_model_info()`
- **THEN** 返回 `{"provider": "ollama", "model": "gemma3:12b", "base_url": "..."}` 格式的信息

