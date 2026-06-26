# MongoDB 文档存储状态

## 第 1 期集合

| MySQL 表 | Mongo 集合 | 默认模式 | 状态 |
| --- | --- | --- | --- |
| `trace_records` | `traceRecords` | `mysql` | 已支持 `mysql`、`dual`、`mongo-read`、`mongo` 后端 |
| `agent_case_drafts` | `caseDrafts` | `mysql` | 已支持 Repository 切换 |
| `agent_repair_packs` | `repairPacks` | `mysql` | 已支持 Repository 切换与去重查询 |
| `agent_review_issue_chains` | `reviewIssueChains` | `mysql` | 已支持 Repository 切换；跨 session 聚合仍保留 MySQL 查询 |
| `agent_data_flywheel_prelabels` | `prelabels` | `mysql` | 已支持 Repository 切换 |

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

## 暂缓项

- 不迁移 `conversations`、`conversation_messages`。
- 不迁移 `agent_turns.rule_hits`。
- 不迁移 `agent_records`、`guardrails_logs`。
- 第 1 期保留 MySQL 表和 MySQL 写入作为回滚基准。
