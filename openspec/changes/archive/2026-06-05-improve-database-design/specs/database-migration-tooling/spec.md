## ADDED Requirements

### Requirement: Schema hardening 迁移校验
系统 SHALL 为数据库设计强化迁移提供迁移前和迁移后的校验命令。

#### Scenario: 迁移前校验
- **WHEN** 开发者运行 schema hardening 迁移前检查
- **THEN** 系统必须报告悬挂外键、非法 JSON、无法匹配分类和重复唯一键风险

#### Scenario: 迁移后校验
- **WHEN** Alembic 迁移执行完成
- **THEN** 系统必须验证关键外键存在、复合索引存在、核心表行数未减少

### Requirement: 账务分类回填迁移
系统 SHALL 在迁移 `cost_records.category_id` 前提供可重复执行的数据回填流程。

#### Scenario: 成功匹配分类
- **WHEN** `cost_records.category` 能按农场、分类名和记录类型匹配 `cost_categories`
- **THEN** 回填流程必须写入对应 `category_id` 和分类名称快照

#### Scenario: 分类缺失
- **WHEN** `cost_records.category` 无法匹配现有分类
- **THEN** 回填流程必须记录该记录并按配置决定自动创建分类或中止迁移

### Requirement: 可回滚迁移
数据库设计强化 migration SHALL 提供 downgrade 路径，并在删除旧字段前保留至少一个版本窗口。

#### Scenario: 回滚到迁移前 schema
- **WHEN** 开发者执行 Alembic downgrade
- **THEN** schema 必须恢复到迁移前可运行状态，且旧分类字符串字段仍可用于兼容读取

#### Scenario: 保留旧字段窗口
- **WHEN** `category_id` 和分类快照已完成回填
- **THEN** 旧 `category` 字符串字段不得在同一个迁移步骤中立即删除
