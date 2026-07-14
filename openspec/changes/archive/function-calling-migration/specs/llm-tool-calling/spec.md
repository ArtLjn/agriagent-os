## MODIFIED Requirements

### Requirement: Function Calling 链路端到端可用
当使用支持 FC 的模型（如 `qwen3.6-flash`）且 `enable_thinking` 为 `false` 时，LangGraph 的 `_llm_node` 中 `bind_tools()` SHALL 正常工作。LLM 遇到需要调用 skill 的用户输入时 SHALL 返回 `tool_calls`，`_should_continue` SHALL 检测到并路由到 `_parallel_tool_node` 执行。`_llm_node` SHALL 在 LLM 返回后以 INFO 级别记录工具选择决策（选择的工具名称列表）或直接回复信息。`_parallel_tool_node` 执行 tool 后，`_llm_node` SHALL 对 tool 返回结果进行第二轮推理，将原始数据组织为自然语言回复。

#### Scenario: 用户询问天气触发 tool call 并获得自然语言回复
- **WHEN** 用户发送"明天天气怎么样"
- **THEN** LLM 第一轮返回 `tool_calls` 包含 `weather`，`_should_continue` 返回 `"tools"`，`_parallel_tool_node` 执行 weather skill 并返回真实天气数据；LLM 第二轮将天气数据组织为自然语言回复（包含温度、降水等关键信息的可读描述）

#### Scenario: 用户闲聊不触发 tool call
- **WHEN** 用户发送"你好"
- **THEN** LLM 直接回复文本，`_should_continue` 返回 `END`，不触发任何 skill 执行，`_llm_node` 日志记录 `reply_len=N`

#### Scenario: 多 skill 并行调用并获得综合回复
- **WHEN** 用户发送"看看天气和最近的成本"
- **THEN** LLM 第一轮返回多个 `tool_calls`（weather + cost_summary），`_parallel_tool_node` 并行执行两个 skill；LLM 第二轮将两个 skill 的结果综合为一个连贯的自然语言回复
