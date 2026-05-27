## ADDED Requirements

### Requirement: 会话自动创建与复用
系统 SHALL 为每个 farm 维持至多一个活跃会话。当前端携带 `session_id` 发送消息时，若该 session_id 对应的会话存在且状态为 `active`，SHALL 复用该会话；若不存在，SHALL 自动创建新会话并同时关闭该 farm 的其他活跃会话。

#### Scenario: 首次请求自动创建会话
- **WHEN** 前端发送 `POST /agent/chat`，携带新的 `session_id`，该 farm 当前无活跃会话
- **THEN** 系统创建 `Conversation` 记录（status=active, farm_id=当前农场），消息写入 `conversation_messages`

#### Scenario: 复用已有活跃会话
- **WHEN** 前端发送消息，携带的 `session_id` 对应的会话状态为 `active` 且 `farm_id` 匹配
- **THEN** 系统将消息追加到该会话，更新 `last_active_at`

#### Scenario: 新会话自动关闭旧会话
- **WHEN** 前端发送消息携带新的 `session_id`，但该 farm 已有另一个活跃会话
- **THEN** 系统将旧会话状态设为 `closed`，创建新会话并追加消息

#### Scenario: 未携带 session_id 时使用当前活跃会话
- **WHEN** 前端发送 `POST /agent/chat` 未携带 `session_id`，该 farm 有活跃会话
- **THEN** 系统复用该活跃会话

#### Scenario: 未携带 session_id 且无活跃会话
- **WHEN** 前端发送 `POST /agent/chat` 未携带 `session_id`，该 farm 无活跃会话
- **THEN** 系统自动生成 session_id 并创建新会话

### Requirement: 会话自动过期
活跃会话若连续 24 小时无新消息 SHALL 自动关闭。系统在每次写入消息时检查并关闭过期会话。

#### Scenario: 24h 无活动后下次请求触发过期
- **WHEN** 某活跃会话的 `last_active_at` 距当前超过 24 小时，用户发送新消息
- **THEN** 系统将该会话状态设为 `closed`，为当前 farm 创建新会话

#### Scenario: 24h 内继续对话
- **WHEN** 某活跃会话的 `last_active_at` 距当前不超过 24 小时，用户发送新消息
- **THEN** 会话保持 active，`last_active_at` 更新为当前时间

### Requirement: 对话消息持久化
每次对话交互 SHALL 同时持久化用户输入和 LLM 回复到 `conversation_messages` 表。每条消息记录 `role`（user/assistant）、`content`、`created_at`。

#### Scenario: 完整对话记录
- **WHEN** 用户发送"明天天气怎么样"，LLM 回复天气信息
- **THEN** `conversation_messages` 表新增两条记录：role=user + role=assistant，content 分别为用户输入和 LLM 回复

#### Scenario: 流式对话同样持久化
- **WHEN** 用户通过 `POST /agent/chat/stream` 发送消息
- **THEN** 流式完成后，用户输入和完整 LLM 回复均写入 `conversation_messages`

### Requirement: 多轮对话历史注入 LangGraph
`invoke_advisor` / `stream_advisor` 调用时 SHALL 从 `conversation_messages` 加载当前会话最近 10 轮对话（20 条消息），作为历史上下文注入 LangGraph 的 messages 列表。

#### Scenario: 首次对话无历史
- **WHEN** 新会话首次调用 `invoke_advisor`
- **THEN** LangGraph 只收到当前用户消息，无历史消息

#### Scenario: 有历史时注入上下文
- **WHEN** 会话已有 5 轮对话，用户发送第 6 条消息
- **THEN** LangGraph 收到最近 10 轮（实际 5 轮）历史消息 + 当前用户消息

#### Scenario: 历史超过 10 轮时截断
- **WHEN** 会话已有 15 轮对话，用户发送新消息
- **THEN** LangGraph 只收到最近 10 轮（第 6-15 轮）历史 + 当前消息，更早的历史不注入

#### Scenario: 追问理解上下文
- **WHEN** 用户先问"明天天气"，LLM 回复后，用户追问"后天呢"
- **THEN** LLM 能根据历史上下文理解"后天"指的是天气，正确调用天气 skill

### Requirement: 会话历史查询 API
系统 SHALL 提供 `GET /agent/conversations` 接口返回当前 farm 的会话列表（按 last_active_at 倒序），以及 `GET /agent/conversations/{session_id}/messages` 返回指定会话的完整消息列表。

#### Scenario: 查询会话列表
- **WHEN** 前端调用 `GET /agent/conversations`
- **THEN** 返回当前 farm 的所有会话（id, session_id, status, created_at, last_active_at），按 last_active_at 倒序，最多返回 20 条

#### Scenario: 查询会话消息
- **WHEN** 前端调用 `GET /agent/conversations/{session_id}/messages`
- **THEN** 返回该会话的所有消息（id, role, content, created_at），按 created_at 正序

#### Scenario: 查询不存在的会话
- **WHEN** 前端调用 `GET /agent/conversations/nonexistent-id/messages`
- **THEN** 返回 404

### Requirement: ChatRequest 支持 session_id
`ChatRequest` schema SHALL 新增可选字段 `session_id: str | None = None`，前端可选择传入。

#### Scenario: 携带 session_id
- **WHEN** 前端发送 `{"message": "你好", "session_id": "abc-123"}`
- **THEN** 后端使用该 session_id 查找或创建会话

#### Scenario: 不携带 session_id
- **WHEN** 前端发送 `{"message": "你好"}`
- **THEN** 后端查找当前 farm 的活跃会话，不存在则自动创建
