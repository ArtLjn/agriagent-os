## MODIFIED Requirements

### Requirement: LLM 初始化支持 thinking 模式配置
`get_llm()` SHALL 优先通过 `LLMClientManager` 获取 LLM 实例。当 `providers.json` 存在且有效时，由 Manager 提供 `ChatOpenAI` 实例（已配置 enable_thinking）。当 `providers.json` 不存在时，SHALL 回退到 config.yaml 的 `ai.api_key` / `ai.base_url` / `ai.model` 创建实例，`enable_thinking` 配置行为不变。

#### Scenario: providers.json 存在时通过 Manager 获取
- **WHEN** `providers.json` 存在且包含可用 provider
- **THEN** `get_llm()` 通过 `LLMClientManager.get_chat_model()` 获取实例，Manager 负责选择 provider/model/key

#### Scenario: providers.json 不存在时回退 config.yaml
- **WHEN** `providers.json` 不存在
- **THEN** `get_llm()` 使用 config.yaml 的 `ai.api_key` / `ai.base_url` / `ai.model` 创建 `ChatOpenAI` 实例，行为与改造前一致

#### Scenario: Manager 异常时回退 config.yaml
- **WHEN** `LLMClientManager` 初始化失败或所有 provider 不可用
- **THEN** `get_llm()` 回退到 config.yaml 兜底，记录 warning 日志

#### Scenario: 配置关闭思考模式
- **WHEN** `config.yaml` 中 `ai.enable_thinking` 为 `false`
- **THEN** 无论通过 Manager 还是 config.yaml 创建的实例，都通过 `extra_body` 传递 `{"enable_thinking": false}`

## ADDED Requirements

### Requirement: LLMIntentClassifier 使用统一管理器
`graph.py` 中的 `_get_classifier()` SHALL 通过 `LLMClientManager.get_sync_client()` 获取 API key、base_url 和 model 参数，不再直接读取 `settings.ai_api_key`。

#### Scenario: Classifier 通过 Manager 初始化
- **WHEN** `_get_classifier()` 首次调用
- **THEN** 使用 `LLMClientManager` 提供的参数创建 `LLMIntentClassifier`，而非 `settings.ai_api_key`

### Requirement: build_skill_context 使用统一管理器
`skills/__init__.py` 中的 `build_skill_context()` SHALL 通过 `LLMClientManager.get_async_client()` 获取 `AsyncOpenAI` 客户端，不再直接读取 `settings.ai_api_key`。

#### Scenario: SkillContext 通过 Manager 获取客户端
- **WHEN** `build_skill_context()` 被调用
- **THEN** 使用 `LLMClientManager.get_async_client()` 提供的客户端和模型信息构建 `SkillContext`
