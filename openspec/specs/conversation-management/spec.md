## ADDED Requirements

### Requirement: 会话摘要输入短时记忆
Conversation 模块 SHALL 为 Memory 短时记忆提供最近消息和可选会话摘要。Agent SHALL 通过 Memory 或 Context 边界消费这些信息，而不是直接在 Runtime 中查询消息表。

#### Scenario: 注入最近会话
- **WHEN** Agent 处理同一 session 的追问
- **THEN** 短时记忆提供最近消息或摘要给 Context Builder

### Requirement: 对话观察事件
对话完成后，Conversation 或 Agent application SHALL 向 Memory 提交观察事件，供后续摘要和事实沉淀使用。

#### Scenario: 保存回复后观察
- **WHEN** 用户消息和助手回复已经持久化
- **THEN** 系统提交包含本轮交互内容和 metadata 的 Memory observation event
