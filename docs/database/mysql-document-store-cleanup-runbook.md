# MySQL 文档存储清库 Runbook

## 目标

MongoDB 文档存储三期让 MySQL 从文档归档库退回到关系元数据和回滚控制面。清库只处理已迁移对象的数据行或大字段，不执行 `DROP TABLE`。

## 候选与禁止范围

候选表：

- `trace_records`
- `agent_case_drafts`
- `agent_repair_packs`
- `agent_review_issue_chains`
- `agent_data_flywheel_prelabels`
- `conversation_messages`
- `agent_records`
- `guardrails_logs`

禁止表：

- `conversations`
- `agent_turns`
- `feedback_records`
- `token_daily_stats`
- `agent_data_flywheel_labels`

`conversation_messages` 默认使用 `slim` 策略：保留 `id`、`conversation_id`、`role`、`turn_id`、`content_hash`、`created_at` 等稳定引用字段，清空 `content`、`meta`、`meta_json`。它仍被 `agent_turns`、`feedback_records`、`trace_records`、debug export 和 Data Flywheel 逻辑引用，三期不得直接删除行。

## 前置条件

每张候选表执行前必须满足：

1. 对应 `storage.*` 已切到 `mongo`。
2. 最近一次 `migrate_mysql_to_mongo.py verify` 通过，报告里 `ok=true`。
3. `mongo_compensation_tasks` 中对应对象无 `pending` 或 `failed` 积压。
4. 已生成 MySQL JSONL 备份和 SHA256 元数据。
5. 清库执行窗口已确认，业务低峰执行。
6. `backend/config.yaml` 真实密钥不入库；备份和清理报告位于 `backend/var/mongodb-cleanup/` 或外部受控目录。

## 推荐顺序

1. `guardrails_logs`
2. `trace_records`
3. `agent_case_drafts`
4. `agent_repair_packs`
5. `agent_review_issue_chains`
6. `agent_data_flywheel_prelabels`
7. `agent_records`
8. `conversation_messages`，只执行 `slim`

每张表单独执行 plan、backup、dry-run、execute、post-verify，不要把多表 execute 合并成一个批次。

## 执行命令

生成计划：

```bash
python scripts/cleanup_mysql_document_store.py plan \
  --verify-report-dir reports/mongodb-verify \
  --report-dir var/mongodb-cleanup/reports
```

生成备份：

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
  --backup-file var/mongodb-cleanup/backups/guardrails_logs-YYYYMMDDHHMMSS.jsonl \
  --batch-size 500
```

真实执行：

```bash
python scripts/cleanup_mysql_document_store.py cleanup \
  --table guardrails_logs \
  --strategy delete \
  --execute \
  --verify-report reports/mongodb-verify/guardrails_logs.json \
  --backup-file var/mongodb-cleanup/backups/guardrails_logs-YYYYMMDDHHMMSS.jsonl \
  --confirm-token CLEANUP:guardrails_logs:<sha256前12位> \
  --batch-size 500 \
  --sleep-ms 100
```

`conversation_messages` 使用：

```bash
python scripts/cleanup_mysql_document_store.py cleanup \
  --table conversation_messages \
  --strategy slim \
  --execute \
  --verify-report reports/mongodb-verify/conversation_messages.json \
  --backup-file var/mongodb-cleanup/backups/conversation_messages-YYYYMMDDHHMMSS.jsonl \
  --confirm-token CLEANUP:conversation_messages:<sha256前12位>
```

后置校验：

```bash
python scripts/cleanup_mysql_document_store.py post-verify \
  --table guardrails_logs \
  --strategy delete \
  --expected-mongo-count 0
```

## 回滚

清理后不能直接把已清理对象切回 `mysql`。必须先从备份恢复：

```bash
python scripts/cleanup_mysql_document_store.py rollback-import \
  --table guardrails_logs \
  --backup-file var/mongodb-cleanup/backups/guardrails_logs-YYYYMMDDHHMMSS.jsonl \
  --execute \
  --confirm-token ROLLBACK:guardrails_logs:<sha256前12位>
```

回滚后执行：

1. 重新运行 `migrate_mysql_to_mongo.py verify`。
2. 按需要把对应 `storage.*` 切回 `mysql` 或 `dual`。
3. 做 API 冒烟测试。
4. 保留清理报告、备份元数据和回滚报告。

## 生产 Checklist

- [ ] 对象 storage backend 为 `mongo`。
- [ ] Mongo verify 报告通过。
- [ ] 补偿队列无 pending/failed。
- [ ] 备份文件和 `.metadata.json` 已生成，SHA256 已登记。
- [ ] dry-run 输出符合预期。
- [ ] execute token 已由备份 SHA256 生成。
- [ ] 业务低峰窗口已确认。
- [ ] 清理后 post-verify 和 API 冒烟测试通过。
- [ ] 备份保留周期和转储位置已登记。
