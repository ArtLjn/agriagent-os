## Context

### 当前状态

`../../../agri_backend_v2/agent` 已经具备 Prompt Cache、ReAct Turn、Redis 并发协调、Mongo 对话历史和 Trace，但这些机制处在不同层级：

```text
POST /chat
  -> Redis Turn
  -> Worker
  -> react.run_turn
       -> memory.snapshot(local JSON)
       -> context.build_initial_messages
       -> LLM + Tool loop
       -> memory.save_messages(local JSON)
  -> Mongo conversationMessages（仅用户可见消息）
```

主要问题：

- Agent Context 从本地 JSON 读取，用户历史和会话列表从 MongoDB 读取，存在双事实源；
- `memory.py` 以固定消息数截断，未按完整 Turn 和实际 token 做预算；
- `summarizer.py` 生成的摘要以孤立 assistant 消息保存，经过 `_dialogue_messages()` 后可能被丢弃；
- `long_term` 目前只有读取入口，没有稳定的观察、审核和写入生命周期；
- Context usage 只统计 messages，没有统计 Tool Schema、工具结果和模型输出预留；
- 每个 Turn 默认暴露全部可用 Skill Schema，缺少活跃工具候选和 schema 预算治理；
- `react.py` 同时承担 Runtime、Context、Memory 和持久化职责，后续修复容易形成跨层耦合。

### 设计约束

- 保留现有 `/api/v2/chat` 的 `conversation_id` 兼容契约，第一阶段不强制引入新的公开 `session_id`；
- 保留 Redis Turn、SSE replay、HITL 和 Mongo Trace 四集合设计，不把 Trace 变成业务事实源；
- 业务数据仍只能经 Skill/Business MCP 访问，Context 不得整包注入业务表；
- 所有用户、农场、会话记忆必须带 `user_id`、`farm_uid`/`farm_id` 的可信租户范围；
- 设计先覆盖可靠性和可解释性，向量检索、自动长期记忆抽取不作为第一阶段强依赖。

## Goals / Non-Goals

**Goals:**

- 统一 Conversation、Turn、Context、Session Memory、Long-term Memory 的概念和生命周期；
- 建立单一会话事实源、可版本化的 Context 投影和可恢复的滚动摘要；
- 让每次 LLM 调用都在 token 预算内构建 Context，并记录保留、压缩和丢弃决策；
- 让 Worker 重启、SSE 重连、进程扩容、摘要失败和存储部分失败都有明确结果；
- 以现有 v2 代码为落点，明确文件、API、数据、配置、测试和迁移范围；
- 让 Trace 可以回答：模型看到了什么、为什么保留、为什么丢弃、使用了哪个摘要版本。

**Non-Goals:**

- 第一阶段不引入向量数据库、Embedding、RAG 服务或新的外部记忆平台；
- 不把完整 Tool/Observation/Thought 轨迹注入下一轮用户可见对话；
- 不改变 Business MCP 的业务契约和写操作 HITL 规则；
- 不在本次设计阶段直接重写 ReAct 循环；
- 不默认删除 Mongo 中的用户可见历史；`reset` 只重置活跃 Context，硬删除属于独立的数据治理能力。

## Decisions

### D1. 四层模型与边界

采用以下稳定模型：

| 层 | 作用 | 持久性 | 事实源 |
|---|---|---|---|
| Conversation | 用户可见的长期对话边界 | 长期 | Mongo `conversationMessages` + `conversationStates` |
| Turn | 一次用户输入的执行、审批、工具和终态 | Turn TTL 内可恢复 | Redis Turn/Event Stream，终态摘要写 Mongo |
| Context | 一次 LLM 调用的输入投影 | 单次调用 | `ContextBuilder` 计算结果 |
| Memory | 从会话和业务交互中沉淀的可复用事实 | 跨 Turn/Session | `MemoryService`，第一阶段可为空实现 |

外部 API 继续使用 `conversation_id`。在内部把“活跃 Session View”定义为 Conversation 的当前工作记忆投影，而不是新增一个容易与 Turn 混淆的公开 ID。

### D2. 单一事实源与存储职责

引入一个按租户和会话唯一的 `conversationStates` 文档，用于存放会话元数据和最新摘要；不再让本地 JSON 成为生产 Context 来源。

```text
conversationMessages   用户/助手最终可见消息事实
conversationStates     会话状态、summary、summary_revision、reset_generation
Redis Turn/Event       正在运行的 Turn、审批、SSE replay 和并发协调
traceRecords           内部执行节点和受控摘要
traceEvents            语义 SSE 事件投影
memoryRecords          后续长期记忆事实；第一阶段仅保留 MemoryService 接口
```

`conversationMessages` 不保存 Tool 原始结果、Thought 或逐 token 增量。Tool 轨迹由 Trace/Turn 保存，Context 只消费经过裁剪的结构化摘要。

#### Session、Short Memory、Long Memory 的具体存储与注入

当前实现必须明确标记为迁移前状态：`conversation_id` 是公开 Session 标识，但没有独立 Session 文档；活动 Turn 在 Redis；用户可见消息在 Mongo `conversationMessages`；短时记忆在 `../../../agri_backend_v2/agent/core/data/conversations/*.json`；长期记忆在 `../../../agri_backend_v2/agent/core/data/memory.json`，且当前没有稳定写入流程。

目标实现采用以下映射：

| 层 | 目标存储 | 写入时机 | 读取入口 | Context 注入 |
|---|---|---|---|---|
| Session metadata | Mongo `conversationStates` | 创建/更新/reset/过期 | `MemoryService.get_session_view()` | revision、status，不直接拼全文 |
| Short Memory recent turns | Mongo `conversationMessages` | 用户消息和最终答复终态写入 | `get_session_view()` | `recent_turns` system block |
| Short Memory summary | `conversationStates.summary` | 窗口/预算超阈值后 CAS 写入 | `get_session_view()` | `session_summary` system block |
| Short Memory pending/task | Redis Turn + `conversationStates` | 审批/计划状态变化 | `get_session_view()` + Turn restore | `pending_action`/`active_task_state` |
| Long Memory observation | Mongo `memoryObservations` 或队列 | Turn finalization 后幂等追加 | Memory worker | 默认不注入 |
| Long Memory facts | Mongo `memoryRecords` | 确认/提交/审核后 upsert | `MemoryService.search()` | 按需 `memory_hits` block |

注入顺序必须保持：静态 system contract → Tool Schema → hot context → pending/task → session summary → recent turns → 当前 user task；同一 Turn 的 observation 作为动态内容追加。Long Memory hits 只在 ContextPolicy/Skill dependency 触发时追加，且低于当前任务和最近观察的优先级。

Short Memory 不能直接注入完整 Tool payload；Long Memory 不能直接注入未经确认的摘要。两者均需通过 MemoryService 返回带 `source_status`、`revision`、`scope` 和 token 预算信息的投影。

### D3. ContextBundle 与 ContextBlock

每次 LLM 调用前由 ContextBuilder 构建新的 `ContextBundle`。Turn 内的基础会话快照带版本号，工具调用和观察结果作为当前 Turn 动态部分追加。

```json
{
  "conversation_id": "conv_01",
  "turn_id": "turn_01",
  "conversation_revision": 42,
  "summary_revision": 7,
  "blocks": [
    {
      "key": "session_summary",
      "source": "conversationStates.summary",
      "priority": 30,
      "required": false,
      "compressible": true,
      "estimated_tokens": 420,
      "status": "included",
      "fresh_until": "2026-08-20T12:00:00Z"
    }
  ],
  "budget": {
    "model_context_tokens": 32000,
    "response_reserve_tokens": 4096,
    "safety_margin_tokens": 1024,
    "used_tokens": 6800,
    "decision": "within_budget"
  }
}
```

标准 Block 顺序：

1. `system_contract`：身份、安全、输出和工具规则；
2. `tool_schema`：当前活跃能力的 Schema；
3. `task_input`：当前用户请求；
4. `hot_context`：可信用户、农场、位置、时间等低 token 信息；
5. `pending_action`：待审批写操作和过期时间；
6. `session_summary`：窗口外历史的滚动摘要；
7. `recent_turns`：最近完整 Turn 原文；
8. `memory_hits`：按需检索的长期事实；
9. `turn_observations`：本轮工具观察和动态提醒。

每个 Block 必须有 `source`、`priority`、`required`、`compressible`、`estimated_tokens`、`status` 和 `drop_reason`。不可把“当前 Context”直接当作一个不可解释的字符串。

### D4. Token 预算与压缩

预算定义为：

```text
usable = model_context - response_reserve - safety_margin
```

预算器必须计算消息、Tool Schema、工具结果和结构化开销。决策顺序为：

1. 保留 `required` Block；
2. 保留当前任务、审批状态和最近 Turn；
3. 压缩旧 Turn 和旧工具结果；
4. 丢弃低优先级、过期或非当前意图相关的 Block；
5. 仍超预算时返回结构化 `context_budget_exceeded`，不得静默发送超限请求。

建议默认值由配置提供而非散落在代码中：

```text
recent_turn_limit = 6
summary_soft_ratio = 0.60
summary_hard_ratio = 0.80
response_reserve_tokens = 4096
safety_margin_tokens = 1024
max_tool_result_summary_chars = 1200
```

### D5. 短时记忆采用“完整 Turn + 滚动摘要”

不再使用本地文件或固定消息数作为生产策略。一个完整 Turn 至少包含用户输入和最终 assistant 答复；Tool 结果只保留结构化摘要或引用。

窗口外历史进入 `conversationStates.summary`，摘要记录：

- `summary_revision`；
- `source_from_message_id`、`source_to_message_id`；
- `source_conversation_revision`；
- `content`、`content_hash`；
- `generated_by`、`created_at`、`expires_at`；
- `status`：`ready`、`stale`、`failed`。

摘要写入使用 `source_conversation_revision` CAS。旧摘要不能覆盖新消息；摘要失败只降级为最近窗口。

### D6. 长期 Memory 与会话记忆隔离

第一阶段只实现 `MemoryService` 端口、空结果和 observation 事件，不强制接入向量检索。长期事实必须按 `user`、`farm` 或领域范围存储，不按 conversation 独占。

允许沉淀的事实包括明确用户偏好、稳定农场配置、已确认业务实体和已提交操作结果；禁止沉淀模型猜测、审批前参数、临时天气结果和工具失败推断。

Long Memory 的写入链路固定为 `Turn Finalizer -> MemoryObservation -> eligibility check -> optional review/fact extraction -> memoryRecords upsert`；读取链路固定为 `ContextPolicy -> MemoryService.search(scope, query, dependencies) -> memory_hits Block`。Long Memory 不写入 `recent_turns`，也不默认注入每个请求。

### D7. 工具 Schema 按需暴露

`SkillLoader` 负责发现，`SkillRegistry` 负责运行时能力索引，Context/Policy 层负责决定当前候选工具集合。第一阶段允许保留兼容的全量模式，但必须记录 `tool_schema_mode=all|candidate`；切换到 candidate 模式后，按请求意图、Skill metadata 和安全策略计算候选集合。

写工具、HITL 后继动作和有依赖的工具不得因为预算裁剪而失去安全约束；被裁剪的工具必须在 Trace 中记录原因。

### D8. reset、过期和重启语义

- `/api/v2/reset` 增加 `reset_generation`，清理当前 Session View、pending action 和会话摘要；Mongo 用户可见历史默认保留；
- 活跃上下文按 idle TTL 过期，过期只停止自动注入旧窗口，历史仍可通过 summary/replay 查询；
- Worker 重启从 Redis Turn 状态和 Mongo Conversation Snapshot 恢复，不依赖本地进程内列表；
- SSE 重连只重放同一 Turn 事件，不重新创建 Turn 或追加重复消息；
- 版本冲突时拒绝旧写入并记录 `stale_context`，不能静默覆盖新状态。

### D9. Runtime 依赖 Memory/Context 服务接口

将 `react.py` 中直接调用 `memory.snapshot()` 和 `memory.save_messages()` 收敛为 Runtime application 层提供的接口。Runtime 只接收 `TurnRuntime` 和 `ContextBundle`，不直接知道 Mongo、JSON 或向量索引。

初期可使用 adapter 保持现有测试替身兼容，但 adapter 必须是唯一存储入口，并支持 shadow-read、fallback 和迁移统计。

### D10. Trace 作为设计验收的一部分

每次 Context 构建至少记录：

- `conversation_revision`、`summary_revision`、`memory_revision`；
- 候选/保留/压缩/丢弃 Block；
- 每个 Block token 估算和 drop reason；
- Tool Schema 数量、版本和暴露模式；
- Context source：Mongo、Redis、fallback 或 unavailable；
- summary 触发原因、耗时、CAS 结果和失败分类。

Trace 只保存脱敏摘要，不保存凭证、完整隐藏思维链或无限大的 Tool payload。

## Risks / Trade-offs

- **[Mongo 读取增加延迟]** → 对 `conversationStates` 和消息分页建立索引；在单 Turn 内缓存不可变 Snapshot；必要时使用 Redis 只读缓存，但 Redis 不是事实源。
- **[摘要有损导致实体 ID 丢失]** → 最近完整 Turn 原文优先；摘要 schema 强制保留实体 ID、状态、待办和来源范围；为关键 ID 增加回归测试。
- **[摘要任务与 Turn 写入竞争]** → 使用 `source_conversation_revision` CAS 和幂等 summary key，禁止无版本覆盖。
- **[全量工具 Schema 迁移后模型召回下降]** → 先 shadow 记录 candidate 集合与全量选择结果，按评测集灰度切换。
- **[Conversation snapshot 与活动 Turn 不一致]** → 记录 source divergence；以 Mongo Conversation snapshot 为事实源，Redis 只提供活动 Turn 和 replay 状态。
- **[Context trace 增加 payload 成本]** → 只记录 block metadata、hash、token 和受控 preview；不逐 token 记录。
- **[reset 后用户仍能看到旧历史产生歧义]** → API 返回明确的 `reset_generation` 和“仅重置 Agent 工作记忆”语义；硬删除单独设计。

## Migration Plan

### Phase 0：契约和观测（可回滚）

1. 增加 `ContextBlock`、`ContextBundle`、`ConversationSnapshot`、`MemoryObservation` 数据结构和接口；
2. 不改变现有 Runtime 行为，shadow 计算 block、token、summary revision 和 Mongo/JSON 差异；
3. 增加 `context_source_status`、`summary_status`、`memory_source_status` Trace 字段。

### Phase 1：摘要正确性和 Conversation State

1. 创建 `conversationStates` 集合及租户/会话唯一索引；
2. 把摘要从伪 assistant 消息迁移为独立字段；
3. 使用 CAS 写入摘要，增加摘要恢复、失败和并发测试；
4. `/reset` 改为重置 active view 和 generation，不删除可见历史。

### Phase 2：统一读取路径

1. Memory adapter 只从 Mongo Conversation Snapshot 读取；
2. Mongo 不可用时返回 `unavailable`，由 application 按策略决定当前 Turn 是否继续；
3. 完成真实重启、多 Worker 和 source divergence 验收；
4. 不保留本地 JSON fallback 或对应 feature flag。

### Phase 3：预算与按需工具 Schema

1. 接入真实模型 tokenizer 或校准估算器；
2. 计入 messages、tools、tool results 和 response reserve；
3. 启用最近 Turn + summary 的压缩策略；
4. 先灰度 candidate tool schema，再逐步关闭全量暴露。

### Phase 4：长期 Memory 与数据治理

1. 接入 observation queue 和长期事实审核策略；
2. 仅实现用户/农场事实的有限类型；
3. 后续再评估关键词/向量检索，不把 RAG 作为短时记忆前置条件。

### 回滚策略

- 运行时只保留业务能力开关：`candidate_tool_schema`、`long_term_memory_observation`；Session/Short Memory 不通过迁移开关切换事实源；
- 发现 Context 质量下降时可退回全量 Tool Schema，但保留 Trace 和预算统计；
- 发现 Mongo 读异常时必须返回 `unavailable`，由 application 明确选择继续当前 Turn 或终止；
- 任何回滚不得删除已写入的 Mongo 消息、摘要或 Trace。

## Open Questions

- `conversationStates` 是否与现有 Mongo 四集合一起作为第五个逻辑集合，还是在现有会话集合中增加专门的 state 文档，需要在 DDL 评审时确定；
- 是否由 Agent 服务提供摘要 LLM，还是由独立 Memory Worker 提供低成本模型，需要结合部署资源和成本确认；
- 当前各模型真实 Context Window 和 tokenizer 是否都能通过网关 usage 获取，需要先完成模型校准；
- `reset` 是否需要追加“硬删除可见历史”的管理员接口，不属于本次第一阶段；
- candidate Tool Schema 的初始召回策略采用 metadata 规则、LLM router 还是两者混合，需要基于现有 Skill 数量和回放集确定。
