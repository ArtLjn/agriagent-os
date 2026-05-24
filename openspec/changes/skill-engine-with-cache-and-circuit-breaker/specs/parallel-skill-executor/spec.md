## Requirements

### R1: 并行执行节点
- 自定义 LangGraph 节点替换 `create_react_agent` 默认 tool 执行
- 解析 LLM 返回的 `tool_calls` 列表
- 当 tool_calls 数量 > 1 时，使用 `asyncio.gather` 并发执行
- 当 tool_calls 数量 = 1 时，直接同步执行

### R2: 结果聚合
- 每个 tool_call 结果封装为 `ToolMessage`，tool_call_id 一一对应
- 所有结果收集后追加到 messages 列表，传回 LLM 节点

### R3: 错误隔离
- 单个 Skill 执行失败不影响其他并行 Skill
- 失败的 Skill 返回错误信息作为 ToolMessage content
- 日志记录每个 Skill 的执行耗时和结果状态

## Acceptance Criteria
- [ ] LLM 返回 2+ tool_calls 时，日志显示并行执行，总耗时 ≈ max(单个) 而非 sum
- [ ] 单个 Skill 失败时其他 Skill 正常返回，LLM 收到部分结果+错误提示
