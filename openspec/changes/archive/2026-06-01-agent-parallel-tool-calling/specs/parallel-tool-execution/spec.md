## Purpose
定义并行工具调用的执行机制，包括 prompt 引导、聚合 trace 日志和配置项。

## ADDED Requirements

### Requirement: System prompt 包含并行调用引导指令
Agent system prompt SHALL 包含一段引导文本，指示 LLM 在用户请求需要多个工具时，在一次回复中同时返回所有 tool_calls。

#### Scenario: 多意图问题触发并行 tool_calls
- **WHEN** 用户发送包含多个独立意图的消息（如"今天天气怎么样？顺便看看这个月花了多少钱"）
- **THEN** LLM 在一次回复中返回至少两个 tool_calls（天气查询 + 成本查询），而不是先返回一个再返回另一个

#### Scenario: 单意图问题正常返回单个 tool_call
- **WHEN** 用户发送只涉及一个工具的消息（如"明天天气怎么样"）
- **THEN** LLM 返回单个 tool_call，行为与并行功能启用前一致

### Requirement: 并行执行聚合 trace 日志
`_parallel_tool_node` 在并行执行多个 Skill 时 SHALL 额外记录一条聚合 trace 记录，包含并行数和各 Skill 耗时。

#### Scenario: 并行执行两个 Skill 记录聚合 trace
- **WHEN** LLM 返回 2 个 tool_calls，`_parallel_tool_node` 并行执行完成
- **THEN** trace 系统除各 Skill 的单独记录外，还包含一条 `node_type="parallel_batch"` 的聚合记录，`output_data` 包含 `parallel_count`、`skills` 列表（含各 Skill 名称和耗时）

#### Scenario: 单个 Skill 执行不记录聚合 trace
- **WHEN** LLM 返回 1 个 tool_call
- **THEN** trace 系统不记录 `parallel_batch` 类型的聚合记录，仅记录该 Skill 的单独记录

### Requirement: parallel_tool_calls 配置项
`AIConfig` SHALL 包含 `parallel_tool_calls: bool` 字段，默认值为 `True`。`graph.py` 中 `bind_tools()` 调用 SHALL 读取该配置并传入对应参数。

#### Scenario: 配置启用并行 tool_calls
- **WHEN** `AIConfig.parallel_tool_calls` 为 `True`（默认）
- **THEN** `llm.bind_tools(selected_tools, parallel_tool_calls=True)` 被调用

#### Scenario: 配置关闭并行 tool_calls
- **WHEN** `AIConfig.parallel_tool_calls` 为 `False`
- **THEN** `llm.bind_tools(selected_tools)` 不传入 `parallel_tool_calls` 参数（或传入 `False`）

#### Scenario: 配置关闭后串行执行正常
- **WHEN** `parallel_tool_calls` 为 `False` 且 LLM 返回单个 tool_call
- **THEN** `_parallel_tool_node` 正常执行该 Skill，行为与关闭前一致
