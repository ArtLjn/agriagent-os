## Context

第 1 期已完成 `trace_records`、`agent_case_drafts`、`agent_repair_packs`、`agent_review_issue_chains`、`agent_data_flywheel_prelabels` 的 MongoDB 文档存储工程，并保留 MySQL 作为回滚基准。第 2 期候选来自 `14_MongoDB迁移方案.md`：`conversation_messages`、`agent_records`、`guardrails_logs` 进入建议迁移范围，`agent_turns.rule_hits` 只做拆分迁移评估。

现状盘点：

- `conversation_messages`: MySQL 字段包含 `conversation_id`、`role`、`content`、`meta`、`turn_id`、`content_hash`、`meta_json`、`created_at`；主要写入在 `conversation_service.save_message()`、`save_messages_batch()` 和 `SessionFlywheelRecorder`，主要读取在历史消息、最近消息注入、debug export、Data Flywheel 样本和测试用例。
- `agent_records`: 字段包含 `farm_id`、`user_id`、`conversation_id`、`cycle_id`、`record_type`、`content`、`meta`、`created_at`；主要写入在聊天、流式回复、每日建议和报告生成，主要读取在建议历史、报告历史、报告分页、每日建议缓存和农场/周期关联清理。
- `guardrails_logs`: 字段包含 `farm_id`、`trigger_type`、`trigger_detail`、`source_text`、`created_at`；主要读取在 `/admin/guardrails-logs`，清理在 `cleanup_old_logs()`，当前写入路径较薄，实施前需要补齐 Repository 入口或确认现有创建点。
- `agent_turns.rule_hits`: ORM 中为 `JSON`，被规则引擎写入，被 Data Flywheel 列表、详情、问题链和 judge worker 读取；同时 `agent_turns` 还承载热字段、外键和多维范围查询，本期不拆。

## Goals / Non-Goals

**Goals:**

- 第 2 期实施 `conversation_messages`、`agent_records`、`guardrails_logs` 三张表的 MongoDB 文档存储。
- 保持 `mysql -> dual -> mongo-read -> mongo` 路线，默认仍为 `mysql`，逐对象灰度。
- 保持所有现有 API 返回结构兼容，不让 App、Admin 或 Data Flywheel 感知存储切换。
- 设计三类集合 schema、索引、mapper、Repository 抽象、回填、校验、补偿和回滚预案。
- 扩展第 1 期的 Mongo client、补偿任务、索引脚本和迁移脚本，不引入新的同步基础设施。
- 保留所有 MySQL 表，MySQL 在第 2 期仍为双写期 source of truth 和回滚基准。
- 对 `agent_turns.rule_hits` 输出评估报告和后续建议，不在本变更中迁移。

**Non-Goals:**

- 不迁移 `conversations`、`feedback_records`、`token_daily_stats`、`agent_data_flywheel_labels`。
- 不删除 MySQL 表，不关闭 MySQL 写入，不做不可逆归档。
- 不修改 `backend/config.yaml` 真实密钥，不提交 MongoDB 连接串或生产凭据。
- 不改变用户侧和 admin 侧 API contract，不新增强制前端改造。
- 不为 `agent_turns` 引入跨库 join 或强一致事务。
- 不引入 CDC、Kafka、ClickHouse 或新的日志平台。

## Decisions

### 1. 第 2 期实施范围

**选择**: 本期实施 `conversation_messages`、`agent_records`、`guardrails_logs`，只评估 `agent_turns.rule_hits`。

**理由**: 三张实施表都是追加型或读多写少对象，包含大文本或文本 JSON，事务需求弱，适合沿用第 1 期 Repository 与双写模式。`agent_turns` 仍有强关联外键、热字段范围查询和 Data Flywheel 多维筛选，拆出 `rule_hits` 会引入跨库一致性与查询组合复杂度。

**替代方案**: 同期拆迁 `agent_turns.rule_hits`。该方案会扩大 Data Flywheel 读路径改造面，并要求 `agent_turns` 与 Mongo rule hit 文档保持强关联，风险不适合第 2 期在线消息迁移窗口。

### 2. 集合 schema

`conversationMessages`:

```javascript
{
  _id: ObjectId("..."),
  mysqlId: 1066,
  farmId: 1,
  conversationId: 88,
  sessionId: "sess_xxx",
  turnId: 136,
  role: "assistant",
  content: "...",
  contentHash: "sha256...",
  meta: { /* 由 meta_json 或 meta 文本解析而来 */ },
  legacyMetaText: null,
  createdAt: ISODate("...")
}
```

关键索引：`{ mysqlId: 1 }` 唯一、`{ farmId: 1, conversationId: 1, createdAt: 1, mysqlId: 1 }`、`{ farmId: 1, sessionId: 1, createdAt: 1, mysqlId: 1 }`、`{ farmId: 1, turnId: 1 }`、`{ contentHash: 1 }`。

`agentRecords`:

```javascript
{
  _id: ObjectId("..."),
  mysqlId: 782,
  farmId: 1,
  userId: "user_xxx",
  conversationId: 88,
  cycleId: 12,
  recordType: "daily",
  content: "...",
  meta: { /* token_usage、结构化报告、缓存指纹等 */ },
  legacyMetaText: null,
  createdAt: ISODate("...")
}
```

关键索引：`{ mysqlId: 1 }` 唯一、`{ farmId: 1, recordType: 1, createdAt: -1 }`、`{ farmId: 1, cycleId: 1, recordType: 1, createdAt: -1 }`、`{ farmId: 1, conversationId: 1, createdAt: -1 }`、`{ userId: 1, createdAt: -1 }`。

`guardrailsLogs`:

```javascript
{
  _id: ObjectId("..."),
  mysqlId: 1,
  farmId: 1,
  triggerType: "input_injection",
  triggerDetail: "检测到潜在注入模式",
  sourceText: "...",
  sourceTextHash: "sha256...",
  createdAt: ISODate("...")
}
```

关键索引：`{ mysqlId: 1 }` 唯一、`{ farmId: 1, createdAt: -1 }`、`{ farmId: 1, triggerType: 1, createdAt: -1 }`、`{ sourceTextHash: 1 }`。Guardrails 日志可沿用现有 30 天清理策略；是否设置 Mongo TTL 由实施任务中与现有清理策略对齐后确定。

### 3. Repository 接入边界

**选择**: 建立三个 Repository Protocol：

- `ConversationMessageRepository`: `save_one`、`save_batch`、`get_recent`、`list_by_session`、`get_by_id`、`list_by_turn_ids`。
- `AgentRecordRepository`: `create`、`delete_daily_cache`、`list_advice_history`、`list_report_history`、`list_report_page`、`find_daily_cache`、`clear_cycle_reference`。
- `GuardrailsLogRepository`: `create`、`list_admin_page`、`cleanup_before`。

服务层先改为依赖 Repository，MySQL 实现保持现有语义；Mongo 实现仅在配置切换时启用；DualWrite 先写 MySQL，再写 Mongo，失败进入补偿队列。

**理由**: 第 2 期涉及在线聊天、历史、报告缓存、admin 查询和清理路径，直接在各函数里插入 Mongo 调用会让切换和回滚不可审计。Repository 能统一 mapper、farmId 过滤、读回退和补偿。

### 4. `conversation_id` 与 `farmId` 的来源

**选择**: Mongo 文档必须存 `farmId`。`conversation_messages` 原表没有 `farm_id`，写入时从 `Conversation` 解析；回填时 join `conversations` 获取 `farm_id` 与 `session_id`。Repository 业务查询必须带 `farm_id`，迁移脚本是唯一允许按 `mysqlId` 批处理的入口。

**理由**: 第 1 期已规定 Mongo Repository 强制租户隔离。第 2 期不能因为原 MySQL 表依赖外键间接隔离而在 Mongo 中丢失 `farmId`。

### 5. 灰度模式

**选择**: 继续使用 `mysql`、`dual`、`mongo-read`、`mongo` 四种模式，并按对象独立配置：

- `conversation_messages`
- `agent_records`
- `guardrails_logs`

`dual`: 写 MySQL 成功即主流程成功，Mongo 写失败记录补偿。
`mongo-read`: 优先 Mongo，失败或未命中回退 MySQL并记录结构化日志。
`mongo`: 仅在回填、补偿清零、校验通过和灰度观察完成后启用。

**理由**: `conversation_messages` 属于在线体验路径，必须保留可快速切回 MySQL 的读写策略。

### 6. 回填、校验和补偿

**选择**: 扩展 `scripts/migrate_mysql_to_mongo.py` 和 `scripts/init_mongo_indexes.py` 的表计划，以 `mysqlId` 幂等 upsert。校验包含 count、缺失 ID、关键字段抽样、JSON 规范化和按 session/report/admin 列表顺序校验。

关键校验：

- `conversation_messages`: `farmId`、`conversationId`、`sessionId`、`role`、`contentHash`、`turnId`、`meta`。
- `agent_records`: `farmId`、`recordType`、`cycleId`、`conversationId`、`content`、`meta`。
- `guardrails_logs`: `farmId`、`triggerType`、`triggerDetail`、`sourceTextHash`、`createdAt`。

补偿任务记录对象类型、`farmId`、`mysqlId`、业务关联字段、错误 code 和脱敏错误上下文。重放从 MySQL 重新加载 source of truth 并幂等写入 Mongo。

### 7. API 兼容

**选择**: API 层不新增字段、不移除字段、不改变排序。`ConversationMessageItem.id` 仍返回 MySQL ID；`ReportHistoryItem.id` 仍返回 MySQL ID；Guardrails admin 列表仍返回与 ORM 可序列化兼容的字段。

**理由**: Mongo 文档 `_id` 只作为内部主键，API 与回滚均以 MySQL ID 为稳定标识。

### 8. `agent_turns.rule_hits` 评估输出

**选择**: 本变更增加评估任务，产出 `docs/database/mongodb-agent-turn-rule-hits-evaluation.md` 或同等文档，包含数据量、字段大小、查询路径、索引收益、迁移收益和推荐结论。

评估点：

- `rule_hits` 平均长度、最大长度和空数组比例。
- 写入路径：`evaluate_turn()` 与 `finish_turn()`、`mark_event_range()` 的调用时序。
- 读取路径：Data Flywheel 样本列表、详情、问题链、judge worker、测试。
- 与 `rule_score`、`risk_score`、`risk_dominant_signal`、`risk_severity` 的一致性。
- 若后续迁移，是否建立 `agentTurnRuleHits` 集合或嵌入 Data Flywheel 样本文档。

## Risks / Trade-offs

- **[在线消息读路径扩大]** 切读失败会影响历史消息和 debug export。→ `mongo-read` 必须回退 MySQL，且按 session 灰度观察 P99 和回退率。
- **[conversation_messages 缺少 farm_id]** 回填或写入时 farm 解析错误会造成租户串读。→ mapper 必须从 `Conversation` 校验 `farmId`，Repository 拒绝缺少 `farm_id` 的业务查询。
- **[AgentRecord 缓存语义变化]** 每日建议缓存依赖最新记录和 meta 指纹。→ Mongo 查询必须保持 `record_type + created_at desc` 排序和 meta JSON 解析兼容。
- **[文本 JSON 解析不稳定]** `meta` 可能是旧文本或非法 JSON。→ mapper 将可解析对象存入 `meta`，不可解析原文放入 `legacyMetaText`，反向 mapper 保持兼容。
- **[Guardrails 敏感内容扩散]** `source_text` 可能含敏感输入。→ 写入前复用现有脱敏/截断策略，并对日志和差异报告脱敏。
- **[补偿队列积压]** 在线路径写量比第 1 期更高。→ 按对象监控二级写失败率、补偿积压和重放耗时，超过阈值切回 `mysql`。
- **[Mongo 主模式回滚复杂]** 进入 `mongo` 后 MySQL 可能落后。→ 第 2 期默认目标是双写和切读验证，进入 `mongo` 前必须有反向同步预览和人工审批。

## Migration Plan

1. 完成第 2 期盘点审计：确认三张表所有直接 SQLAlchemy 读写点、API、测试和未覆盖路径。
2. 扩展配置和索引计划：新增三类 storage backend 默认 `mysql`，新增三集合索引 dry-run。
3. 实现 mapper 与 Repository：先 MySQL Repository 包装现有逻辑，再实现 Mongo 和 DualWrite。
4. 接入服务层：会话消息、AgentRecord、Guardrails 日志先保持 `mysql` 行为一致。
5. 扩展补偿、回填、校验、反向同步：以 `mysqlId` 幂等 upsert。
6. 补齐测试：mapper、Repository 四模式、迁移工具、补偿、API 兼容、Data Flywheel 只读影响。
7. 开发或灰度环境执行索引初始化、回填和一致性校验。
8. 按 `guardrails_logs -> agent_records -> conversation_messages` 顺序进入 `dual`。
9. 补偿清零且一致性校验通过后，按相同顺序进入 `mongo-read`，观察读错误率、回退率和 P99。
10. 进入 `mongo` 前执行反向同步预览并人工审批；第 2 期不删表。

**Rollback**:

- `dual` 异常：配置切回 `mysql`，停止补偿重放，保留 Mongo 数据排查。
- `mongo-read` 异常：配置切回 `dual` 或 `mysql`，所有读取回到 MySQL。
- `mongo` 异常：先运行反向同步预览，人工处理冲突后切回 `mysql`。

**Rollback triggers**:

- Mongo 读错误率 5 分钟窗口 > 1%。
- Mongo 二级写失败率 > 0.1%。
- 补偿任务积压持续增长超过 15 分钟。
- 一致性校验不一致率 > 配置阈值。
- `/agent/chat`、历史消息或报告列表 P99 较基线升高 > 50%。

## Open Questions

- Guardrails 日志是否需要 Mongo TTL 与现有 30 天清理同时存在，还是只保留应用清理。
- `agent_records` 的 `meta` 是否需要为每日建议缓存指纹建立嵌套索引，取决于生产缓存查询量。
- `conversation_messages.content` 是否需要全文检索或仅按 session/turn 拉取；本期默认不建全文索引。
- `agent_turns.rule_hits` 后续更适合作为独立集合，还是随 Data Flywheel 样本物化。
