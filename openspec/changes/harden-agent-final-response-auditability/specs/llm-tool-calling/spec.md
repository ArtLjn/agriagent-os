## ADDED Requirements

### Requirement: Tool 阶段与 Final 阶段边界隔离
系统 SHALL 将工具调用阶段和最终回复阶段分离。Tool 阶段 MAY 绑定候选工具并使用 `tool_choice=auto|required`；Final 阶段 MUST 不绑定工具，且不得把原始 tool call 历史作为模型输入。

#### Scenario: Tool 阶段允许工具选择
- **WHEN** Router 为用户请求选择了只读候选工具
- **THEN** Tool 阶段 LLM 可以绑定候选工具
- **AND** Tool 阶段可以返回 `tool_calls`

#### Scenario: Final 阶段禁止继续工具调用
- **WHEN** Tool Executor 已返回工具结果
- **THEN** Final 阶段不得绑定任何工具
- **AND** Final 阶段不得把 `AIMessage(tool_calls)` 传给 LLM

### Requirement: Final 阶段工具调用输出被视为协议违规
如果 Final 阶段 LLM 返回原生 `tool_calls` 或 content 中的工具调用 JSON，系统 SHALL 将其视为协议违规，而不是继续执行工具。

#### Scenario: Final 阶段原生 tool_calls
- **WHEN** Final 阶段 LLM 返回原生 `tool_calls`
- **THEN** 系统不得把这些 tool calls 交给 Tool Executor 执行
- **AND** 系统 SHALL 交由 Output Guard 处理

#### Scenario: Final 阶段 content 工具 JSON
- **WHEN** Final 阶段 LLM content 中出现可解析工具调用 JSON
- **THEN** 系统不得把该 JSON 转换为可执行 tool call
- **AND** 系统 SHALL 记录泄漏诊断
