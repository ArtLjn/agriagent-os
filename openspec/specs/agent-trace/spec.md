## ADDED Requirements

### Requirement: AgentTrace 写入 LLM 调用记录
`_llm_node` 每次调用 LLM 后 SHALL 向 `agent_traces` 表写入一条记录，包含：`farm_id`、`session_id`（从 `request_id_var` 获取）、`node_type="llm_call"`、`node_name="llm"`、`input_summary`（用户最后一条消息前 200 字符）、`output_summary`（LLM 响应前 200 字符或 tool_calls 摘要）、`duration_ms`（毫秒耗时）、`tokens_used`（如 LLM 响应 metadata 包含则提取，否则 None）。

#### Scenario: LLM 直接回复文本
- **WHEN** LLM 返回文本回复（无 tool_calls）
- **THEN** 写入 `agent_traces` 一条记录，`node_type="llm_call"`，`output_summary` 为回复前 200 字符，`duration_ms` 为实际耗时

#### Scenario: LLM 返回 tool_calls
- **WHEN** LLM 返回包含 tool_calls 的响应
- **THEN** 写入 `agent_traces` 一条记录，`output_summary` 格式为 `tool_calls: [skill1, skill2]`，包含调用的 Skill 名称列表

#### Scenario: LLM 调用失败
- **WHEN** LLM 调用抛出异常
- **THEN** 写入 `agent_traces` 一条记录，`error_message` 包含异常信息，`output_summary` 为 None

### Requirement: AgentTrace 写入 Skill 执行记录
`_parallel_tool_node` 每次执行 Skill 后 SHALL 向 `agent_traces` 表写入一条记录，包含：`farm_id`、`session_id`、`node_type="tool_call"`、`node_name`（Skill 名称）、`input_summary`（参数 JSON 前 200 字符）、`output_summary`（返回值前 200 字符）、`duration_ms`（毫秒耗时）、`error_message`（失败时记录异常信息）。

#### Scenario: Skill 执行成功
- **WHEN** Skill `ainvoke` 正常返回
- **THEN** 写入 `agent_traces` 一条记录，`node_type="tool_call"`，`node_name` 为 Skill 名称，`output_summary` 为返回值前 200 字符，`duration_ms` 为实际耗时

#### Scenario: Skill 执行失败
- **WHEN** Skill `ainvoke` 抛出异常
- **THEN** 写入 `agent_traces` 一条记录，`error_message` 包含异常信息，`output_summary` 为 None

#### Scenario: 写操作 Skill 拦截
- **WHEN** 写操作 Skill 被 pending action 拦截
- **THEN** 写入 `agent_traces` 一条记录，`node_type="tool_call"`，`output_summary` 为 "已拦截为 pending action"，`duration_ms` 为 0

### Requirement: AgentTrace session_id 关联
每条 `agent_traces` 记录 SHALL 从 `request_id_var` ContextVar 获取 `session_id`，使同一请求的 LLM 调用和 Skill 执行记录可关联查询。

#### Scenario: 同一请求产生多条追踪记录
- **WHEN** 用户发送一条消息，触发 LLM 调用 + Skill 执行
- **THEN** LLM 调用记录和 Skill 执行记录具有相同的 `session_id`
