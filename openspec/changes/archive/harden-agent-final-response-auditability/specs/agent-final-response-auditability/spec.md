## ADDED Requirements

### Requirement: Final Agent 使用干净上下文
系统 SHALL 在工具执行后通过 FinalContextBuilder 构建最终回复上下文。FinalContextBuilder MUST 将原始 ReAct 消息历史投影为 `FinalResponseRequest`，且不得向最终 LLM 传递原始 `AIMessage.tool_calls` 或原始 `ToolMessage`。

#### Scenario: 工具结果后构建最终上下文
- **WHEN** 当前轮消息包含 `HumanMessage -> AIMessage(tool_calls) -> ToolMessage`
- **THEN** FinalContextBuilder 返回的 `FinalResponseRequest` 包含用户问题和脱敏工具结果摘要
- **AND** `FinalResponseRequest` 不包含原始 `AIMessage.tool_calls`
- **AND** `FinalResponseRequest` 不包含原始 `ToolMessage`

#### Scenario: 工具结果事实保留
- **WHEN** 工具 `calculate_arithmetic` 返回 `30 / 1.5 = 20`
- **THEN** `FinalResponseRequest.tool_results` 包含工具名、状态和事实摘要
- **AND** 最终回复可基于该事实回答用户问题

### Requirement: Final 阶段禁止工具调用
系统 SHALL 在 final_response 阶段调用 LLM 时显式使用 `tools=[]` 和 `tool_choice=none`。日志和 trace 中记录的 `tool_choice` MUST 来自真实 invocation 参数，不得根据 `selected_tools=[]` 推导。

#### Scenario: Final LLM 调用参数
- **WHEN** 当前轮已有工具结果并进入 final_response 阶段
- **THEN** LLM 调用参数包含 `tools=[]`
- **AND** LLM 调用参数包含 `tool_choice=none`
- **AND** `llm_call_started` 日志记录 `tool_choice=none`

#### Scenario: Trace 不推导 tool_choice
- **WHEN** final_response 阶段记录 `llm_call` trace
- **THEN** trace 中的 `input_data.tool_choice` 等于真实 LLM invocation 参数
- **AND** 若真实参数不是 `none`，系统不得把 trace 展示为 `none`

### Requirement: Output Guard 阻断 function call JSON 泄漏
系统 SHALL 在最终回复返回用户前检测原生 `tool_calls`、疑似 function call JSON、协议关键字和整段 JSON 输出。首次泄漏 SHALL 使用同一 `FinalResponseRequest` 重试一次；二次泄漏 SHALL 尝试安全抽取自然语言，无法抽取时 fail-closed。

#### Scenario: 原生 tool_calls 泄漏
- **WHEN** final_response 阶段 LLM 返回带 `response.tool_calls` 的响应
- **THEN** Output Guard 记录 `leak_type=native_tool_calls`
- **AND** 系统使用 final prompt 重试一次

#### Scenario: content 中出现工具 JSON
- **WHEN** final_response 阶段 LLM 文本包含 `{"name": "calculate_arithmetic", "arguments": {...}}`
- **THEN** Output Guard 记录 `leak_type=content_tool_call_json`
- **AND** 该 JSON 不得直接返回用户

#### Scenario: 二次泄漏后安全兜底
- **WHEN** final_response 阶段重试后仍包含工具协议
- **THEN** 系统尝试抽取自然语言
- **AND** 无法安全抽取时返回 fail-closed 文案
- **AND** 系统记录 DataFlywheel issue

### Requirement: 有工具结果时不得错误要求重新调用工具
系统 SHALL 区分“已有工具结果但最终回复格式异常”和“无可靠工具结果”两种兜底场景。若当前轮已有成功工具结果，fail-closed 文案 MUST NOT 表达“需要先调用工具”。

#### Scenario: 已有工具结果时的兜底
- **WHEN** 当前轮已有成功 `ToolResultSummary`
- **AND** final_response 阶段因 JSON 泄漏二次失败
- **THEN** 返回文案说明“已拿到工具结果但回复格式异常”
- **AND** 文案不得包含“需要先调用工具”

#### Scenario: 无工具结果时的兜底
- **WHEN** 当前轮没有可靠工具结果
- **AND** final_response 阶段无法生成安全自然语言
- **THEN** 返回文案说明“没有可靠结果可展示”

### Requirement: 防泄漏坏例进入 DataFlywheel
系统 SHALL 将 final_response 阶段 JSON 泄漏、工具结果丢弃、trace 与 app.log invocation 参数不一致、有工具结果却回复需要调用工具等问题沉淀为 DataFlywheel issue。

#### Scenario: JSON 泄漏入仓
- **WHEN** Output Guard 二次重试仍检测到工具协议泄漏
- **THEN** DataFlywheel issue 包含 request_id、session_id、用户输入、最终回复、泄漏类型和处理动作

#### Scenario: 工具结果丢弃入仓
- **WHEN** 当前轮已有工具结果但最终回复未使用工具事实
- **THEN** DataFlywheel issue 标记为 `tool_result_discarded_reply`
