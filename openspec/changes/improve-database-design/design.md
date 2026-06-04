## Context

当前数据库已迁移到 MySQL 8.x，并通过 Alembic 管理 schema，但 `backend/sql/farm_manager.sql` 暴露出几个典型 MVP 阶段遗留问题：部分跨表关系没有数据库外键、账务分类仍以字符串存储、观测和仿真 JSON 字段以 `text` 保存、部分时间字段使用字符串类型、查询索引主要是单列索引且存在主键冗余索引。

这些问题不会立即阻断功能，但会在多用户、Agent trace 增长、账务数据增多后放大为数据一致性、查询性能和迁移治理风险。本设计以“小步 Alembic 迁移 + 保持 API 兼容”为约束，优先强化数据库结构，而不是重写业务模块。

## Goals / Non-Goals

**Goals:**

- 补齐关键外键和删除策略，降低悬挂数据风险。
- 为核心查询路径补充复合索引，并移除主键冗余二级索引。
- 将结构化文本字段逐步迁移到 MySQL `JSON` 类型。
- 将日期、时间、布尔字段改为更准确的 MySQL 类型。
- 将账务记录的分类从自由字符串升级为 `cost_categories` 外键，同时保留历史展示快照。
- 提供迁移前后校验，保证历史数据可回填、可回滚。

**Non-Goals:**

- 不改变移动端或 Admin Web API 合同。
- 不引入 Redis、分库分表或新的数据库产品。
- 不实现多农场成员协作模型；`farm_members` 属于后续独立变更。
- 不实现长期记忆表；只为现有 conversation、agent_records、trace 等表做治理。

## Decisions

### 分阶段 Alembic 迁移

采用多步 Alembic migration，而不是一次性大迁移。

- 第一步增加可空新列、复合索引和外键前置清洗校验。
- 第二步回填 `cost_records.category_id` 和分类名称快照。
- 第三步收紧约束、转换 JSON/日期类型、删除冗余索引。

替代方案是直接在单个 migration 中修改所有表。该方案实现快，但一旦历史数据存在异常会导致整次迁移失败，回滚成本高。

### 成本分类保留快照

`cost_records` 新增 `category_id` 指向 `cost_categories(id)`，同时保留 `category_name_snapshot`。

这样分类改名或删除后，历史账务仍能展示当时的分类名称。直接只保留 FK 会导致历史记录随分类改名漂移；继续只存字符串则无法保证分类一致性。

### JSON 类型按字段分批转换

优先转换 `meta`、`token_usage`、仿真 JSON 字段等明确存 JSON 的列。迁移脚本必须先校验现有值是否合法 JSON；非法值保留为字符串包裹或写入迁移报告，不得静默丢弃。

替代方案是继续使用 `text`。这能减少 migration 风险，但后续无法使用 JSON 校验和查询能力，也不利于 trace/评测分析。

### 索引围绕真实查询路径设计

新增索引优先覆盖当前服务层和管理端的高频访问：

- `cost_records(farm_id, record_date, deleted_at)`
- `cost_records(farm_id, record_type, record_date)`
- `crop_cycles(farm_id, status, start_date)`
- `farm_logs(farm_id, operation_date)`
- `conversation_messages(conversation_id, created_at)`
- `trace_records(request_id, round_index, id)`
- `agent_records(farm_id, created_at)`

避免为所有列盲目建索引，防止写入成本膨胀。

### 外键删除策略按业务语义区分

- 用户删除不作为常规业务操作；用户禁用通过 `users.status` 完成。
- `farms.user_id`、`user_settings.user_id`、`feedback_records.user_id` 指向 `users(id)`。
- 农场业务数据默认限制硬删除，避免误删农场导致账务、周期、trace 丢失。
- 会话消息跟随会话删除；反馈对消息使用 `ON DELETE SET NULL` 保持反馈记录。

## Risks / Trade-offs

- 历史数据不满足新外键 → 迁移前增加检查脚本，输出不可迁移记录，先修复或归档后再加约束。
- `cost_records.category` 无法匹配现有分类 → 按 `farm_id + name + type` 匹配，未命中时创建非默认分类或写入人工处理清单。
- JSON 文本存在非法内容 → 迁移脚本先扫描，能解析的转 JSON，不能解析的写报告并保留原字段，避免数据丢失。
- 复合索引增加写入成本 → 只保留高频查询索引，删除主键冗余索引抵消部分成本。
- 类型转换锁表 → 生产迁移前在备份库演练，必要时拆分 migration 并安排低峰窗口。

## Migration Plan

1. 添加迁移前检查脚本，校验悬挂外键、非法 JSON、无法匹配的账务分类和重复数据。
2. 生成 Alembic migration：新增 `category_id`、`category_name_snapshot`、必要 JSON 临时列和复合索引。
3. 回填账务分类：按 farm、分类名和收支类型匹配 `cost_categories`，未命中项记录处理报告。
4. 补齐外键：用户、农场、分类、反馈、Agent 记录和设置表关系。
5. 转换字段类型：日期、时间、JSON、布尔字段按校验结果逐步转换。
6. 删除主键冗余二级索引。
7. 运行迁移后校验：行数、关键外键、核心查询、Agent trace 和账务 API 冒烟测试。
8. 回滚策略：保留迁移前 mysqldump；每步 migration 提供 downgrade，涉及数据回填的步骤保留旧字段到至少一个版本窗口后再删除。

## Open Questions

- `cost_records.category` 是否需要长期保留为兼容字段，还是在一个版本窗口后删除。
- 是否允许迁移时自动创建缺失分类，还是要求人工确认后再迁移。
- `farms.user_id` 是否继续保持一人一农场唯一约束，还是为后续 `farm_members` 提前解除唯一约束。
