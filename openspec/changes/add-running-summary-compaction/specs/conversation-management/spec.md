## MODIFIED Requirements

### Requirement: 多轮对话历史注入 LangGraph
`invoke_advisor` / `stream_advisor` 调用时 SHALL 通过短时记忆策略向 LangGraph 注入当前 session 的工作记忆。工作记忆 SHALL 包含最近消息窗口，并在历史超过窗口或 token 预算时使用会话摘要替代更早历史。系统不得仅按固定条数无预算地注入完整历史。

会话摘要 SHALL 优先来源于 `conversations.summary` 持久化字段；ConversationSelector SHALL 通过数据库 JOIN 一并取出，作为独立 ContextBlock（key 形如 `conversation_summary`）注入到 ContextBundle，与最近消息窗口分块存储，便于独立压缩或丢弃。

#### Scenario: 首次对话无历史
- **WHEN** 新会话首次调用 `invoke_advisor`
- **THEN** LangGraph 只收到当前用户消息和必要热上下文，无历史消息

#### Scenario: 有历史时注入上下文
- **WHEN** 会话已有 5 轮对话，用户发送第 6 条消息
- **THEN** LangGraph 收到最近窗口内的历史消息、当前用户消息和符合 token 预算的工作记忆

#### Scenario: 历史超过窗口时摘要替代
- **WHEN** 会话历史超过最近消息窗口
- **THEN** LangGraph 收到窗口内原文消息，并收到来自 `conversations.summary` 的会话摘要作为独立 ContextBlock；若预算不足，摘要 block 可被压缩或丢弃，但最近窗口优先保留

#### Scenario: 摘要字段不存在时降级
- **WHEN** 会话历史超过窗口但 `conversations.summary` 为空（如老 session 未生成摘要、feature flag 关闭期间）
- **THEN** ConversationSelector 不注入空摘要 block，仅注入最近窗口；LangGraph 通过 `FinalPromptBudget` 字符串截断兜底

#### Scenario: 追问理解上下文
- **WHEN** 用户先问"明天天气"，LLM 回复后，用户追问"后天呢"
- **THEN** LLM 能根据短时记忆理解"后天"指的是天气，正确调用天气 skill

#### Scenario: 工具结果过长
- **WHEN** 历史消息中包含超过预算的大型 ToolMessage
- **THEN** 系统将旧工具结果压缩为执行摘要或通过 trace 标记丢弃，不得把完整大型工具结果无预算注入 LangGraph

#### Scenario: 摘要 block 与最近窗口分块
- **WHEN** ConversationSelector 同时取到 `conversations.summary` 和最近窗口消息
- **THEN** 两者作为两个独立 ContextBlock 注入，分别有各自的 key、priority、compressible、min_tokens，便于 TokenBudget 独立决策
