## ADDED Requirements

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
