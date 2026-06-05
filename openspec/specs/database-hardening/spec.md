## Purpose

定义 database-hardening 能力的行为要求。
## Requirements
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

### Requirement: 关键关系外键完整性
系统 SHALL 为用户、农场、设置、反馈、账务分类和 Agent 记录等关键跨表关系配置数据库外键约束，并按业务语义配置删除策略。

#### Scenario: 阻止悬挂农场数据
- **WHEN** 新增或更新依赖 `farm_id` 的业务记录
- **THEN** 数据库必须拒绝引用不存在的 `farms.id`

#### Scenario: 保留反馈记录
- **WHEN** 被评价的会话消息被删除
- **THEN** `feedback_records.conversation_message_id` 必须被置空且反馈记录保留

### Requirement: 账务分类引用完整性
系统 SHALL 使用 `cost_records.category_id` 引用 `cost_categories.id`，并保留历史分类名称快照用于展示。

#### Scenario: 创建账务记录
- **WHEN** 用户创建收入或支出记录并选择分类
- **THEN** 系统必须保存 `category_id` 并写入 `category_name_snapshot`

#### Scenario: 分类改名后展示历史账务
- **WHEN** 成本分类名称被修改
- **THEN** 历史账务记录必须仍可展示创建时的分类名称快照

### Requirement: 冗余索引治理
系统 SHALL 移除主键列上的冗余二级索引，并保留业务查询需要的索引。

#### Scenario: 主键索引审查
- **WHEN** 迁移脚本检查表结构
- **THEN** 对已经作为 PRIMARY KEY 的 `id` 列不得保留单独的 `ix_*_id` 二级索引

### Requirement: 迁移前数据完整性检查
系统 SHALL 在添加新外键或收紧约束前检查历史数据，并输出无法迁移的数据清单。

#### Scenario: 检测悬挂外键
- **WHEN** 运行迁移前检查
- **THEN** 系统必须列出引用不存在用户、农场、会话、分类或作物周期的记录

#### Scenario: 检测无法匹配的账务分类
- **WHEN** 运行账务分类回填检查
- **THEN** 系统必须列出无法按农场、分类名和收支类型匹配到 `cost_categories` 的 `cost_records`

