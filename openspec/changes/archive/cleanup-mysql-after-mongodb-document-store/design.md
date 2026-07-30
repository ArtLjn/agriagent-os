## Context

第 1 期 MongoDB 文档存储已覆盖 `trace_records`、`agent_case_drafts`、`agent_repair_packs`、`agent_review_issue_chains`、`agent_data_flywheel_prelabels`。第 2 期已覆盖 `conversation_messages`、`agent_records`、`guardrails_logs`，并完成 Mongo 索引、回填、校验、Repository 四模式和生产候选回填验证。

目前 MySQL 仍承担两类职责：

- 关系型业务数据、热路径索引、外键、稳定 API ID 和未迁移字段。
- 已迁移文档对象的回滚基准。

三期目标是让 MySQL 保持干净，但这不能等同于直接删表。`conversations`、`agent_turns`、`feedback_records`、`token_daily_stats`、`agent_data_flywheel_labels` 仍是关系或评估热路径；`agent_turns.rule_hits` 明确不迁移。对于已迁移对象，只有在 Mongo 主模式稳定后，才允许清理 MySQL 数据行。

## Goals / Non-Goals

**Goals:**

- 为第 1 期和第 2 期已迁移文档表建立安全清库机制。
- 清理 MySQL 中已由 Mongo 主存储承接的文档型历史行，降低备份体积和表扫描噪音。
- 清理脚本默认 dry-run，实际执行需要备份、校验、人工确认和显式 `--execute`。
- 清理前检查 storage backend 必须为 `mongo`，Mongo 校验必须通过，补偿队列必须清零。
- 保留表结构、Alembic 迁移历史、必要外键兼容和最小关系骨架。
- 产出可审计报告和回滚导入入口。

**Non-Goals:**

- 不直接 drop MySQL 表。
- 不清理 `conversations`。
- 不清理 `agent_turns` 或 `agent_turns.rule_hits`。
- 不清理 `feedback_records`、`token_daily_stats`、`agent_data_flywheel_labels`。
- 不修改 `backend/config.yaml` 中真实密钥。
- 不绕过备份、校验和人工确认执行生产删除。
- 不在本变更中引入 CDC、Kafka 或新的长期双写平台。

## Decisions

### 1. 清理单位是“表数据行”，不是表结构

**选择**: 三期默认执行 `DELETE`/分批删除数据行，保留 MySQL 表结构。`DROP TABLE` 只允许未来单独 OpenSpec 且确认所有外键、API ID、迁移脚本和审计工具均不再依赖表结构。

**理由**: 当前代码、测试和 Alembic 仍需要这些表存在；直接 drop 会破坏回滚、补偿和外键引用。

**替代方案**: 直接 drop 已迁移表。风险过高，且难以快速恢复。

### 2. 候选清理范围

**可清理候选**:

- 第 1 期：`trace_records`、`agent_case_drafts`、`agent_repair_packs`、`agent_review_issue_chains`、`agent_data_flywheel_prelabels`
- 第 2 期：`conversation_messages`、`agent_records`、`guardrails_logs`

**禁止清理**:

- `conversations`
- `agent_turns`
- `feedback_records`
- `token_daily_stats`
- `agent_data_flywheel_labels`
- 任何未进入 Mongo 主模式的业务表

**理由**: 候选表已有 Mongo mapper、索引、校验和 Repository 支撑；禁止清理表仍承担关系查询、评估、热路径或未迁移字段职责。

### 3. 清理前置条件

每张候选表必须满足：

1. storage backend 为 `mongo`，不是 `mysql`、`dual` 或 `mongo-read`。
2. 最近一次 `verify` 通过，MySQL 与 Mongo count/关键字段一致。
3. `reverse-sync` 预览无冲突或冲突已人工处理。
4. `mongo_compensation_tasks` 对应对象无 pending/failed 积压。
5. 已生成 MySQL 备份文件，并记录 SHA256。
6. 清理报告写入 `reports/mongodb-cleanup/` 或指定目录。

### 4. 清理脚本模式

扩展 `scripts/migrate_mysql_to_mongo.py` 或新增 `scripts/cleanup_mysql_document_store.py`：

- `plan`: 输出候选表、当前行数、Mongo 文档数、storage backend、是否满足清理条件。
- `backup`: 导出目标表数据为 JSONL 或 SQL dump，并生成 SHA256。
- `cleanup --dry-run`: 输出将删除的行数和分批计划，不删除数据。
- `cleanup --execute`: 需要 `--backup-file`、`--confirm-token`、`--table`，执行分批删除。
- `post-verify`: 清理后验证 MySQL 行数为 0 或符合保留策略，Mongo 文档仍完整。
- `rollback-import`: 从备份恢复指定表数据，仅用于紧急回滚。

### 5. 对 `conversation_messages` 的额外约束

`conversation_messages` 与 `agent_turns.user_message_id`、`agent_turns.assistant_message_id`、`feedback_records.message_id`、`trace_records.message_id` 存在外键或逻辑关联。清理前必须完成引用策略：

- 若仍有 MySQL 外键阻止删除，则不得执行清理。
- 若采用保留骨架策略，必须保留 `id`、`conversation_id`、`role`、`created_at` 和必要引用字段，清空或归档 `content`、`meta`、`meta_json` 等大字段。
- 若采用全量删除策略，必须先设计并验证所有引用改为 Mongo `mysqlId` 或解除外键。

三期默认优先采用“瘦身”而非删除 `conversation_messages` 行，除非实现阶段证明外键和 API 引用已经完全迁出。

### 6. 回滚策略

清理后的回滚不再依赖 MySQL 原表实时数据，而依赖：

- Mongo 主存储。
- 清理前 MySQL 备份。
- `rollback-import` 工具。

如果清理后发现 Mongo 数据缺失或 API 异常，应先停止写入、恢复备份到 MySQL、切 storage backend 回 `mysql` 或 `dual`，再进行差异修复。

## Risks / Trade-offs

- **[误删回滚基准]** → 所有执行默认 dry-run，`--execute` 必须带备份文件和确认 token。
- **[外键约束导致删除失败]** → 清理前运行引用检查；`conversation_messages` 默认采用瘦身策略。
- **[Mongo 数据不完整]** → 清理前强制 verify 和 reverse-sync 预览；清理后再 post-verify。
- **[线上仍有 MySQL 读路径]** → plan 阶段扫描配置和代码保留路径，storage 未到 `mongo` 禁止执行。
- **[备份泄露敏感内容]** → 备份目录不得入 Git；报告中只记录路径、数量和 SHA256，不打印大文本内容。
- **[清理锁表影响业务]** → 分批删除，限制 batch size 和 sleep interval，优先低峰执行。

## Migration Plan

1. 盘点当前候选表行数、Mongo 文档数、storage backend 和外键引用。
2. 实现 plan/backup/cleanup/post-verify/rollback-import 工具和测试。
3. 更新 runbook，明确候选范围、禁止范围和执行命令。
4. 在开发库执行 dry-run 和备份恢复演练。
5. 在生产只读阶段运行 plan，确认无 blocked 项。
6. 按 `guardrails_logs -> trace_records -> Data Flywheel 文档表 -> agent_records -> conversation_messages` 顺序逐表清理。
7. 每张表清理后立即运行 post-verify 和 API 冒烟测试。
8. 观察期内保留备份；观察期结束后按备份保留策略转移到对象存储。

**Rollback**:

- 停止清理任务。
- 从备份执行 `rollback-import`。
- 将对应 storage backend 切回 `mysql` 或 `dual`。
- 运行 verify 和 API 冒烟测试。

## Open Questions

- `conversation_messages` 是否先做大字段瘦身，还是在外键迁出后全量删除行。
- 生产备份最终落地位置是本机加密目录、对象存储还是数据库快照。
- 清理观察期保留 7 天、14 天还是 30 天。
- 是否为 `guardrailsLogs` 增加 Mongo TTL，替代 MySQL 30 天清理。
