## MODIFIED Requirements

### Requirement: SQLite WAL 模式
系统启动时 SHALL 根据数据库类型自动配置优化参数。SQLite 使用 WAL 模式，MySQL 使用连接池参数。

#### Scenario: SQLite 启动配置（不变）
- **WHEN** FastAPI 应用启动，数据库 URL 以 `sqlite:///` 开头
- **THEN** 自动执行 PRAGMA journal_mode=WAL, synchronous=NORMAL, foreign_keys=ON, busy_timeout=5000

#### Scenario: MySQL 启动配置
- **WHEN** FastAPI 应用启动，数据库 URL 以 `mysql` 开头
- **THEN** 跳过 SQLite PRAGMA，使用 pool_size=10, max_overflow=20, pool_recycle=3600, pool_pre_ping=True

### Requirement: 外键约束生效
所有外键关系 SHALL 在数据库层面强制执行。SQLite 通过 PRAGMA foreign_keys=ON，MySQL InnoDB 默认启用外键约束。

#### Scenario: MySQL 外键约束
- **WHEN** 使用 MySQL InnoDB 引擎
- **THEN** 所有外键约束（CASCADE、SET NULL、RESTRICT）由 InnoDB 自动强制执行

### Requirement: 定时备份
系统 SHALL 根据数据库类型提供对应的备份策略。SQLite 使用文件拷贝，MySQL 使用 mysqldump。

#### Scenario: MySQL 定时备份
- **WHEN** 使用 MySQL 数据库，cron 触发备份脚本
- **THEN** 执行 `mysqldump --single-transaction` 生成 SQL 备份文件，自动清理 7 天前的备份

#### Scenario: SQLite 定时备份（不变）
- **WHEN** 使用 SQLite 数据库，cron 触发备份脚本
- **THEN** 使用 `sqlite3 .backup` 命令生成备份文件，命名含时间戳，自动清理 7 天前的备份
