## MODIFIED Requirements

### Requirement: Agent trace 记录 skill 执行链路
Agent trace 系统 SHALL 通过 `llm_call` 和 `skill_call` 节点记录完整的 FC 路由链路。`_llm_node` SHALL 记录 LLM 的 tool selection 决策（`tool_calls` 字段或直接回复）。`_parallel_tool_node` SHALL 记录每个 skill 的执行结果。SHALL 不再记录 `node_type="routing"` 的 `skillify_route` 条目。

#### Scenario: FC 路由的 trace 记录完整
- **WHEN** 用户发送 "今天天气咋样"，FC 路由命中 `weather`
- **THEN** trace 中包含 `llm_call` 节点（`tool_calls=[weather]`）和 `skill_call` 节点（`node_name=weather`，含执行结果），不包含 `node_type="routing"` 的记录

#### Scenario: 无 tool 调用的 trace 记录
- **WHEN** 用户发送 "你好"，LLM 直接回复
- **THEN** trace 中仅包含 `llm_call` 节点（`reply_len=N`），不包含 `skill_call` 或 `routing` 记录

## REMOVED Requirements

### Requirement: 预路由 trace 记录
**Reason**: skillify 预路由快通道已移除，不再有独立的路由阶段
**Migration**: FC 路由的 tool selection 由 `_llm_node` 的 `llm_call` trace 记录覆盖
