## Why

当前 MySQL schema 已能支撑 MVP，但部分表缺少外键、复合索引和准确类型，长期运行后容易出现跨用户悬挂数据、查询退化和观测数据难以治理的问题。现在后端已经迁移到 MySQL + Alembic，适合通过一次小步 schema hardening 把数据一致性和可运营性补齐。

## What Changes

- 为用户、农场、分类、反馈、Agent 记录等跨表关系补齐外键约束和删除策略。
- 为高频查询路径补充复合索引，包括账务按农场和日期查询、会话消息按时间查询、trace 按请求轮次查询、Agent 历史按农场时间查询。
- 将部分文本型时间和日期字段改为准确类型，例如 `trace_records.start_time/end_time`、`token_daily_stats.date`。
- 将 `meta`、`token_usage`、仿真 JSON 字段等结构化文本逐步迁移为 MySQL `JSON` 类型。
- 将 `cost_records.category` 迁移为 `category_id` 关联 `cost_categories`，并保留分类名称快照以保护历史展示语义。
- 清理主键上的冗余二级索引，减少写入成本和索引维护噪音。
- 保持现有 API 响应兼容，不引入业务接口破坏性变更。

## Capabilities

### New Capabilities

无。该变更强化已有数据库能力，不新增独立业务能力。

### Modified Capabilities

- `database-hardening`: 增加外键完整性、冗余索引清理、JSON/日期字段类型治理、成本分类关联约束要求。
- `mysql-database-engine`: 增加 MySQL 8.x 下复合索引、JSON 类型、在线迁移兼容性的要求。
- `database-migration-tooling`: 增加 Alembic 迁移、数据回填、迁移前后校验和回滚策略要求。

## Impact

- 影响数据库 schema、Alembic migrations、SQLAlchemy ORM models 和相关服务查询。
- 影响账务、分类、会话、反馈、trace、token 统计和仿真结果等表。
- 需要为历史数据补齐外键可引用值，迁移 `cost_records.category` 到 `category_id` 时需做数据回填。
- 不应修改移动端或管理端 API 合同；必要字段转换由后端保持兼容。
