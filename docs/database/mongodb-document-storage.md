# MongoDB 文档存储状态

## 第 1 期集合

| MySQL 表 | Mongo 集合 | 默认模式 | 状态 |
| --- | --- | --- | --- |
| `trace_records` | `traceRecords` | `mysql` | 已支持 `mysql`、`dual`、`mongo-read`、`mongo` 后端 |
| `agent_case_drafts` | `caseDrafts` | `mysql` | 已支持 Repository 切换 |
| `agent_repair_packs` | `repairPacks` | `mysql` | 已支持 Repository 切换与去重查询 |
| `agent_review_issue_chains` | `reviewIssueChains` | `mysql` | 已支持 Repository 切换；跨 session 聚合仍保留 MySQL 查询 |
| `agent_data_flywheel_prelabels` | `prelabels` | `mysql` | 已支持 Repository 切换 |

## 第 2 期集合

| MySQL 表 | Mongo 集合 | 默认模式 | 状态 |
| --- | --- | --- | --- |
| `conversation_messages` | `conversationMessages` | `mysql` | 已支持索引、mapper、Repository、回填和校验 |
| `agent_records` | `agentRecords` | `mysql` | 已支持索引、mapper、Repository、回填和校验 |
| `guardrails_logs` | `guardrailsLogs` | `mysql` | 已支持索引、mapper、Repository、回填和校验；继续沿用应用层 30 天清理策略 |

第 2 期已执行回填校验：

| MySQL 表 | Mongo 集合 | MySQL 数量 | Mongo 数量 | 缺失 | 不一致 |
| --- | --- | ---: | ---: | ---: | ---: |
| `guardrails_logs` | `guardrailsLogs` | 0 | 0 | 0 | 0 |
| `agent_records` | `agentRecords` | 221 | 221 | 0 | 0 |
| `conversation_messages` | `conversationMessages` | 308 | 308 | 0 | 0 |

## 第 2 期审计摘要

MySQL 结构与数据量：

- `conversation_messages`：字段包含 `conversation_id`、`role`、`content`、`meta`、`turn_id`、`content_hash`、`meta_json`、`created_at`；通过 `conversation_id` 关联 `conversations` 获取 `farm_id` 和 `session_id`；当前已回填 308 行。
- `agent_records`：字段包含 `farm_id`、`user_id`、`conversation_id`、`cycle_id`、`record_type`、`content`、`meta`、`created_at`；当前已回填 221 行。
- `guardrails_logs`：字段包含 `farm_id`、`trigger_type`、`trigger_detail`、`source_text`、`created_at`；当前无历史行，仍创建集合和索引。

主要读写路径：

- `conversation_messages`：聊天和流式聊天保存消息、历史消息 API、debug export、会话摘要、Data Flywheel turn 证据读取已接入 `ConversationMessageRepository`。`session_sync_service` 仍保留 MySQL 直写，因为它是离线补齐任务，需要原地更新 `turn_id` 和 `meta_json`。
- `agent_records`：聊天记录、每日建议、报告生成、建议历史、报告历史、报告分页、每日缓存读取和 cycle 清理已接入 `AgentRecordRepository`。
- `guardrails_logs`：`/admin/guardrails-logs` 和旧日志清理已接入 `GuardrailsLogRepository`；管理员查询支持可选 `farm_id` 过滤，全局查询仅作为 admin 运维入口。

API 影响面与兼容性：

- `/agent/chat`、`/agent/chat/stream` 不暴露 Mongo `_id`，Mongo 二级写失败不改变主流程成功语义。
- `/agent/conversations/{session_id}/messages`、`/agent/conversations/{session_id}/debug-export`、建议历史、报告历史、报告分页和 `/admin/guardrails-logs` 继续返回 MySQL 稳定 ID 和既有字段。
- Data Flywheel 仍保持 `chat_record_source=mysql_conversation_messages` 兼容标记；本期只改变底层读取入口，不改变来源语义。

测试覆盖：

- Mapper、索引、回填、校验、补偿和反向同步测试：`backend/tests/test_mongo_mappers.py`、`backend/tests/test_mongo_indexes.py`、`backend/tests/test_mongo_migration_tooling.py`。
- Repository 四模式测试：`backend/tests/test_online_document_repositories.py`。
- API 与服务兼容测试：conversation、agent API、debug export、daily advice、report、guardrails、Data Flywheel 和 memory summary 相关测试。

## 通用字段

每个 Mongo 文档保留：

- `mysqlId`：原 MySQL 主键，用于幂等回填、校验和回滚。
- `farmId`：租户隔离字段，业务查询必须携带。
- 业务 ID：如 `requestId`、`draftId`、`packId`、`chainId`、`sampleId`。
- `createdAt`、`updatedAt` 或对象已有时间字段。

## 索引策略

- 所有集合都有 `{ mysqlId: 1 }` 唯一索引。
- 业务 ID 和常用列表查询有显式索引。
- `traceRecords.createdAt` 有 TTL 索引。
- Data Flywheel 四个集合不设置默认 TTL。
- `guardrailsLogs` 暂不设置 Mongo TTL，先与现有应用层 30 天清理保持一致。

## 生命周期阶段

MongoDB 文档存储按对象逐类推进：

1. `mysql`：MySQL 为唯一读写来源。
2. `dual`：MySQL 主写，Mongo 二级写；失败写入 `mongo_compensation_tasks`。
3. `mongo-read`：优先读 Mongo，失败或未命中回退 MySQL。
4. `mongo`：Mongo 主读写；进入前三方回填、校验、补偿重放必须完成。
5. `mysql-cleanup`：Mongo 已稳定作为 source of truth，MySQL 文档型历史数据按清库 runbook 删除或瘦身。

进入 `mysql-cleanup` 后，MySQL 不再作为已清理对象的实时回滚基准；回滚依赖 Mongo 主存储和清理前 JSONL 备份，通过 `rollback-import` 恢复 MySQL 后才能把对应对象切回 `mysql` 或 `dual`。

三期候选清理范围：

- 第 1 期：`trace_records`、`agent_case_drafts`、`agent_repair_packs`、`agent_review_issue_chains`、`agent_data_flywheel_prelabels`。
- 第 2 期：`conversation_messages`、`agent_records`、`guardrails_logs`。

三期禁止清理范围：

- `conversations`
- `agent_turns`
- `feedback_records`
- `token_daily_stats`
- `agent_data_flywheel_labels`

`conversation_messages` 默认只执行大字段瘦身，保留 `id`、`conversation_id`、`role`、`turn_id`、`content_hash` 和 `created_at`。原因是 `agent_turns`、`feedback_records`、`trace_records` 和部分调试/数据飞轮路径仍依赖稳定消息 ID；只有未来所有引用迁出后，才允许单独提出 drop 行或 drop 表方案。

## 暂缓项

- 不迁移 `conversations`。
- 不迁移 `agent_turns.rule_hits`，评估结论见 `docs/database/mongodb-agent-turn-rule-hits-evaluation.md`。
- 三期不 drop MySQL 表结构，只清理或瘦身已迁移对象的数据行。
- 三期前第 1 期和第 2 期保留 MySQL 表和 MySQL 写入作为回滚基准；三期清理后按备份导入回滚。
