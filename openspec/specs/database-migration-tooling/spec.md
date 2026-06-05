## Purpose

定义 database-migration-tooling 能力的行为要求。
## Requirements
### Requirement: SQLite 到 MySQL 数据迁移脚本
系统 SHALL 提供独立的 Python 迁移脚本，将现有 SQLite 数据完整迁移到 MySQL。

#### Scenario: 全量数据迁移
- **WHEN** 运行 `python scripts/migrate_sqlite_to_mysql.py --source farm_manager.db --target mysql+pymysql://...`
- **THEN** 脚本按外键依赖顺序逐表迁移所有数据，日志输出每张表的迁移记录数

#### Scenario: 类型自动转换
- **WHEN** SQLite 的布尔值（0/1）迁移到 MySQL
- **THEN** 自动映射为 MySQL 的 TINYINT(1)

#### Scenario: 迁移失败回滚
- **WHEN** 迁移过程中某张表写入失败
- **THEN** 脚本回滚当前表操作并报告错误，已完成的表不受影响

### Requirement: 迁移验证
迁移完成后 SHALL 提供数据校验，确认 SQLite 和 MySQL 数据一致。

#### Scenario: 行数校验
- **WHEN** 迁移完成后自动执行校验
- **THEN** 逐表对比 SQLite 和 MySQL 的行数，输出差异报告

#### Scenario: 抽样内容校验
- **WHEN** 迁移完成后
- **THEN** 每张表随机抽取 5 条记录对比字段值，验证数据完整性

### Requirement: 迁移前备份
迁移脚本 SHALL 在开始前自动备份 SQLite 数据库文件。

#### Scenario: 自动备份
- **WHEN** 运行迁移脚本
- **THEN** 脚本先复制 SQLite 文件为 `.bak` 后缀，再执行迁移

#### Scenario: 备份存在提示
- **WHEN** 迁移脚本发现目标 MySQL 数据库已有数据
- **THEN** 提示用户确认是否覆盖，未确认则中止

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

