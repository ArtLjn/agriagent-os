## Context

当前后端每次对话请求都是无状态的。`advisor.py:41` 每次调用只传 `[HumanMessage(content=user_input)]`，没有历史消息。LLM 无法理解追问（如"那个怎么办"指什么）、无法维持上下文连续性。

同时，`Farm.location` 字段已存在于数据库但从未注入 prompt。天气 skill 的 `parameters_schema` 要求传入 `location` 参数，LLM 不知道用户在哪里就无法正确调用。

参考 product-agent 的 `AgentContext` 设计模式（结构化上下文对象 + 会话级状态持久化），结合农场场景的简单性（单用户、单农场），采用**单会话 + 自动过期**方案。

现有相关代码：
- `app/models/agent.py` — `AdviceRecord` 只存 LLM 回复，不存用户输入
- `app/agents/advisor.py` — `invoke_advisor` / `stream_advisor` 无历史注入
- `app/agents/graph.py:57-89` — `_llm_node` 每次重新构建 system prompt，已支持模板变量注入
- `backend/prompts/base.j2` — 已有 `{{ farm_context_summary }}` 和 `{{ display_name }}` 变量
- `app/models/farm.py` — `Farm.location` 字段已存在但未使用

## Goals / Non-Goals

**Goals:**
- 实现单会话模式：app 打开自动创建/复用当前会话，无需用户手动管理
- 持久化完整对话历史（用户输入 + LLM 回复），支持历史回看
- 将最近 N 轮对话注入 LangGraph，实现多轮上下文
- 将用户关键信息（城市/位置、季节、称呼）以结构化格式注入 system prompt
- 控制历史消息 token 开销，避免上下文窗口溢出

**Non-Goals:**
- 不做多会话管理（类似 ChatGPT 的会话列表/切换）
- 不做跨设备会话同步
- 不做会话分享/导出
- 不做用户登录认证（当前 farm_id 通过 API header 识别）
- 不引入 Redis 或外部缓存，使用 SQLite 持久化

## Decisions

### D1: 单会话模式 + 24h 自动过期

**选择**: 每个 farm 同时只有一个活跃会话，24h 无新消息自动关闭

**备选方案**:
- A) 多会话（ChatGPT 模式）→ 农场场景用户通常只有一个话题，多会话增加前端复杂度
- B) 永久单会话 → 历史无限增长，token 开销失控
- C) 每次打开 app 新会话 → 无法利用当天早些时候的对话上下文

**理由**: 24h 窗口覆盖一天的农事活动周期，过期后自动清理避免历史堆积。用户无需理解"会话"概念。

### D2: 最近 10 轮对话注入

**选择**: 注入最近 10 轮对话（10 条 HumanMessage + 10 条 AIMessage = 20 条）

**理由**: 根据成熟项目经验（Anthropic/CrewAI），10 轮约消耗 2000-4000 token（取决于内容长度），qwen3.6-flash 有 1M 上下文窗口，远未触顶。配合 `micro_compact` 对旧 tool result 的压缩，实际开销可控。

### D3: 结构化 XML 格式注入用户上下文

**选择**: 在 `base.j2` 中新增 `<user_context>` XML 段

```xml
<user_context>
  <location>{{ farm.location }}</location>
  <name>{{ display_name }}</name>
  <season>{{ current_season }}</season>
</user_context>
```

**备选方案**:
- A) 自然语言描述 → 更费 token，解析准确度低
- B) JSON 格式 → 比 XML 多 token（引号、逗号、花括号）

**理由**: Anthropic 实测 XML 标签在 prompt 中解析准确度最高，且最省 token。qwen 系列模型对 XML 格式也有良好支持。

### D4: Conversation + ConversationMessage 两表设计

**选择**:
```
conversations: id, farm_id, status(active/closed), created_at, last_active_at
conversation_messages: id, conversation_id, role(user/assistant), content, created_at
```

**理由**: 现有 `AdviceRecord` 只存回复不存输入，且没有会话概念。新建两张表比改造旧表更清晰，旧表保持向后兼容。`last_active_at` 用于过期判断。

### D5: session_id 由前端生成

**选择**: 前端打开 app 时生成 UUID v4 作为 session_id，首次请求后端自动创建 Conversation 记录

**备选方案**:
- A) 后端创建会话返回 session_id → 需要额外的创建会话 API，前端多一次网络请求
- B) 自动用 farm_id + 日期组合 → 不够灵活

**理由**: 前端生成最简单，后端按需创建（lazy creation），无需额外 API。

## Risks / Trade-offs

- **[历史消息过长]** → 10 轮历史在复杂对话中可能超过 4000 token。→ `micro_compact` 已压缩旧 tool result，后续可引入 LLM 摘要压缩
- **[24h 过期丢失上下文]** → 用户隔天回来无法引用昨天的对话。→ 可接受，农场场景每天的农事关注点不同
- **[单会话限制]** → 无法按话题隔离对话（如"天气讨论"和"成本分析"混在一起）。→ 后续可升级为多会话，当前方案向前兼容
- **[location 为空时无城市]** → 老数据 Farm.location 可能为 NULL。→ prompt 中条件渲染，为空时不注入 location 段，LLM 会追问用户所在城市
