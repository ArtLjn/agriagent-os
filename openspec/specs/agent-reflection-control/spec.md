# agent-reflection-control Specification

## Purpose
TBD - archived from change add-agent-reflection-mode. Update Purpose after review.

## Requirements
### Requirement: Triggered reflection control
系统 SHALL 提供触发式 Agent Reflection 控制层，在高风险或高不确定性节点执行自检，并输出结构化反思结果。Reflection SHALL NOT 作为用户可手动选择的独立聊天模式暴露。

#### Scenario: Low risk request skips reflection
- **WHEN** 用户发送普通问候或无需工具的低风险闲聊
- **THEN** 系统 SHALL 不触发 Reflection 检查
- **AND** 回复 SHALL 沿用现有低延迟路径

#### Scenario: High risk write request triggers reflection
- **WHEN** 用户请求新增、修改、删除或结算业务数据
- **THEN** 系统 SHALL 在展示 pending action 或 pending plan 前触发 Reflection 检查
- **AND** Reflection 结果 SHALL 包含触发器、检查项、问题列表和最终决策

### Requirement: Reflection decision actions
Reflection 控制层 SHALL 将检查结果归一为明确动作：通过、要求澄清、要求补工具、阻断写入、重试生成或安全兜底。系统 SHALL 根据动作继续请求生命周期，且 MUST NOT 在存在阻断级写入问题时执行写技能。

#### Scenario: Missing write parameter asks clarification
- **WHEN** 写操作计划缺少必需参数
- **THEN** Reflection 决策 SHALL 为 `ask_clarification` 或 `block_write`
- **AND** 系统 SHALL 不创建可确认的执行结果
- **AND** 用户 SHALL 收到说明缺失信息的澄清回复

#### Scenario: Tool result supports final response
- **WHEN** 工具结果完整且最终回复与工具结果一致
- **THEN** Reflection 决策 SHALL 为 `pass`
- **AND** 系统 SHALL 输出最终回复

### Requirement: Post-tool consistency checks
系统 SHALL 在工具执行后、最终回复前，对需要工具证据的回答执行一致性检查。检查 SHALL 识别工具执行失败后仍声称成功、工具结果与回复结论矛盾、应调用工具却未调用等问题。

#### Scenario: Failed tool cannot produce success reply
- **WHEN** 写技能或读技能返回失败状态
- **AND** LLM 生成的最终回复声称操作成功或查询完成
- **THEN** Reflection SHALL 标记结果矛盾
- **AND** 系统 SHALL 返回失败说明或重新生成安全回复

#### Scenario: Missing required tool call is caught
- **WHEN** Router 已选择必需工具
- **AND** LLM 未生成工具调用且直接回答真实业务数据
- **THEN** Reflection SHALL 决策为 `require_tool` 或 `retry_generation`
- **AND** 系统 SHALL 不把未经工具验证的数据回答作为最终事实输出

### Requirement: Reflection observability
每次触发 Reflection 检查时，系统 SHALL 记录可回放的结构化 trace 事件。事件 SHALL 包含 trigger、decision、issues、关联工具、关联 pending plan 或 tool call 标识、响应摘要和耗时。

#### Scenario: Reflection event appears in debug export
- **WHEN** 一次 Agent 请求触发 Reflection 检查
- **THEN** debug export 或 trace SHALL 包含 `reflection_check` 事件
- **AND** Evaluation SHALL 能基于该事件识别失败原因或通过原因

### Requirement: Reflection failure is fail-closed for writes
当 Reflection 检查自身异常或超时时，系统 SHALL 对写操作采用 fail-closed 策略，对只读或闲聊场景采用可降级策略。

#### Scenario: Reflection timeout before write execution
- **WHEN** 用户确认执行 pending plan
- **AND** Reflection 检查超时或异常
- **THEN** 系统 SHALL 不执行写技能
- **AND** 用户 SHALL 收到稍后重试或重新确认的安全提示

#### Scenario: Reflection timeout after read tool
- **WHEN** 只读查询工具已成功返回
- **AND** Reflection 检查超时
- **THEN** 系统 MAY 使用现有回复链路继续输出
- **AND** trace SHALL 记录 Reflection 降级事件
