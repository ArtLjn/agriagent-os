# farm-manager 链路证据地图

## MySQL 热索引

- `agent_turns`：一轮对话聚合，关键字段 `request_id`、`session_id`、`conversation_id`、`user_message_id`、`assistant_message_id`、`tool_calls_count`、`token_total`、`latency_ms`、`status`、`event_file`、`event_seq_start`、`event_seq_end`。
- `trace_records`：节点级 trace，关键字段 `request_id`、`session_id`、`farm_id`、`round_index`、`node_type`、`node_name`、`input_data`、`output_data`、`duration_ms`、`token_usage`、`status`、`error_message`。
- `conversations` / `conversation_messages`：会话和消息证据，assistant 消息的 `meta_json.trace_request_id` 常用于回链到 trace。

## Mongo 证据库

- `traceRecords`：`trace_records` 的文档形态，字段为 camelCase：`requestId`、`sessionId`、`farmId`、`roundIndex`、`nodeType`、`nodeName`、`input`、`output`、`tokenUsage`、`durationMs`、`status`、`errorMessage`。
- `traceRecords` 真实样本还包含 `_id`、`mysqlId`、`conversationMessageId`、`startTime`、`endTime`、`createdAt`。`mysqlId` 可能是 Mongo-only 生成的 Int64，并不一定能回查 MySQL。
- `conversationMessages`：消息文档，字段 `mysqlId`、`farmId`、`conversationId`、`sessionId`、`role`、`content`、`contentHash`、`turnId`、`meta`、`legacyMetaText`、`createdAt`。
- `conversationMessages.meta.trace_request_id`：assistant 消息到请求 trace 的主回链。
- `conversationMessages.meta.event_file` / `event_seq_range`：assistant 消息到本地 JSONL 事件片段的主回链。
- `turnId` 不是 Mongo 全局唯一键；按单次请求反查同轮消息时必须组合 `turnId + sessionId + farmId`，否则会串到同 farm 其他 session 的同号 turn。

## 本地事件

- 默认目录：`data/agent-events/dt=<date>/farm_id=<id>/session_id=<id>/events.jsonl`。
- 常见事件：`message.user`、`message.assistant`、`tool.call.finished`。
- 如果 `agent_turns.event_file` 存在，优先按 `event_seq_start/event_seq_end` 读取对应事件片段。
- 如果 MySQL `agent_turns` 不可用，使用 Mongo `conversationMessages.meta.event_file` 和 `meta.event_seq_range` 读取事件片段。

## 真实降级模式

- `trace_records` MySQL 表不存在时，Admin trace 代码会走 Mongo `traceRecords`；调试脚本应把 MySQL 状态标为 partial，而不是失败退出。
- `agent_turns` 不存在或未命中时，仍可从 Mongo `traceRecords.sessionId/farmId` 和 `conversationMessages.turnId/meta` 反推链路范围。
- 按短 `request_id` 调试时，Mongo 查询允许 `requestId` 前缀匹配；Admin API 默认是精确匹配。
- 多开发环境会导致同一个项目目录连接到不同 MySQL/Mongo。调试脚本导入 `app.shared.config.settings`，因此会受到 `FARM_MANAGER_ENV`、`APP_ENV` 以及 `DATABASE__URL`、`MONGODB__URI`、`MONGODB__DATABASE` 等环境变量影响。证据未命中时，先确认脚本运行环境与后端服务进程一致。

## 存储原则

MySQL 是主状态和热索引；Mongo 是证据和审计。Mongo 失败不能阻断主问答链路。调试时允许 Mongo 缺失，但必须在报告中说明证据缺口。
