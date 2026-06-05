## ADDED Requirements

### Requirement: 多轮对话历史注入 LangGraph
`invoke_advisor` / `stream_advisor` 调用时 SHALL 通过短时记忆策略向 LangGraph 注入当前 session 的工作记忆。工作记忆 SHALL 包含最近消息窗口，并在历史超过窗口或 token 预算时使用会话摘要替代更早历史。系统不得仅按固定条数无预算地注入完整历史。

#### Scenario: 首次对话无历史
- **WHEN** 新会话首次调用 `invoke_advisor`
- **THEN** LangGraph 只收到当前用户消息和必要热上下文，无历史消息

#### Scenario: 有历史时注入上下文
- **WHEN** 会话已有 5 轮对话，用户发送第 6 条消息
- **THEN** LangGraph 收到最近窗口内的历史消息、当前用户消息和符合 token 预算的工作记忆

#### Scenario: 历史超过窗口时摘要替代
- **WHEN** 会话历史超过最近消息窗口
- **THEN** LangGraph 收到窗口内原文消息，并收到窗口外历史的会话摘要候选；若预算不足，摘要可被压缩或丢弃

#### Scenario: 追问理解上下文
- **WHEN** 用户先问"明天天气"，LLM 回复后，用户追问"后天呢"
- **THEN** LLM 能根据短时记忆理解"后天"指的是天气，正确调用天气 skill

#### Scenario: 工具结果过长
- **WHEN** 历史消息中包含超过预算的大型 ToolMessage
- **THEN** 系统将旧工具结果压缩为执行摘要或通过 trace 标记丢弃，不得把完整大型工具结果无预算注入 LangGraph
