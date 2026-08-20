---
spec_id: 2026-08-18-agent-trace-observability-and-recall-design
last_updated: 2026-08-18
status: draft
---

# v2 Agent Trace、SSE 观测与链路召回设计

## 0. 目的与范围

本文规定 v2 Agent 一轮对话的 Trace 数据模型、SSE 事件关联字段、Trace HTTP 接口命名，以及开发调试时“整段会话”和“单轮 Turn”的证据召回方式。MongoDB 四集合的字段边界和关联约束见配套文档 [2026-08-18-agent-mongo-collection-and-link-design.md](./2026-08-18-agent-mongo-collection-and-link-design.md)。

本文是目标契约，不代表所有接口已经实现。实现状态以 `../../agent/api/` 和 `../../agent/infra/` 当前代码为准。

范围包括：

- Agent `POST /api/v2/chat` 及 `GET /api/v2/turns/{turn_id}/events` 的 SSE 事件；
- MongoDB `traceRecords`、`traceRequestSummaries` 和目标 `traceEvents`；
- `conversationMessages` 与 Trace、SSE 事件的回链；
- `.codex/skills/trace-chain-debugger/` 的只读调试流程。

不包括：业务库写入审计的完整替代方案、LLM 原始思维链持久化、客户端展示组件实现。

## 1. 当前实现与问题

当前 Trace 收集器主要记录 `llm_call`、`tool_call`、`commit_state` 和 `turn` 节点。SSE 事件主要进入 Redis Stream，Trace 节点和 SSE 事件没有稳定的一对一回链。

MongoDB 采用四集合分层：`conversationMessages` 保存用户可见消息全文，`traceRequestSummaries` 保存一轮汇总，`traceRecords` 保存内部节点，`traceEvents` 保存语义 SSE 事件；消息全文不重复复制到 Trace 节点，SSE 传输连接也不单独建集合。

当前存在以下契约问题：

1. `client_request_id` 在 Chat 创建入口用于幂等，但 Worker 初始化 Trace 时没有传入该 ID；当前 Trace `request_id` 可能是 Worker 内生成的随机 ID。
2. Redis SSE 事件目前主要包含 `seq`、`turn_id`、`type`、`data` 和 `terminal`，缺少稳定 `event_id`、`trace_id`、创建时间和事件发生后的状态。
3. `turn.emit()` 只覆盖部分 Runtime 事件，`queued`、`accepted`、部分终态补发和 SSE 重连信息需要从统一发布入口采集。
4. v2 的 `conversation_id` 是会话召回主键；不能把旧版 `session_id` 或旧版数字 `agent_turns.id` 直接当作 v2 `turn_id`。

## 2. 术语与 ID 规则

| 字段 | 语义 | 生命周期 | 规则 |
|---|---|---|---|
| `trace_id` | 一轮 Turn 的完整诊断链路 | 一轮对话 | 创建 Turn 时生成，重连和 Worker 恢复不变 |
| `turn_id` | 一轮 Agent 执行实例 | 一轮对话 | v2 字符串 ID；审批、取消、事件重放使用它 |
| `conversation_id` | 会话 ID | 多轮对话 | v2 会话召回主键，替代旧版 session 语义 |
| `client_request_id` | 客户端幂等键 | 请求幂等窗口 | 不能作为 Trace 主键 |
| `transport_request_id` | 一次 HTTP/SSE 连接请求 | 单次连接 | SSE 重连时可以变化 |
| `event_id` | 单个事件的稳定 ID | 单个事件 | 重放时保持不变，不因发送次数变化 |
| `seq` | 单个 Turn 内的单调序号 | 单个 Turn | 用于 `after_seq`，不能使用 Redis Stream ID 替代 |
| `span_id` | 一个内部执行节点 | 一个节点 | LLM、Tool、审批、提交等节点使用 |
| `parent_span_id` | 节点父级 | 一个节点 | 用于还原调用树 |

兼容策略：现有 `request_id` 字段保留一个迁移周期，但新接口、新文档和新存储字段以 `trace_id` 为正式名称。`GET /api/v2/traces/{request_id}` 暂时作为 `trace_id` 的兼容别名；不得继续把 `client_request_id`、`transport_request_id` 和 `trace_id` 混称为 request。

## 3. 存储分层

### 3.1 `traceRequestSummaries`：一轮汇总

一条文档对应一个 `trace_id`，用于列表、筛选和快速判断：

```text
trace_id, turn_id, conversation_id, client_request_id
user_id, farm_uid, worker_id, worker_attempt
status, stop_reason, root_error
started_at, ended_at, total_duration_ms
queue_wait_ms, lock_wait_ms, llm_wait_ms, mcp_wait_ms, approval_wait_ms
sse_first_event_ms, sse_last_event_ms
first_seq, last_seq, event_count, reconnect_count, replay_event_count
terminal_event_id, terminal_event_type
business_committed, reply_generated, reply_persisted
node_count, error_count, metrics, schema_version
```

### 3.2 `traceRecords`：执行节点

保留现有集合，补充统一字段：

```text
trace_id, turn_id, conversation_id
span_id, parent_span_id, step_index, phase, attempt
node_type, node_name, status
start_time, end_time, duration_ms
input_summary, output_summary, token_usage
resource, error, created_at, schema_version
```

节点类型固定为：

```text
admission, queue_wait, context_build, llm_call, tool_call,
approval, business_commit, finalization, turn_outcome
```

节点内容要求：

- `llm_call`：`provider`、`model`、`stream_started`、`tool_calls_count`、`token_usage`、`finish_reason`、provider request ID；
- `tool_call`：`tool_call_id`、`tool_name`、脱敏参数、执行模式、并行批次、MCP request ID、重试信息；
- `approval`：`approval_id`、风险级别、请求时间、决议时间、等待耗时、决议和原因；
- `business_commit`：业务 operation ID、业务结果码、影响实体 ID、是否幂等重放、是否真实提交；
- `turn_outcome`：最终状态、`stop_reason`、错误、是否生成答复、是否落 assistant 消息。

### 3.3 `traceEvents`：SSE 语义事件

目标新增集合，一条文档对应一个语义事件：

```json
{
  "_id": "evt_01J...",
  "schema_version": 2,
  "trace_id": "trace_01J...",
  "user_id": "user_01J...",
  "farm_uid": "farm_01J...",
  "turn_id": "turn_01J...",
  "conversation_id": "conv_01J...",
  "transport_request_id": "http_01J...",
  "event_id": "evt_01J...",
  "seq": 12,
  "event_type": "tool_finished",
  "phase": "tool_executing",
  "step_index": 1,
  "attempt": 1,
  "status_before": "running",
  "status_after": "running",
  "terminal": false,
  "occurred_at": "2026-08-18T10:00:00Z",
  "data": {},
  "payload_meta": {"bytes": 512, "redacted": true},
  "created_at": "2026-08-18T10:00:00Z"
}
```

`traceEvents` 和 Redis Stream 使用同一个 `event_id`、`seq` 和事件 envelope。Redis 是短期重放源，Mongo 是长期诊断源。事件写入失败不能阻断主问答链路，但必须暴露 `trace_write_failed` 指标和证据状态。

## 4. SSE 事件契约

### 4.1 统一 envelope

每个 SSE `data` 至少包含：

```text
event_id, trace_id, turn_id, conversation_id, seq
event_type, phase, step_index, attempt
status_before, status_after, terminal, occurred_at
data
```

SSE 的 `event:` 行仍使用事件类型，例如 `event: tool_finished`；`data.event_type` 用于日志、Trace 和重放校验。客户端不得从事件名称推断终态，只有 `terminal=true` 且 `event_type=done` 才是权威终态。

### 4.2 事件持久化策略

完整保存：

```text
queued, accepted, started, meta
action, tool_started, tool_finished, observation
approval_required, approval_result
operation_committed
error, verification_warning
context_compressing, context_compressed
final_answer_start, final_answer
cancelled, timeout, done
```

聚合保存：

- `assistant_delta`、`final_answer_delta`：保存增量数量、字符数、首末时间和内容哈希，不逐 token 写 Mongo；
- `heartbeat`：保存数量、首末时间、最后阶段；超时或异常窗口可以保留原始事件；
- `thought`：不保存完整原始思维内容，只保存长度、哈希和受限预览。

### 4.3 状态机

```text
queued/accepted -> started -> meta -> running
running -> approval_required -> awaiting_approval
awaiting_approval -> approval_result -> running
running -> tool_started -> tool_finished -> observation
running -> operation_committed -> final_answer_start -> final_answer
running -> error/cancelled/timeout -> final_answer
任意活动状态 -> done(completed|failed|rejected|cancelled|timeout)
```

`error`、`cancelled`、`timeout` 可以是收敛过程中的事件，不直接替代 `done`。每个 Turn 必须最多有一个 `done`。

## 5. Trace HTTP 接口命名规范

### 5.1 命名规则

1. 资源名使用复数：`traces`、`nodes`、`events`、`conversations`、`turns`。
2. 路径参数使用正式 ID：`{trace_id}`、`{turn_id}`、`{conversation_id}`。
3. `summary` 表示聚合摘要，`timeline` 表示按时间合并的执行节点和 SSE 事件，`events` 只表示 SSE 语义事件。
4. 不使用 `/debug`、`/dump`、`/raw-trace` 作为公开接口名称；调试能力仍是只读查询。
5. 所有错误响应包含 `code`、`message`，必要时包含 `trace_id`、`turn_id` 和 `evidence_status`。

### 5.2 目标接口

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/v2/traces` | Trace 汇总列表；支持 `conversation_id`、`turn_id`、`status`、时间范围、分页 |
| `GET` | `/api/v2/traces/{trace_id}` | 一轮 Trace 详情 envelope，返回基本信息、summary 链接和节点/事件计数 |
| `GET` | `/api/v2/traces/{trace_id}/summary` | 一轮聚合指标、状态、根错误和业务结果 |
| `GET` | `/api/v2/traces/{trace_id}/nodes` | LLM、Tool、审批、提交等内部节点 |
| `GET` | `/api/v2/traces/{trace_id}/events` | SSE 事件账本；支持 `after_seq`、`limit`、`include_payload` |
| `GET` | `/api/v2/traces/{trace_id}/timeline` | 按时间合并 nodes 和 events，作为开发调试主接口 |
| `GET` | `/api/v2/conversations/{conversation_id}` | 会话消息召回，支持 `before` 分页 |
| `GET` | `/api/v2/turns/{turn_id}` | Turn 当前状态，不等同完整 Trace |
| `GET` | `/api/v2/turns/{turn_id}/events` | 在线 SSE 事件订阅和短期重放，不等同长期 Trace 查询 |

当前实现的 `GET /api/v2/traces/{request_id}` 和 `.../summary` 在迁移期保留，但路径参数语义按 `trace_id` 解释。节点查询建议从详情路径迁移到 `.../{trace_id}/nodes`，避免把 Trace 和节点集合混为一谈。

### 5.3 响应边界

- `traces`：只返回汇总，不默认返回大 payload；
- `summary`：返回指标、状态和根错误，不返回完整消息；
- `nodes`：返回内部执行节点，payload 默认摘要化；
- `events`：返回 SSE 事件顺序和状态，payload 默认脱敏；
- `timeline`：返回调试所需的合并时间线，可用 `include_payload=true` 显式扩大内容；
- `conversations`：返回聊天消息，不承担 Trace 节点查询；
- `turns`：返回运行态和审批态，不作为历史审计的唯一来源。

## 6. 整段会话与单轮召回

### 6.1 整段会话召回

输入：`conversation_id`。

顺序：

1. 分页读取 `GET /api/v2/conversations/{conversation_id}`，得到用户消息、assistant 消息和每条消息的 `turn_id`；
2. 分页读取 `GET /api/v2/traces?conversation_id={conversation_id}`，得到该会话的所有 `trace_id`；
3. 对每个 `trace_id` 读取 `summary` 和 `timeline`；
4. 按 `created_at` 合并消息、Turn、节点和 SSE 事件；
5. 输出每轮的状态、根错误、工具调用、业务提交和最终答复；
6. 对缺失 Trace 的消息标记 `trace_missing`，不能根据 assistant 文本推断执行成功。

会话报告的主键顺序为：

```text
conversation_id -> trace_id -> turn_id -> event_id/seq -> span_id
```

### 6.2 单轮召回

优先级：`trace_id` > `turn_id` > 精确 `request_id` > 短 `request_id` 前缀。

输入 `turn_id` 时：

1. `GET /api/v2/traces?turn_id={turn_id}` 解析唯一 `trace_id`；
2. 读取 `GET /api/v2/traces/{trace_id}/timeline`；
3. 读取对应会话消息，并按 `turn_id` 过滤；
4. 检查 SSE `seq` 是否连续、是否恰好一个 `done`；
5. 沿第一条错误向前追溯父节点、上一步 Tool 结果、上下文和消息证据。

输入 `request_id` 时，旧版允许前缀匹配；v2 新接口默认精确匹配，前缀匹配必须在报告中注明 `resolution=prefix`。

### 6.3 证据状态

每次召回都输出：

```text
trace_summary: ok|missing|error
trace_nodes: ok|missing|error
trace_events: ok|missing|not_available|error
conversation_messages: ok|missing|error
runtime_turn: ok|missing|not_available
```

Mongo 不可用不能被写成“没有 Trace”；应写为 `trace_nodes=error(code=mongo_unavailable)`。消息存在但 Trace 缺失时，结论只能是“有消息证据，缺少执行证据”。

## 7. 调试报告格式

开发 Skill 的 Markdown 输出固定为：

1. `目标`：输入参数和环境；
2. `解析范围`：conversation、trace、turn、event 的实际解析结果；
3. `证据状态`：各存储来源状态；
4. `会话/Turn 概览`：消息、状态和最终结果；
5. `SSE 时间线`：`seq`、事件类型、状态迁移和重放标记；
6. `Trace 时间线`：节点、耗时、Token、Tool 和错误；
7. `业务结果`：是否真实提交、是否幂等重放、是否生成并持久化答复；
8. `错误节点`：第一个根错误和后续派生错误；
9. `证据缺口`：没有查询到的存储或关联；
10. `排查建议`：按证据给出下一步，不根据自然语言答复补全事实。

## 8. 采集和脱敏规则

- 不写入 Authorization、Service Token、Delegation Token、密码、连接串和完整 Cookie；
- 用户输入、Tool 参数和 Tool 返回值默认摘要化并按字段脱敏；
- 原始聊天全文归 `conversationMessages`，不重复复制到每一个 Trace 节点；
- 原始异常堆栈归应用日志，Trace 保存 `code`、`message`、`category`、`phase`、`retryable`、`attempt`；
- `trace_id`、`turn_id`、`event_id`、`seq` 必须可用于跨集合回链；
- Trace 写入失败不能阻断问答，但必须在汇总中体现 `evidence_status` 和丢失计数。

## 9. 索引与保留

推荐索引：

```text
traceRequestSummaries: user_id + farm_uid + conversation_id + ended_at
traceRequestSummaries: turn_id
traceRecords: trace_id + step_index + start_time
traceEvents: trace_id + seq (unique)
traceEvents: turn_id + occurred_at
conversationMessages: conversationId + createdAt
conversationMessages: conversationId + turnId + createdAt
```

Redis 事件按短期重放策略保留；Mongo `traceEvents` 按诊断保留周期保存。增量事件和心跳不应无限制地增加 Mongo 文档数量。

## 10. 落地顺序与验收

1. 统一 `trace_id`、`event_id`、`seq` 和 `request_id` 命名；
2. 在 `publish_event()` 生成完整事件 envelope；
3. 增加 `traceEvents` 投影和唯一索引；
4. 增强 `traceRecords` 和 `traceRequestSummaries` 字段；
5. 实现 `nodes/events/timeline` 接口，并保留旧接口兼容别名；
6. 扩展 `trace-chain-debugger` 的整段会话和单轮召回；
7. 用真实 Redis、Agent SSE、Mongo 和 MCP 验证正常、审批、失败、取消、超时、断线重连和 after_seq 重放。

验收必须证明：事件序号单调、事件 ID 不重复、每轮只有一个 `done`、Trace 节点和 SSE 事件可回链、业务提交和最终答复失败可以区分、Mongo 缺失时报告不会伪造成功。
