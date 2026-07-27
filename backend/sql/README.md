# Farm Manager 数据库结构快照

本目录只维护可直接用于 MySQL 的 DDL。MongoDB 是文档集合，不放进 SQL 文件里创建。

## MySQL DDL

- 文件：`farm_manager.sql`
- 来源：生产 `farm_manager` 库的 schema-only 导出
- 最近核对日期：2026-07-27
- 范围：当前线上 MySQL 真实存在的表，不包含已迁出到 MongoDB 的历史文档表

当前 MySQL 运行时表：

```text
agent_data_flywheel_labels
agent_pending_plan_steps
agent_pending_plans
agent_task_states
agent_turns
conversations
cost_categories
cost_records
crop_cycles
crop_templates
cycle_stages
farm_logs
farms
feedback_records
growth_stages
idempotency_keys
labor_entries
memory_records
mongo_compensation_tasks
operation_work_order_units
operation_work_orders
planting_units
simulation_results
simulation_runs
token_daily_stats
user_settings
users
workers
```

迁移元数据表：

```text
alembic_version
```

## MongoDB 集合

生产配置中以下文档对象已切到 MongoDB，不能再混入 MySQL DDL：

| 业务对象 | Mongo 集合 | 原 MySQL 表 |
| --- | --- | --- |
| trace | `traceRecords` | `trace_records` |
| trace request summary | `traceRequests` | 无 |
| case drafts | `caseDrafts` | `agent_case_drafts` |
| repair packs | `repairPacks` | `agent_repair_packs` |
| review issue chains | `reviewIssueChains` | `agent_review_issue_chains` |
| data flywheel prelabels | `prelabels` | `agent_data_flywheel_prelabels` |
| conversation messages | `conversationMessages` | `conversation_messages` |
| agent records | `agentRecords` | `agent_records` |
| guardrails logs | `guardrailsLogs` | `guardrails_logs` |

Mongo 索引计划由 `backend/scripts/init_mongo_indexes.py` 维护；SQL DDL 更新时不要手写 Mongo 集合结构。
