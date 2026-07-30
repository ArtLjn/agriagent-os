## ADDED Requirements

### Requirement: 会话摘要 block 注入
ContextBuilder SHALL 在每次构建 ContextBundle 时，通过 ConversationSelector 从 `conversations.summary` 字段读取会话摘要（若存在），作为独立 ContextBlock 注入。该 block SHALL 与最近消息窗口 block 分离，便于独立预算决策。

block 元数据 SHALL 满足：
- key 形如 `conversation_summary`
- source 标记为 `conversation.summary`
- priority 介于 pending_action（95）与最近消息窗口（55）之间，默认 50
- compressible=True，min_tokens ≥ 64
- metadata 包含 `layer=working`、`cache_scope=session`

#### Scenario: 存在摘要时注入
- **WHEN** ContextBuilder 构建会话上下文且 `conversations.summary` 非空
- **THEN** ContextBundle 包含 key 为 `conversation_summary` 的 ContextBlock，内容为摘要原文

#### Scenario: 摘要为空时不注入
- **WHEN** `conversations.summary` 为 NULL 或空字符串
- **THEN** ContextBundle 不包含 `conversation_summary` block，不产生空 block

#### Scenario: 预算紧张时优先保留最近窗口
- **WHEN** TokenBudget 决策时遇到预算不足，且候选包含 `conversation_summary` 与最近消息窗口
- **THEN** 系统优先保留最近窗口 block，按 priority 与 compressible 规则压缩或丢弃摘要 block，记录 trace 决策原因

#### Scenario: 摘要 block 可独立观测
- **WHEN** ContextBuilder 完成构建
- **THEN** trace 事件包含 `conversation_summary` block 的存在性、token 估算、是否被压缩或丢弃，便于调试"摘要未生效"类问题
