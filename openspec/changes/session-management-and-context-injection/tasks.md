## 1. 数据模型：Conversation + ConversationMessage

- [ ] 1.1 创建 `app/models/conversation.py`，定义 `Conversation` 模型（id, farm_id, session_id, status, created_at, last_active_at）
- [ ] 1.2 定义 `ConversationMessage` 模型（id, conversation_id, role, content, created_at），role 为枚举 user/assistant
- [ ] 1.3 在 `app/models/__init__.py` 中导入新模型，确保 Alembic 迁移能识别
- [ ] 1.4 生成并执行 Alembic 迁移脚本

## 2. 会话服务层

- [ ] 2.1 创建 `app/services/conversation_service.py`，实现 `get_or_create_conversation(farm_id, session_id)` — 查找活跃会话或创建新会话并关闭旧会话
- [ ] 2.2 实现 `close_expired_conversations(farm_id)` — 关闭 24h 无活动的活跃会话
- [ ] 2.3 实现 `save_message(conversation_id, role, content)` — 持久化单条消息
- [ ] 2.4 实现 `get_recent_messages(conversation_id, limit=20)` — 获取最近 N 条消息（按 created_at 正序）
- [ ] 2.5 实现 `list_conversations(farm_id, limit=20)` — 返回会话列表（按 last_active_at 倒序）
- [ ] 2.6 实现 `get_conversation_messages(session_id)` — 返回指定会话的完整消息列表

## 3. ChatRequest 扩展与 API

- [ ] 3.1 `app/schemas/agent.py` — `ChatRequest` 新增 `session_id: str | None = None`
- [ ] 3.2 `app/api/agent.py` — `agent_chat` 和 `agent_chat_stream` 接口从 `ChatRequest` 取 `session_id`，调用 `conversation_service` 获取/创建会话
- [ ] 3.3 `app/api/agent.py` — `agent_chat` 在 LLM 回复后调用 `save_message` 分别存 user 和 assistant 消息
- [ ] 3.4 `app/api/agent.py` — `agent_chat_stream` 在流式完成后存 user 和 assistant 消息
- [ ] 3.5 新增 `GET /agent/conversations` 接口，返回当前 farm 的会话列表
- [ ] 3.6 新增 `GET /agent/conversations/{session_id}/messages` 接口，返回指定会话的消息列表
- [ ] 3.7 新增 `app/schemas/agent.py` 对应的 response schema（ConversationListItem, ConversationMessageItem）

## 4. 多轮对话注入 Agent 层

- [ ] 4.1 `app/agents/advisor.py` — `invoke_advisor` 接受 `conversation_id` 参数，从 `conversation_service.get_recent_messages` 加载最近 20 条消息
- [ ] 4.2 `app/agents/advisor.py` — 将历史消息转为 `[HumanMessage/AILessage]` 列表，追加当前用户消息后传入 LangGraph
- [ ] 4.3 `app/agents/advisor.py` — `stream_advisor` 同样接受 `conversation_id` 并注入历史
- [ ] 4.4 `app/services/agent_service.py` — `chat_with_agent` 传递 `conversation_id` 给 `invoke_advisor`

## 5. 用户上下文注入 Prompt

- [ ] 5.1 `prompts/base.j2` — 新增 `<user_context>` XML 段，条件渲染 `{{ farm_location }}`、`{{ display_name }}`、`{{ current_season }}`
- [ ] 5.2 `app/agents/graph.py` — `_llm_node` 从 `Farm.location` 取值，计算当前季节，传入 `render_prompt` 的 `variables`
- [ ] 5.3 `app/core/prompt_registry.py` — 更新内置默认 prompt 的 `_DEFAULT_PROMPTS["system_base"]`，包含 `<user_context>` 段

## 6. 端到端验证

- [ ] 6.1 测试：首次对话无历史时正常回复
- [ ] 6.2 测试：连续 2 轮对话后，LLM 能理解追问（如"明天天气" → "后天呢"）
- [ ] 6.3 测试：24h 过期后新消息触发创建新会话
- [ ] 6.4 测试：`<user_context>` 中 location 正确渲染
- [ ] 6.5 测试：location 为空时不渲染 location 节点
- [ ] 6.6 测试：天气 skill 使用注入的城市调用
