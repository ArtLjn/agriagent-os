## MODIFIED Requirements

### Requirement: 会话摘要输入短时记忆
Conversation 模块 SHALL 为 Memory 短时记忆提供最近完整 Turn、版本化会话摘要、pending action 和 Conversation revision。Agent SHALL 通过 Memory 或 Context 边界消费这些信息，而不是直接在 Runtime 中查询消息表。

#### Scenario: 注入最近会话
- **WHEN** Agent 处理同一 conversation 的追问
- **THEN** 短时记忆提供最近窗口、可用摘要和 source status 给 Context Builder

### Requirement: 对话观察事件
对话完成后，Conversation 或 Agent application SHALL 向 Memory 提交幂等 observation event，供后续摘要和事实沉淀使用；事件必须关联 conversation revision 和 turn id。

#### Scenario: 保存回复后观察
- **WHEN** 用户消息和助手回复已经持久化
- **THEN** 系统提交包含本轮交互内容摘要和 metadata 的 Memory observation event，并在失败时记录待重试状态

### Requirement: 多轮对话历史注入 LangGraph
Agent Runtime SHALL 通过短时记忆策略向运行时注入当前 conversation 的工作记忆。工作记忆 SHALL 包含最近完整 Turn，并在历史超过窗口或 token 预算时使用会话摘要替代更早历史。系统不得仅按固定条数无预算地注入完整历史。

#### Scenario: 首次对话无历史
- **WHEN** 新 conversation 首次调用 Agent
- **THEN** Runtime 只收到当前用户消息、必要热上下文和工具候选，不注入不存在的历史

#### Scenario: 有历史时注入上下文
- **WHEN** 会话已有 5 轮对话，用户发送第 6 条消息
- **THEN** Runtime 收到预算内的最近完整 Turn、会话摘要和当前用户消息

#### Scenario: 历史超过窗口时摘要替代
- **WHEN** 会话历史超过最近 Turn 窗口
- **THEN** Runtime 收到窗口内原文和窗口外摘要候选；若预算不足，摘要可被压缩或丢弃但必须记录原因

#### Scenario: 追问理解上下文
- **WHEN** 用户先问“明天天气”，LLM 回复后，用户追问“后天呢”
- **THEN** LLM 能根据短时记忆理解“后天”指的是天气，并正确调用天气 skill

#### Scenario: 工具结果过长
- **WHEN** 历史消息中包含超过预算的大型 ToolMessage
- **THEN** 系统将旧工具结果压缩为执行摘要或通过 Trace 标记丢弃，不得把完整大型工具结果无预算注入 Runtime

## ADDED Requirements

### Requirement: Conversation lifecycle and reset
系统 SHALL 管理 Conversation 的 `active`、`idle`、`closed`、`expired` 和 `reset` 语义。reset 默认只清理活跃 Context，不删除用户可见历史；过期只停止旧工作记忆自动注入。

#### Scenario: Reset then continue
- **WHEN** 用户 reset 后继续发送消息
- **THEN** 新 Turn 使用新的 reset generation，不注入旧 pending action 或旧 summary，同时历史查询仍可返回保留的用户可见消息

### Requirement: Conversation message fact source
用户和助手最终可见消息 SHALL 以 `conversationMessages` 为唯一产品事实源；会话列表、详情和 Memory projection 必须使用相同租户过滤条件。

#### Scenario: Mongo and Memory consistency
- **WHEN** 用户可见消息已经成功写入 Mongo
- **THEN** 后续新 Worker 构建 Context 时能够从该事实源读取消息或其已确认摘要；读取失败必须暴露 source status

### Requirement: Reconnect and worker recovery
会话重连或 Worker 恢复 MUST 复用原 `turn_id`、`trace_id` 和 `conversation_revision`，不得重复创建用户消息、assistant 最终消息或 Memory observation。

#### Scenario: SSE reconnect
- **WHEN** 客户端携带 `after_seq` 重连正在运行或已终态 Turn
- **THEN** 系统只重放缺失事件，且不会重新执行工具或追加重复会话消息
