## ADDED Requirements

### Requirement: Agent 审计日志单行结构化
系统 SHALL 为 Agent 关键阶段记录单行结构化审计日志。日志 MUST 包含稳定 `event` 字段，并在可用时包含 `request_id`、`session_id`、`farm_id`、`phase`、`status` 和 `duration_ms`。

#### Scenario: Final 阶段日志
- **WHEN** Agent 进入 final_response 阶段
- **THEN** `app.log` 输出一条单行日志
- **AND** 日志包含 `event=agent_audit`
- **AND** 日志包含 `phase=final_response`
- **AND** 日志包含真实 `tool_choice`

#### Scenario: Output Guard 日志
- **WHEN** Output Guard 检测最终回复
- **THEN** `app.log` 输出 `final_output_guard_checked`
- **AND** 日志包含 `passed`、`leak_type` 和 `action`

### Requirement: 审计追踪块导出格式
系统 SHALL 支持将 Agent 关键阶段导出为人读审计追踪块。审计追踪块 MUST 包含工单 ID、Run ID、Trace ID、边界、SOP、工具、最终动作、结果和耗时。

#### Scenario: 导出 final_response 审计块
- **WHEN** 开发者复制某次 final_response 诊断
- **THEN** 导出的审计块包含 `工单 ID`
- **AND** 包含 `Run ID`
- **AND** 包含 `Trace ID`
- **AND** 包含 `边界`
- **AND** 包含 `最终动作`

#### Scenario: 审计块不写入默认 app.log
- **WHEN** Agent 正常运行
- **THEN** 默认 `app.log` 只写单行结构化日志
- **AND** 不直接写入多行审计追踪块

### Requirement: 日志脱敏
Agent 审计日志 SHALL 只记录摘要字段，不得记录完整密钥、连接串、鉴权头、完整 prompt、完整 ToolMessage 或完整工具参数 JSON。

#### Scenario: 工具参数脱敏
- **WHEN** 工具调用包含多个参数
- **THEN** `app.log` 记录 `arg_keys`
- **AND** 不记录完整参数 JSON

#### Scenario: Provider 配置脱敏
- **WHEN** LLM 调用日志记录 provider 信息
- **THEN** 日志不得包含完整 api key
- **AND** 日志不得包含完整鉴权头
