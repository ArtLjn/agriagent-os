# MongoDB 第 1 期迁移 Runbook

## 范围

本次只迁移以下五类高 JSON 密度对象：

- `trace_records` -> `traceRecords`
- `agent_case_drafts` -> `caseDrafts`
- `agent_repair_packs` -> `repairPacks`
- `agent_review_issue_chains` -> `reviewIssueChains`
- `agent_data_flywheel_prelabels` -> `prelabels`

不迁移对话消息、`agent_turns.rule_hits`、`agent_records`、`guardrails_logs`。

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
```

一致性校验：

```bash
python scripts/migrate_mysql_to_mongo.py verify --table trace_records --report reports/mongo-trace-verify.json
```

校验不一致率超过 `storage.mongo_consistency_mismatch_rate_threshold` 时脚本返回非零退出码，禁止继续切到 `mongo-read` 或 `mongo`。

## 补偿重放

双写失败会写入 `mongo_compensation_tasks`。重放服务入口在 `app.infra.mongo_compensation.MongoCompensationReplayService`，通过 MySQL source of truth 重新加载对象并幂等写入 Mongo。

## 回滚

- `dual` 异常：切回 `mysql`，暂停补偿重放，保留 Mongo 数据排查。
- `mongo-read` 异常：切回 `dual` 或 `mysql`，读流量回到 MySQL。
- `mongo` 异常：先运行反向同步预览，人工处理冲突后再切回 MySQL。

```bash
python scripts/migrate_mysql_to_mongo.py reverse-sync --table agent_repair_packs --limit 100
```

## 回滚阈值

- Mongo 写失败率 > `storage.mongo_write_failure_rate_threshold`
- Mongo 读错误率 > `storage.mongo_read_error_rate_threshold`
- 一致性不一致率 > `storage.mongo_consistency_mismatch_rate_threshold`
- 主流程 P99 延迟较基线升高 > 50%

## 多租户要求

Mongo Repository 的业务查询必须接收 `farm_id` 并在实际 filter 中包含 `farmId`。迁移脚本是唯一允许按 `mysqlId` 批处理的入口。
