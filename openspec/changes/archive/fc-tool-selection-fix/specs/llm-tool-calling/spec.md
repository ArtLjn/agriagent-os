## MODIFIED Requirements

### Requirement: Function Calling 链路端到端可用
当使用支持 FC 的模型（如 `qwen3.6-flash`）且 `enable_thinking` 为 `false` 时，LangGraph 的 `_llm_node` 中 `bind_tools()` SHALL 正常工作。LLM 遇到需要调用 skill 的用户输入时 SHALL 返回 `tool_calls`，`_should_continue` SHALL 检测到并路由到 `_parallel_tool_node` 执行。`_llm_node` SHALL 在 LLM 返回后以 INFO 级别记录工具选择决策（选择的工具名称列表）或直接回复信息。各 Skill 的 `description` 属性 SHALL 使用意图场景描述格式，覆盖用户典型口语表达，确保小模型能准确映射用户意图到 tool。`base.j2` 的工具调用规则 SHALL 包含【可用工具】映射表，明确列出所有 tool 名称与用户意图关键词的对应关系。

#### Scenario: 用户询问天气触发 tool call
- **WHEN** 用户发送"明天天气怎么样"
- **THEN** LLM 返回 `tool_calls` 包含 `weather`，`_should_continue` 返回 `"tools"`，`_parallel_tool_node` 执行 weather skill 并返回真实天气数据，`_llm_node` 日志记录 `tool_calls=[weather]`

#### Scenario: 用户闲聊不触发 tool call
- **WHEN** 用户发送"你好"
- **THEN** LLM 直接回复文本，`_should_continue` 返回 `END`，不触发任何 skill 执行，`_llm_node` 日志记录 `reply_len=N`

#### Scenario: 多 skill 并行调用
- **WHEN** 用户发送"看看天气和最近的成本"
- **THEN** LLM 返回多个 `tool_calls`（weather + cost_summary），`_parallel_tool_node` 并行执行两个 skill，`_llm_node` 日志记录 `tool_calls=[weather, get_cost_summary]`

#### Scenario: 口语化余额查询触发 tool call
- **WHEN** 用户发送"我的余额"
- **THEN** LLM 返回 `tool_calls` 包含 `get_cost_summary`

#### Scenario: 口语化创建茬口触发 tool call
- **WHEN** 用户发送"帮我创建春茬种植西瓜"
- **THEN** LLM 返回 `tool_calls` 包含 `create_crop_cycle`
