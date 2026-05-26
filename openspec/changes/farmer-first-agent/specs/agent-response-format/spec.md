## ADDED Requirements

### Requirement: Agent 回复格式遵守短句式约束
Agent 回复（每日建议和聊天）SHALL 遵守以下格式规则，通过 prompt 模板注入：
- 每条建议/操作不超过 2 行
- 总共不超过 5 条
- 先说结论，再说原因
- 禁止铺垫、寒暄、总结段

#### Scenario: 每日建议格式
- **WHEN** 用户请求每日建议
- **THEN** 回复为条目列表，每条 ≤2 行，总共 ≤5 条，无开头寒暄和结尾总结

#### Scenario: 聊天回复格式
- **WHEN** 用户在对话中提问
- **THEN** 回复直接回答问题，不超过 5 条要点，无「你好」「希望对你有帮助」等客套

#### Scenario: 复杂问题允许长回复
- **WHEN** 用户明确要求详细解释（如「详细说说白粉病怎么治」）
- **THEN** Agent 可以超出 5 条限制，但仍需条目化、先结论后展开

### Requirement: Agent 使用用户称呼
Agent 回复 SHALL 使用用户设置中的 `display_name` 称呼用户，替代默认的「您好」。

#### Scenario: 有称呼时
- **WHEN** 用户设置了 display_name="老李"
- **THEN** Agent 回复开头使用「老李」，如「老李，今天三件事」

#### Scenario: 无称呼时
- **WHEN** 用户未设置 display_name
- **THEN** Agent 使用默认称呼「农友」

### Requirement: 回复口语化
Agent 回复 SHALL 使用口语化表达，用「你」不用「您」，避免书面语和过于专业的术语。

#### Scenario: 口语化回复
- **WHEN** Agent 生成建议
- **THEN** 使用「该打药了」而非「建议进行农药喷洒」，使用「明天降温」而非「预计气温将下降」

### Requirement: prompt 模板注入格式规则
`base.j2` 模板 SHALL 包含 `{{ response_format_rules }}` 变量块，由 prompt_renderer 在渲染时填充格式规则和用户称呼。

#### Scenario: 渲染时注入格式规则
- **WHEN** prompt_renderer 渲染 base.j2
- **THEN** `{{ response_format_rules }}` 被替换为包含格式约束和 display_name 的文本块
