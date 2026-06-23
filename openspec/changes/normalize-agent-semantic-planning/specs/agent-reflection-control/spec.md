## MODIFIED Requirements

### Requirement: Post-tool consistency checks
系统 SHALL 在工具执行后、最终回复前，对需要工具证据的回答执行一致性检查。检查 SHALL 识别工具执行失败后仍声称成功、工具结果与回复结论矛盾、应调用工具却未调用、以及未选择工具但回复声称完成写入等问题。

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

#### Scenario: No-tool write success claim is blocked
- **WHEN** Router 未选择工具或 LLM 未生成工具调用
- **AND** 用户输入被 Semantic Gate 或写入话术规则识别为可能写操作
- **AND** 最终回复包含 "已记录"、"已创建"、"已保存"、"已执行" 或同义成功写入话术
- **THEN** Reflection SHALL block or replace the reply with a safe clarification
- **AND** 系统 SHALL NOT claim that business data was changed

## ADDED Requirements

### Requirement: Reflection emits no-tool write guard diagnostics
When Reflection blocks a no-tool write success claim, it SHALL emit trace evidence that identifies the input, final reply preview, matched success phrase, and route state.

#### Scenario: Debug export contains no-tool write guard
- **WHEN** Reflection blocks a no-tool write success claim
- **THEN** debug export or trace SHALL include a `reflection_check` event
- **AND** the event SHALL include issue code `no_tool_write_success_claim`
- **AND** Data Flywheel SHALL be able to label the case as `hallucinated_execution` or `tool_error_ignored`
