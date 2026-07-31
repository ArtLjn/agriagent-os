## ADDED Requirements

### Requirement: Final Context Trace
系统 SHALL 在 final_response 阶段记录 `final_context.build` trace 节点，用于证明原始 tool call 历史已被隔离。

#### Scenario: 记录 final context 构建
- **WHEN** FinalContextBuilder 构建最终回复上下文
- **THEN** trace 包含 `node_type=final_context`
- **AND** `node_name=build`
- **AND** `output_data.dropped_tool_call_history=true`
- **AND** `output_data.tool_results` 包含脱敏工具结果摘要

### Requirement: Output Guard Trace
系统 SHALL 在最终回复返回前记录 `output_guard.final_json_leak_check` trace 节点，描述泄漏检测结果和处理动作。

#### Scenario: 泄漏检查通过
- **WHEN** 最终回复不包含工具协议
- **THEN** trace 记录 `output_data.passed=true`

#### Scenario: 泄漏检查失败
- **WHEN** 最终回复包含 function call JSON
- **THEN** trace 记录 `output_data.passed=false`
- **AND** trace 记录 `output_data.leak_type`
- **AND** trace 记录 `output_data.action`

### Requirement: LLM Trace 记录真实 invocation 参数
LLM 调用 trace SHALL 记录真实 provider invocation 参数中的 `tool_choice`、`selected_tools` 和 `message_count`。系统 MUST NOT 在 trace 中用 `selected_tools=[]` 推导 `tool_choice=none`。

#### Scenario: Final 阶段真实 tool_choice
- **WHEN** final_response 阶段调用 LLM
- **THEN** `llm_call` trace 的 `input_data.tool_choice` 等于真实 invocation 参数

#### Scenario: Trace 与日志一致
- **WHEN** `app.log` 中 `llm_call_started` 记录 `tool_choice=auto`
- **THEN** 对应 `llm_call` trace 不得展示为 `tool_choice=none`

### Requirement: Final 回复数据源 Trace
系统 SHALL 记录最终回复依赖的数据源，用于区分 context-only 回复、工具结果回复和 fail-closed 回复。

#### Scenario: 工具结果回复
- **WHEN** 最终回复基于 `calculate_arithmetic` 工具结果
- **THEN** trace 中 `response.final_reply_data_source` 标记 `data_source=tool:calculate_arithmetic`

#### Scenario: Fail-closed 回复
- **WHEN** Output Guard 触发 fail-closed
- **THEN** trace 中最终回复节点记录 `reason=output_guard_fail_closed`
