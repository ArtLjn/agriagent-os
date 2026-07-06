# MongoDB 迁移 Runbook

## 范围

第 1 期迁移以下五类高 JSON 密度对象：

- `trace_records` -> `traceRecords`
- `agent_case_drafts` -> `caseDrafts`
- `agent_repair_packs` -> `repairPacks`
- `agent_review_issue_chains` -> `reviewIssueChains`
- `agent_data_flywheel_prelabels` -> `prelabels`

第 2 期迁移以下三类在线追加对象：

- `conversation_messages` -> `conversationMessages`
- `agent_records` -> `agentRecords`
- `guardrails_logs` -> `guardrailsLogs`

第 2 期不迁移 `agent_turns.rule_hits`，只保留拆分迁移评估；不迁移 `conversations`、`feedback_records`、`token_daily_stats` 和 `agent_data_flywheel_labels`。

## 前置检查

1. 配置 `mongodb.enabled=true`、`mongodb.uri`、`mongodb.database`。
2. 运行 MySQL 迁移：`alembic upgrade head`。
3. 初始化 Mongo 索引：

```bash
python scripts/init_mongo_indexes.py --dry-run
python scripts/init_mongo_indexes.py
```

## 灰度切换

默认所有对象保持 `mysql`：

```yaml
storage:
  trace: "mysql"
  case_drafts: "mysql"
  repair_packs: "mysql"
  review_issue_chains: "mysql"
  prelabels: "mysql"
  conversation_messages: "mysql"
  agent_records: "mysql"
  guardrails_logs: "mysql"
```

逐类切换顺序：

1. `mysql`：只读写 MySQL，不依赖 Mongo。
2. `dual`：MySQL 先写，Mongo 二级写失败只记录补偿任务。
3. `mongo-read`：优先读 Mongo，失败或未命中回退 MySQL。
4. `mongo`：Mongo 主读写。进入前必须通过一致性校验。

## 回填与校验

按表回填：

```bash
python scripts/migrate_mysql_to_mongo.py backfill --table trace_records --batch-size 500
python scripts/migrate_mysql_to_mongo.py backfill --table agent_case_drafts --batch-size 500
python scripts/migrate_mysql_to_mongo.py backfill --table agent_repair_packs --batch-size 500
python scripts/migrate_mysql_to_mongo.py backfill --table agent_review_issue_chains --batch-size 500
python scripts/migrate_mysql_to_mongo.py backfill --table agent_data_flywheel_prelabels --batch-size 500
python scripts/migrate_mysql_to_mongo.py backfill --table guardrails_logs --batch-size 500
python scripts/migrate_mysql_to_mongo.py backfill --table agent_records --batch-size 500
python scripts/migrate_mysql_to_mongo.py backfill --table conversation_messages --batch-size 500
```

一致性校验：

```bash
python scripts/migrate_mysql_to_mongo.py verify --table trace_records --report reports/mongo-trace-verify.json
python scripts/migrate_mysql_to_mongo.py verify --table guardrails_logs --mismatch-threshold 0
python scripts/migrate_mysql_to_mongo.py verify --table agent_records --mismatch-threshold 0
python scripts/migrate_mysql_to_mongo.py verify --table conversation_messages --mismatch-threshold 0
```

校验不一致率超过 `storage.mongo_consistency_mismatch_rate_threshold` 时脚本返回非零退出码，禁止继续切到 `mongo-read` 或 `mongo`。

## 补偿重放

双写失败会写入 `mongo_compensation_tasks`。重放服务入口在 `app.infra.mongo_compensation.MongoCompensationReplayService`，通过 MySQL source of truth 重新加载对象并幂等写入 Mongo。

第 2 期回填校验结果：

| 表 | MySQL 数量 | Mongo 数量 | 缺失 | 不一致 |
| --- | ---: | ---: | ---: | ---: |
| `guardrails_logs` | 0 | 0 | 0 | 0 |
| `agent_records` | 221 | 221 | 0 | 0 |
| `conversation_messages` | 308 | 308 | 0 | 0 |

## 回滚

- `dual` 异常：切回 `mysql`，暂停补偿重放，保留 Mongo 数据排查。
- `mongo-read` 异常：切回 `dual` 或 `mysql`，读流量回到 MySQL。
- `mongo` 异常：先运行反向同步预览，人工处理冲突后再切回 MySQL。

```bash
python scripts/migrate_mysql_to_mongo.py reverse-sync --table agent_repair_packs --limit 100
python scripts/migrate_mysql_to_mongo.py reverse-sync --table conversation_messages --limit 100
```

## 回滚阈值

- Mongo 写失败率 > `storage.mongo_write_failure_rate_threshold`
- Mongo 读错误率 > `storage.mongo_read_error_rate_threshold`
- 一致性不一致率 > `storage.mongo_consistency_mismatch_rate_threshold`
- 主流程 P99 延迟较基线升高 > 50%

## 多租户要求

Mongo Repository 的业务查询必须接收 `farm_id` 并在实际 filter 中包含 `farmId`。迁移脚本是唯一允许按 `mysqlId` 批处理的入口。

## 第 2 期清理策略

- 不删除 MySQL 表，不关闭 MySQL 写入。
- `conversation_messages` 和 `agent_records` 在双写、切读观察期完整保留 MySQL 数据。
- `guardrails_logs` 可继续按既有 30 天应用层清理策略删除过期行；Mongo 侧暂不创建 TTL 索引，避免与应用清理策略叠加造成不可审计差异。
- 灰度顺序为 `guardrails_logs -> agent_records -> conversation_messages`。

## 第 3 期 MySQL 清库

三期只清理已经进入 `mongo` 主模式的文档型 MySQL 数据行，不 drop 表结构。生产执行前先阅读 `docs/database/mysql-document-store-cleanup-runbook.md`。

候选表：

- `trace_records`
- `agent_case_drafts`
- `agent_repair_packs`
- `agent_review_issue_chains`
- `agent_data_flywheel_prelabels`
- `conversation_messages`
- `agent_records`
- `guardrails_logs`

禁止清理：

- `conversations`
- `agent_turns`
- `feedback_records`
- `token_daily_stats`
- `agent_data_flywheel_labels`

计划检查：

```bash
python scripts/cleanup_mysql_document_store.py plan \
  --verify-report-dir reports/mongodb-verify \
  --report-dir var/mongodb-cleanup/reports
```

备份：

```bash
python scripts/cleanup_mysql_document_store.py backup \
  --table guardrails_logs \
  --output-dir var/mongodb-cleanup/backups
```

dry-run：

```bash
python scripts/cleanup_mysql_document_store.py cleanup \
  --table guardrails_logs \
  --strategy delete \
  --backup-file var/mongodb-cleanup/backups/guardrails_logs-YYYYMMDDHHMMSS.jsonl
```

execute 必须带 verify 报告、备份文件和确认 token：

```bash
python scripts/cleanup_mysql_document_store.py cleanup \
  --table guardrails_logs \
  --strategy delete \
  --execute \
  --verify-report reports/mongodb-verify/guardrails_logs.json \
  --backup-file var/mongodb-cleanup/backups/guardrails_logs-YYYYMMDDHHMMSS.jsonl \
  --confirm-token CLEANUP:guardrails_logs:<sha256前12位>
```

清理后校验：

```bash
python scripts/cleanup_mysql_document_store.py post-verify \
  --table guardrails_logs \
  --strategy delete \
  --expected-mongo-count 0
```

回滚导入：

```bash
python scripts/cleanup_mysql_document_store.py rollback-import \
  --table guardrails_logs \
  --backup-file var/mongodb-cleanup/backups/guardrails_logs-YYYYMMDDHHMMSS.jsonl \
  --execute \
  --confirm-token ROLLBACK:guardrails_logs:<sha256前12位>
```
