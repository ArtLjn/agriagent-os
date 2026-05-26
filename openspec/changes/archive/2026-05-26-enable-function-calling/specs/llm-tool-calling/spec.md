## ADDED Requirements

### Requirement: LLM 初始化支持 thinking 模式配置
`get_llm()` 创建 `ChatOpenAI` 实例时 SHALL 读取 `config.yaml` 中的 `ai.enable_thinking` 配置，并通过 `model_kwargs` 或 `extra_body` 传递给 API。当 `enable_thinking` 为 `false` 或未设置时，SHALL 传递 `enable_thinking: false`。

#### Scenario: 配置关闭思考模式
- **WHEN** `config.yaml` 中 `ai.enable_thinking` 为 `false`
- **THEN** `get_llm()` 创建的 `ChatOpenAI` 实例通过 `extra_body` 传递 `{"enable_thinking": false}`，LLM 不会进入思考模式

#### Scenario: 配置未设置
- **WHEN** `config.yaml` 中未配置 `enable_thinking`
- **THEN** 默认行为等同于 `enable_thinking: false`

#### Scenario: 配置开启思考模式
- **WHEN** `config.yaml` 中 `ai.enable_thinking` 为 `true`
- **THEN** `get_llm()` 不传递 `enable_thinking` 参数（使用模型默认行为）

### Requirement: Function Calling 链路端到端可用
当使用支持 FC 的模型（如 `qwen3.6-flash`）且 `enable_thinking` 为 `false` 时，LangGraph 的 `_llm_node` 中 `bind_tools()` SHALL 正常工作。LLM 遇到需要调用 skill 的用户输入时 SHALL 返回 `tool_calls`，`_should_continue` SHALL 检测到并路由到 `_parallel_tool_node` 执行。

#### Scenario: 用户询问天气触发 tool call
- **WHEN** 用户发送"明天天气怎么样"
- **THEN** LLM 返回 `tool_calls` 包含 `get_weather_forecast`，`_should_continue` 返回 `"tools"`，`_parallel_tool_node` 执行 weather skill 并返回真实天气数据

#### Scenario: 用户闲聊不触发 tool call
- **WHEN** 用户发送"你好"
- **THEN** LLM 直接回复文本，`_should_continue` 返回 `END`，不触发任何 skill 执行

#### Scenario: 多 skill 并行调用
- **WHEN** 用户发送"看看天气和最近的成本"
- **THEN** LLM 返回多个 `tool_calls`（weather + cost_summary），`_parallel_tool_node` 并行执行两个 skill

### Requirement: 默认模型切换为 qwen3.6-flash
`AIConfig.model` 的默认值 SHALL 从 `qwen-flash-character` 变更为 `qwen3.6-flash-2026-04-16`。

#### Scenario: 使用新默认模型
- **WHEN** `config.yaml` 中未配置 `ai.model`
- **THEN** `Settings.ai_model` 返回 `qwen3.6-flash-2026-04-16`

#### Scenario: 显式指定模型
- **WHEN** `config.yaml` 中 `ai.model` 设置为其他模型名
- **THEN** 使用用户指定的模型

### Requirement: LLM 实例缓存包含 thinking 配置
全局 LLM 实例 `LLM_INSTANCE` SHALL 在首次创建时固化 `enable_thinking` 配置。后续通过 `get_llm()` 获取的实例 SHALL 使用相同的 thinking 配置，除非全局实例被重置。

#### Scenario: 首次创建包含配置
- **WHEN** 服务启动后首次调用 `get_llm()`
- **THEN** 创建的 `ChatOpenAI` 实例包含正确的 `extra_body` 参数

#### Scenario: 后续调用复用实例
- **WHEN** 多次调用 `get_llm()`
- **THEN** 返回同一个已初始化的实例
