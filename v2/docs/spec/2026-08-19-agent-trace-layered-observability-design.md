---
spec_id: 2026-08-19-agent-trace-layered-observability-design
last_updated: 2026-08-19
status: proposed
---

# v2 Agent 分层 Trace、Skill Router 与存储调用观测设计

本文补充并细化：

- [v2 Agent Trace、SSE 观测与链路召回设计](./2026-08-18-agent-trace-observability-and-recall-design.md)
- [v2 Agent MongoDB 集合与关联设计](./2026-08-18-agent-mongo-collection-and-link-design.md)

本文先规定目标模型和落地边界，不代表所有字段已经在运行代码中实现。当前实现状态以 `v2/agent/infra/trace/`、`v2/agent/infra/turn_store.py` 和 `v2/agent/core/react.py` 为准。

## 1. 结论先行

当前 Trace 页面只有 `LLM -> tool -> LLM -> outcome` 四个节点，是因为 collector 只记录了 LLM、Tool、commit/outcome 等少数逻辑节点；SSE 状态主要进入 Redis Stream，再异步投影到 `traceEvents`，而 Router、上下文构建、排队等待、审批等待、MCP 重试和存储调用没有形成可关联的执行层级。

因此问题不是简单地“再加几个节点”，而是当前模型缺少三种不同事实的边界：

| 类型 | 记录什么 | 是否有持续时间 | 页面默认展示 |
|---|---|---:|---|
| Span / Node | 一次有开始和结束的执行操作 | 是 | 展示逻辑层，资源层折叠 |
| Event | 某个时刻发生的状态变化或事实 | 否 | 进入时间线和事件抽屉 |
| Metric | 聚合后的计数、耗时和损耗 | 否 | 展示在 Trace summary |

目标结构如下：

```text
Conversation
└── Turn / Trace root
    ├── admission / queue_wait
    ├── skill_router
    │   ├── catalog_recall
    │   ├── policy_guard
    │   └── planner.draft (可选)
    ├── context_build
    ├── llm_call
    │   └── provider HTTP resource span
    ├── skill_call / tool_call
    │   ├── approval_wait (可选)
    │   ├── mcp_call
    │   │   └── business HTTP / DB resource spans
    │   └── observation
    ├── business_commit / finalization
    └── turn_outcome

Redis Stream ──实时重放源──> SSE
       └────异步投影────> traceEvents
Mongo traceRecords ─────> 节点与资源 span
Mongo traceRequestSummaries -> 列表和聚合指标
Mongo conversationMessages -> 用户可见对话事实
```

核心判断：

1. 应该设计成可观测的 Skill Router 链路，但当前 `SkillLoader -> SkillRegistry -> LLM tool call` 是隐式 Router，Trace 先记录“路由决策阶段”，不应虚构一个不存在的运行时模块。
2. Mongo、Redis、业务 MySQL 的关键调用应该生成子 span，但不应该把每条低层读写都变成页面顶层节点。
3. Redis 负责在线状态和 SSE 短期重放，Mongo 负责长期 Trace 诊断；Trace 不能反过来成为 Redis 或业务 MySQL 的一致性来源。
4. 现有四个 Mongo 集合足够支撑第一阶段，不新增 `conversationTraces` 或 `traceResources` 集合；资源调用放入 `traceRecords`，用 `span_kind=client` 和 `layer=resource` 区分。
5. 现有设计文档已经定义了 `span_id` 和 `parent_span_id`，但当前 collector 实际还没有写入它们。补齐父子关系是 UI 扩展前的第一优先级。

## 2. 现状诊断

### 2.1 v1 与公司项目的可复用部分

`archive/backend/app/infra/trace_collector.py` 的优点是节点输入、输出、耗时和 token 统一采集；缺点是没有 span 层级、父节点、重试 attempt、phase 和资源信息，DAO 队列失败时还会丢失诊断证据。

`/Users/ljn/Desktop/aispeech/shs/product-agent/src/storage/trace_dao.py` 值得保留的模式有：

- `parentId` + `depth` 还原执行树；
- `llm_call`、`tool_call`、`http_call`、`mongo_call`、`redis_call` 统一记录；
- 有界批量队列、队列 backlog 指标和 TTL；
- 查询按 session、record、request、node、status 和时间范围组合；
- 嵌套 payload 截断，避免单个输入或输出拖垮写入。

不直接照搬的部分：

- 单集合模型不区分 v2 的对话事实、SSE 事件事实和执行节点事实；
- 所有底层资源调用都作为同等级节点，页面会变成数据库调用清单；
- `recordId`、`requestId`、`sessionId` 语义与 v2 的 `trace_id`、`turn_id`、`conversation_id` 不同，不能直接混用。

### 2.2 v2 当前缺口

当前 v2 collector 已有 `traceRecords`、`traceEvents` 和批量写入，但存在以下观测缺口：

| 缺口 | 现象 | 影响 |
|---|---|---|
| 没有 `span_id` / `parent_span_id` | 节点按 `step_index` 平铺 | 无法回答“哪个 Router 决定了这个 Tool” |
| 没有独立 Router span | SkillRegistry 只提供能力快照 | 看不到候选、过滤、风险和选择原因 |
| 没有 Context span | 输入只有 `message_count` 等摘要 | 无法确认模型实际收到哪些历史、记忆和工具 schema |
| 资源调用不关联 | MCP、Redis、Mongo 调用没有 Trace 子节点 | 无法区分 Agent 慢、业务慢、排队慢 |
| `turn.emit()` 不等于持久事件 | 只有 `publish_event()` 进入 Redis/traceEvents | 调试时不能把本地事件列表当长期证据 |
| SSE 投影异步 | `record_event()` 返回 `persisted=false` | 页面必须展示投影状态，不能宣称事件已落库 |
| summary 只按节点聚合 | 事件损耗、重连、队列等待不完整 | 看到“成功”但无法解释过程中的缺失 |

## 3. 观测模型与字段规范

### 3.1 Trace、Turn、Span、Event 的关系

```text
conversation_id  1 ── N  turn_id
turn_id          1 ── 1  trace_id
trace_id         1 ── N  span_id
span_id          1 ── N  event_id
trace_id         1 ── N  seq/event_id
```

字段语义继续遵守既有规范：

- `conversation_id`：多轮会话主键；
- `turn_id`：一轮 Agent 执行主键；
- `trace_id`：一轮诊断链路主键，重连和 Worker 恢复不变；
- `transport_request_id`：一次 HTTP/SSE 连接，不能代替 Trace；
- `span_id`：一次有持续时间的执行操作；
- `event_id`：一个语义事件，重放时保持不变；
- `seq`：Turn 内单调事件序号，不能使用 Redis Stream ID 代替。

### 3.2 `traceRecords` 统一字段

在现有字段上增加以下结构化字段：

```json
{
  "schema_version": 2,
  "trace_id": "trace_turn_01",
  "turn_id": "turn_01",
  "conversation_id": "conv_01",
  "span_id": "span_01",
  "parent_span_id": "span_root",
  "span_kind": "internal",
  "layer": "agent",
  "node_type": "skill_router",
  "node_name": "skill_router.r1",
  "phase": "reasoning",
  "step_index": 0,
  "attempt": 1,
  "status": "success",
  "start_time": "2026-08-19T10:00:00Z",
  "end_time": "2026-08-19T10:00:00.040Z",
  "duration_ms": 40,
  "input_summary": {},
  "output_summary": {},
  "attributes": {},
  "resource": {},
  "token_usage": null,
  "error": null,
  "payload_ref": null,
  "sampling": {"level": 1, "redacted": true},
  "created_at": "2026-08-19T10:00:00Z"
}
```

字段规则：

| 字段 | 允许值/内容 | 规则 |
|---|---|---|
| `span_kind` | `root`、`internal`、`client` | `client` 表示 MCP/HTTP/DB/Redis 等外部资源调用 |
| `layer` | `agent`、`resource` | UI 默认只展开 `agent` |
| `node_type` | 见下表 | 使用稳定枚举，不把动态名称放进类型 |
| `attributes` | 低基数结构化字段 | 不放完整 SQL、token、密钥或无限动态列表 |
| `input_summary` | 脱敏摘要 | 完整对话仍在 `conversationMessages`；必要 payload 采用引用 |
| `output_summary` | 脱敏摘要 | LLM 输出可保存受限正文和哈希，不能保存隐藏思维链 |
| `resource` | system/operation/collection/route | 只描述资源，不保存凭据 |
| `payload_ref` | 外部对象引用 | 第一阶段可以为空，不能伪造已保存的引用 |
| `sampling` | level/redacted/reason | 让 UI 知道内容缺失是策略还是写入失败 |

逻辑节点枚举：

```text
trace_root, admission, queue_wait, skill_router, catalog_recall,
policy_guard, planner_draft, context_build, llm_call, skill_call,
tool_call, approval, observation, business_commit, finalization,
turn_outcome
```

资源节点枚举：

```text
mcp_call, http_client, llm_provider, redis_command, redis_stream,
mongo_read, mongo_write, mysql_read, mysql_write, trace_persist
```

`trace_persist` 默认只用于 Trace writer 自身健康诊断，不挂到业务主链路的“成功/失败”结论上，避免“写 Trace 的操作又被 Trace 无限递归”。

### 3.3 `traceEvents` 补充字段

保留现有 SSE envelope，增加：

```text
span_id, parent_span_id, event_name, replayed, projection_status,
payload_meta, transport_request_id
```

约束：

- `span_id` 表示该事件属于哪个执行节点；找不到时允许为空，但必须有 `trace_id` 和 `turn_id`；
- `replayed=true` 只代表本次 SSE 读取是重放，不产生新的 `event_id` 或 `seq`；
- `projection_status` 取 `queued`、`persisted`、`retrying`、`dropped`、`unavailable`；
- `assistant_delta` 和 `heartbeat` 聚合写入，不逐 token 或逐心跳写 Mongo；
- 只有 `done` 是权威终态，`error`、`cancelled`、`timeout` 是收敛过程事件。

## 4. Skill Router Trace 设计

### 4.1 当前 Router 的准确命名

现状不是一个独立的 Router 类，而是以下隐式链路：

```text
SkillLoader.load_all
    -> SkillRegistry.from_skills
    -> exposed_tools()
    -> LLM tool call
    -> SkillRegistry.get(tool_name)
    -> Skill.dynamic_risk_level
    -> SkillContext.call_mcp_tool
```

因此建议：

- 当前阶段将 `skill_router` 作为观测阶段名，记录 Registry 快照、工具暴露和模型选择结果；
- 后续如果引入规则/检索/分类器 Router，再把 `skill_router.r1` 拆成明确的 `catalog_recall`、`policy_guard` 和 `router_decision` 子 span；
- `SkillLoader` 只叫发现/加载，`SkillRegistry` 只叫注册/查找，避免把二者误称为 Router。

### 4.2 Router 节点输入

```json
{
  "user_input_hash": "sha256:...",
  "user_input_length": 24,
  "conversation_turn_index": 3,
  "history_message_count": 6,
  "memory_block_count": 2,
  "registry_version": "sha256:...",
  "registry_skill_count": 18,
  "exposed_tool_count": 7,
  "context_policy": "default",
  "router_mode": "llm_tool_binding"
}
```

默认不把用户原文重复写进 Router Trace；需要调试时由权限控制的详情接口从 `conversationMessages` 读取。

### 4.3 Router 节点输出

```json
{
  "selected_tools": ["get_weather"],
  "candidate_count": 7,
  "rejected_tools": [
    {"name": "create_crop_cycle", "reason": "write_not_needed"}
  ],
  "risk_levels": {"get_weather": "read"},
  "requires_approval": false,
  "execution_modes": {"get_weather": "serial"},
  "fallback": null,
  "policy_violations": [],
  "decision_source": "llm_tool_call",
  "decision_confidence": null
}
```

如果未来引入 Router 检索，增加：

```json
{
  "recall_path": "rule|bm25|vector|hybrid",
  "candidate_scores": [{"name": "get_weather", "score": 0.92}],
  "selection_reason_codes": ["weather_intent", "read_only"],
  "catalog_version": "...",
  "router_version": "..."
}
```

不记录原始隐藏思维链。只记录可解释的 reason code、候选摘要、策略命中和实际选择。

### 4.4 与 Planner 的关系

`planner.draft` 是 Router 之后的可选逻辑 span，不应把 Router 结果伪装成 Planner 结果：

- 首轮调用 Planner：记录 `source=llm`、版本、步骤数、校验结果和 fallback 原因；
- 后续轮次复用：记录 `source=state_cache` 和缓存版本，不重复计 LLM 调用；
- 规则降级：记录 `source=router_fallback`；
- PlanDraft 是软提示，最终执行以实际 Tool/Skill span 为准。

## 5. Mongo、Redis、MySQL 触发策略

### 5.1 总原则

存储调用是否生成 span，取决于它是否能解释用户可见行为、状态一致性或性能瓶颈，而不是取决于“发生了写操作”。建议采用四级采集：

| 采集级别 | 内容 | 默认策略 |
|---|---|---|
| L0 | root、summary、终态和损耗计数 | 每轮必采 |
| L1 | Router、Context、LLM、Tool、Approval、Commit、Outcome | 每轮必采 |
| L2 | 关键 Redis/Mongo/MySQL/MCP/HTTP 子 span | 关键路径必采，普通读取采样 |
| L3 | 完整输入输出、SQL/query text、响应正文 | 仅调试开关或受控采样 |

### 5.2 Redis

Redis 是 Turn 协调、状态机和 SSE 重放的实时事实源。

必须采集为资源子 span或事件属性：

- admission、队列入列/出列、claim、lease、heartbeat；
- `publish_event` 的 stream 写入、seq 分配和终态抢占；
- approval 状态写入；
- Worker 恢复、重试和重连导致的读取。

不建议默认逐条采集：

- 普通 `HGET` 状态读取；
- 每次心跳的 Redis 命令；
- 与同一业务阶段重复的 key 查询。

资源字段示例：

```json
{
  "span_kind": "client",
  "layer": "resource",
  "node_type": "redis_stream",
  "resource": {
    "system": "redis",
    "operation": "xadd",
    "key_family": "events:<turn_id>"
  },
  "attributes": {
    "seq": 12,
    "terminal": false,
    "queue_wait_ms": 0
  }
}
```

不得记录 Redis URL、密码、完整 key 中的身份信息或用户原文。

### 5.3 MongoDB

Mongo 分成“产品事实”和“诊断投影”两类：

| Mongo 操作 | 是否生成业务 Trace 子 span | 说明 |
|---|---:|---|
| `conversationMessages.insert_one` | 是，L2 | 关联 `message_id`、role、message_kind、persisted |
| 历史消息读取 | 采样/调试 | 在 `context_build` 中记录 count、duration、source，不默认记录每次查询 |
| `traceRecords.insert_many` | 否，独立 writer 指标 | 防止 Trace 自己递归；失败进入 `trace_write_failed` |
| `traceEvents.update_one` | 否，独立 projection 指标 | 记录 queued/persisted/retry/dropped 计数 |
| `traceRequestSummaries.update_one` | 否，独立 projection 指标 | 作为 summary 写入状态，不作为业务成功证据 |

`conversationMessages` 的写入返回 `message_id` 后，挂到 `finalization` 或 `chat_persist` 子 span；Trace 中只保存摘要和 ID，不重复保存完整对话正文。

### 5.4 业务 MySQL

业务 MySQL 是业务事实来源，不是 Trace 的主存储。建议：

- 业务写操作：必须生成 `mysql_write` 或 `business_commit` 子 span，记录 operation、事务结果、业务 code、受影响实体 ID、幂等键 hash；
- 关键业务读：由 `mcp_call` 的资源子 span 记录耗时、结果 count 和错误分类；不默认记录完整 SQL；
- 普通框架查询：只保留聚合指标或采样 span；
- Trace writer 不再默认双写业务 MySQL；旧 archive 的 MySQL dual-write 只作为迁移兼容，不作为 v2 新链路的默认策略。

业务写 span 只有同时满足“业务返回成功”和“数据库提交成功”才能标记 `committed=true`。`operation_committed` SSE 是用户侧事件，不能单独替代数据库证据。

### 5.5 MCP/HTTP

`SkillContext.call_mcp_tool()` 是最合适的统一边界：一次逻辑 `mcp_call` span 包含所有 retry attempt，attempt 可以作为 child span 或 attributes 展开。

必须记录：

- `tool_name`、risk、operation、idempotency key hash；
- attempt、retryable、error category、总耗时；
- Business request ID、业务返回 code；
- 业务写入是否真实提交。

不记录：

- Authorization、Agent token、Cookie；
- 未脱敏完整 SQL；
- 无限制的 HTTP body。

## 6. 四个 Mongo 集合的最终边界

保留四集合，不新增资源专用集合：

### 6.1 `conversationMessages`

保存产品事实：用户输入和助手最终可见答复全文，以及 `conversation_id`、`turn_id`、`trace_id`、`message_kind`。它是对话历史召回的主来源。

不保存：SSE 每个 delta、内部 Router 候选、隐藏思维链、完整数据库调用细节。

### 6.2 `traceRecords`

保存有持续时间的执行 span，包括 Agent 逻辑 span 和关键资源 span。通过 `parent_span_id` 形成树；通过 `layer` 控制 UI 默认层级。

### 6.3 `traceEvents`

保存语义 SSE 事件账本。它与 Redis Stream 共用 `trace_id`、`turn_id`、`event_id`、`seq`；Mongo 是长期诊断投影，不是实时重放源。

### 6.4 `traceRequestSummaries`

保存一轮摘要和证据状态：

```text
span_count, logical_span_count, resource_span_count
queue_wait_ms, lock_wait_ms, llm_duration_ms, tool_duration_ms
approval_wait_ms, mcp_duration_ms, persistence_duration_ms
event_count, replay_count, reconnect_count, event_loss_count
trace_projection_status, trace_event_projection_status
reply_persisted, business_committed, root_error
router_mode, selected_tool_count, planner_source
```

summary 只做索引、列表和快速判断；详细输入输出仍由节点详情按需读取。

## 7. API 命名与查询参数

沿用现有正式接口，不新增一组平行的 debug API：

```text
GET /api/v2/traces
GET /api/v2/traces/{trace_id}
GET /api/v2/traces/{trace_id}/summary
GET /api/v2/traces/{trace_id}/nodes
GET /api/v2/traces/{trace_id}/events
GET /api/v2/traces/{trace_id}/timeline
GET /api/v2/conversations/{conversation_id}
GET /api/v2/turns/{turn_id}
GET /api/v2/turns/{turn_id}/events
```

节点和时间线接口增加以下可选参数：

```text
include_resource_spans=false
include_events=true
include_payload=false
node_type=skill_router|llm_call|...
span_kind=internal|client
after_seq=<int>
limit=<int>
```

默认响应：

- Trace 列表只返回 summary；
- Timeline 默认返回逻辑节点和语义事件，资源 span 折叠；
- 点开模型/Skill 节点时，侧边抽屉读取该 `span_id` 的 `input_summary`、`output_summary` 和 payload 状态；
- `include_payload=true` 只能由受控调试权限使用，并在返回中标记 `redacted`、`truncated`、`source` 和 `evidence_status`；
- 不用 `/debug`、`/dump`、`/raw-trace` 命名公开接口。

## 8. Admin Trace UI 展示原则

页面默认采用两层：

```text
逻辑时间线
  trace_root
  admission / queue_wait
  skill_router
  context_build
  llm_call
    [资源 2 个，耗时 2391ms]
  skill_call / tool_call
    [MCP 1 次，重试 1 次，业务提交成功]
  finalization / turn_outcome

侧边抽屉
  输入摘要 / 实际输入
  输出摘要 / 实际输出
  父子关系与 phase
  attempts / token / 错误
  关联 SSE 事件
  关联消息、业务 operation、resource span
```

必须显示内容缺失原因：

- `not_collected`：采样策略没有采集；
- `truncated`：采集了但被长度限制；
- `redacted`：安全策略脱敏；
- `projection_pending`：Redis 已有但 Mongo 尚未投影；
- `projection_failed`：投影失败；
- `source_unavailable`：对应存储不可用。

不能用 `-` 把“没有采集”“采集失败”和“业务返回为空”混在一起。用户之前看不到输入输出时，优先检查 `input_summary/output_summary`、`include_payload` 和 `evidence_status`，不要只看节点标题。

## 9. 实现分阶段计划

### Phase 1：补齐 span 树和数据契约

- 扩展 `TraceInfo`：当前 span、root span、phase、attempt、采样等级；
- 新增统一 `start_span/end_span` 或异步上下文管理器；
- collector 写入 `span_id`、`parent_span_id`、`span_kind`、`layer`、`attributes`、`sampling`；
- root、LLM、Tool、commit、outcome 先建立父子关系；
- 修正 store/timeline 排序和接口响应，兼容旧平面节点。

验收：一轮正常 Tool 对话至少能还原 `root -> llm -> tool -> llm -> outcome`，每个节点都有唯一 span ID。

### Phase 2：补齐 Agent 逻辑阶段

- `admission/queue_wait`；
- `skill_router`，记录 Registry 快照、暴露工具数、实际选择、风险和 fallback；
- `context_build`，记录历史/记忆/工具 schema 的数量、版本、预算和压缩结果；
- `approval`、`observation`、`planner.draft`；
- summary 增加逻辑节点统计和等待耗时。

验收：调试员可以回答“为什么选这个 Skill、模型实际拿到哪些上下文、是否等待过审批”。

### Phase 3：补齐关键资源调用

- 在 `SkillContext.call_mcp_tool()` 统一记录 MCP 总 span 和 retry；
- 在 `publish_event()` 记录 Redis stream/seq/终态保护的 resource attributes；
- 在 `append_message()` 记录产品消息持久化结果；
- 业务 MCP 或业务服务侧补齐 MySQL write/business commit 关联；
- Trace writer 和事件投影只记录独立健康指标，不递归进入业务 Trace。

验收：能区分 Agent 推理慢、MCP 慢、业务 DB 慢、Redis 排队慢和 Mongo 投影慢。

### Phase 4：UI 和真实链路验收

- Timeline 默认逻辑层，资源层折叠；
- 点击 LLM/Skill/Tool 打开侧边抽屉，显示真实输入、输出、摘要和缺失原因；
- 支持按 `span_id`、`event_id`、`operation_id` 回链；
- 使用 curl 跑正常、Tool、审批、失败、重连、多轮五类 SSE 对话；
- 逐轮核对 Redis Stream、Mongo 四集合、assistant 消息和业务 MySQL 真实结果。

## 10. 验证指标与失败判定

每轮 Trace 至少检查：

```text
trace_id/turn_id/conversation_id 关联一致
root span 存在且只有一个
span_id 唯一，parent_span_id 可解析或明确为空
SSE seq 单调且无未解释缺口
最多一个 terminal done
Redis event_count 与 traceEvents projection 状态可解释
reply_persisted 与 conversationMessages 实际记录一致
business_committed 与业务库提交证据一致
输入/输出缺失带有 not_collected/truncated/redacted 等原因
Trace writer 失败不被误报为业务失败，但必须有投影失败证据
```

建议监控：

- `trace_span_queue_backlog`、`trace_event_queue_backlog`、`trace_dropped_total`；
- `trace_projection_latency_ms`、`trace_projection_failed_total`；
- `trace_payload_truncated_total`、`trace_payload_redacted_total`；
- Router decision latency、selected tool count、write-tool false exposure；
- queue wait、approval wait、LLM/MCP/DB duration；
- `done` 缺失、重复终态、seq gap、消息未持久化。

业务成功判定仍遵循：最终自然语言回复不是证据；必须结合 `operation_committed`、业务 commit span 和业务库结果。

## 11. 方法论依据与项目映射

本设计采用 OpenTelemetry 的基本区分：有持续时间和父子关系的操作使用 Span；没有独立持续时间边界的状态变化使用 Event；稳定的操作属性使用 Attributes。数据库调用适合使用 `CLIENT` 子 span，但敏感 query text 默认不采集。

参考：

- [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)
- [OpenTelemetry Trace Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/general/trace/)
- [OpenTelemetry Events](https://opentelemetry.io/docs/specs/semconv/general/events/)
- [OpenTelemetry Database Spans](https://opentelemetry.io/docs/specs/semconv/db/database-spans/)
- [Langfuse Observability Overview](https://langfuse.com/docs/observability/overview)

映射到本项目：

- `Turn` 是执行生命周期，`trace_id` 是一轮诊断边界；
- Redis Stream 是在线状态和 SSE 重放源；
- `traceEvents` 是异步长期事件投影；
- `traceRecords` 是 Agent 逻辑和关键资源 span；
- `conversationMessages` 是用户可见产品事实；
- `traceRequestSummaries` 是列表和验收指标，不替代原始证据；
- `SkillRegistry` 是能力快照，`skill_router` 是对这次决策过程的可观测命名；
- `SkillContext.call_mcp_tool()`、`turn_store.publish_event()`、`chat_store.append_message()` 是优先埋点边界。

## 12. 本轮决策

本轮不建议直接把所有 Mongo、MySQL、Redis 操作铺成页面节点，也不建议新增第五个 Trace 集合。推荐先实现 span 树和 Router/Context/Queue 逻辑节点，再对关键资源调用做 L2 子 span；页面用逻辑节点做主视图，侧边抽屉按 `span_id` 展开实际输入输出、事件和资源证据。

这样既能解决当前“Trace 内容少、看不到输入输出”的问题，也能保持对话历史、SSE 重放、Agent 执行和业务提交之间的事实边界清楚，后续才有条件做整段对话或单轮对话的可靠召回和链路调试。
