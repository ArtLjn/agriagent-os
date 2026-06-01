## Purpose
定义 LLM Function Calling 链路的端到端行为，包括 tool call 路由、并行调用配置和日志记录。

## MODIFIED Requirements

### Requirement: Function Calling 链路端到端可用
当使用支持 FC 的模型（如 `qwen3.6-flash`）且 `enable_thinking` 为 `false` 时，LangGraph 的 `_llm_node` 中 `bind_tools()` SHALL 正常工作。`bind_tools()` SHALL 根据 `AIConfig.parallel_tool_calls` 配置决定是否传入 `parallel_tool_calls=True`。LLM 遇到需要调用 skill 的用户输入时 SHALL 返回 `tool_calls`，`_should_continue` SHALL 检测到并路由到 `_parallel_tool_node` 执行。`_llm_node` SHALL 在 LLM 返回后以 INFO 级别记录工具选择决策（选择的工具名称列表）或直接回复信息。

#### Scenario: 用户询问天气触发 tool call
- **WHEN** 用户发送"明天天气怎么样"
- **THEN** LLM 返回 `tool_calls` 包含 `get_weather_forecast`，`_should_continue` 返回 `"tools"`，`_parallel_tool_node` 执行 weather skill 并返回真实天气数据，`_llm_node` 日志记录 `tool_calls=[get_weather_forecast]`

#### Scenario: 用户闲聊不触发 tool call
- **WHEN** 用户发送"你好"
- **THEN** LLM 直接回复文本，`_should_continue` 返回 `END`，不触发任何 skill 执行，`_llm_node` 日志记录 `reply_len=N`

#### Scenario: 多 skill 并行调用
- **WHEN** 用户发送"看看天气和最近的成本"
- **THEN** LLM 返回多个 `tool_calls`（weather + cost_summary），`_parallel_tool_node` 并行执行两个 skill，`_llm_node` 日志记录 `tool_calls=[get_weather_forecast, get_cost_summary]`，trace 系统记录 `parallel_batch` 聚合日志

#### Scenario: 并行配置关闭时 bind_tools 不传 parallel_tool_calls
- **WHEN** `AIConfig.parallel_tool_calls` 为 `False`
- **THEN** `bind_tools()` 不传入 `parallel_tool_calls` 参数，LLM 按 API 默认行为处理
