## Why

当前后端每次对话请求都是无状态的：只传当前用户消息（`[HumanMessage(content=user_input)]`），没有历史对话上下文。LLM 无法理解追问、指代消解，也无法维持连贯的多轮对话。同时，system prompt 缺少用户关键信息（所在城市/位置），导致天气 skill 无法获取正确的 location 参数。随着 function calling 即将启用，这两个问题会直接影响用户体验。

## What Changes

- 新增 `Conversation` 和 `ConversationMessage` 数据模型，持久化用户与 Agent 的完整对话历史
- `ChatRequest` 增加 `session_id` 字段，支持前端传入会话标识
- 采用**单会话模式**：打开 app 自动创建/复用当前会话，24h 无活动自动过期
- `invoke_advisor` / `stream_advisor` 调用时注入最近 N 轮对话历史，实现多轮上下文
- `base.j2` 新增 `<user_context>` 段，注入用户所在城市、季节等结构化上下文
- `Farm.location` 字段已存在但未使用，现将其注入 prompt 并传递给 skill

## Capabilities

### New Capabilities
- `conversation-management`: 会话生命周期管理（创建、复用、过期、历史查询），多轮对话历史持久化与注入
- `user-context-injection`: 将用户信息（城市/位置、季节、称呼）以结构化 XML 格式注入 system prompt

### Modified Capabilities
- `prompt-template-management`: `base.j2` 新增 `<user_context>` 段，注入结构化用户上下文

## Impact

- **数据库**：新增 `conversations` 和 `conversation_messages` 两张表
- **API**：`POST /agent/chat` 和 `POST /agent/chat/stream` 的 `ChatRequest` 新增 `session_id` 可选字段；新增 `GET /agent/conversations` 和 `GET /agent/conversations/{id}/messages` 接口
- **Agent 层**：`advisor.py` 的 `invoke_advisor` / `stream_advisor` 需要加载历史消息注入 LangGraph
- **Prompt**：`base.j2` 新增 `<user_context>` 段
- **前端**：需要在 app 打开时生成或复用 session_id，并在每次请求时携带
