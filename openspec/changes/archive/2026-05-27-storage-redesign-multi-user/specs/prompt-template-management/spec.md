## MODIFIED Requirements

### Requirement: 用户上下文结构化注入
系统 SHALL 将用户关键信息以 XML 格式注入 `base.j2` 的 `<user_context>` 段。`<name>` 标签的值 SHALL 从 `users.nickname` 获取（不再从 `farms.display_name`）。

#### Scenario: location 有值时注入
- **WHEN** 用户 nickname="老李"，Farm.location 为"苏州"
- **THEN** system prompt 包含 `<user_context><location>苏州</location><name>老李</name><season>夏季</season></user_context>`

#### Scenario: location 为空时不注入 location 节点
- **WHEN** Farm.location 为 NULL，用户 nickname="老李"
- **THEN** system prompt 的 `<user_context>` 段不包含 `<location>` 节点，但包含 `<name>老李</name>`
