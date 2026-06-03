## Why

当前后端使用 SQLite 作为数据库，随着功能增长和数据量增加，SQLite 的单文件锁机制和缺乏连接池管理成为瓶颈。迁移到 MySQL 可以支持并发访问、提供更成熟的事务隔离级别、并为未来多实例部署和读写分离打基础。

## What Changes

- **BREAKING**: 数据库从 SQLite 切换到 MySQL 8.x，连接串配置格式变更
- 引入 Alembic 作为数据库迁移框架，替代 `create_all()` + ad-hoc `ALTER TABLE` 的方式
- 修改 `database.py` 的引擎创建逻辑，为 MySQL 配置连接池参数
- 审查并修复 12+ 个未指定长度的 `String` 列，确保 MySQL 兼容
- 重构测试套件中的 SQLite 硬编码（6+ 文件），支持 MySQL 测试数据库
- 删除 SQLite 专有测试文件（`test_database_wal.py`）
- 添加 `pymysql` 依赖到 requirements.txt
- 审查 20+ 个 Skill/Service 的独立 session 创建模式对连接池的影响

## Capabilities

### New Capabilities
- `mysql-database-engine`: MySQL 数据库引擎配置、连接池管理、Alembic 迁移框架集成
- `database-migration-tooling`: 从 SQLite 到 MySQL 的数据迁移工具和脚本

### Modified Capabilities
- `database-hardening`: 数据库加固规范需适配 MySQL 特性（连接池、字符集、时区处理）

## Impact

- **核心文件**: `app/core/config.py`、`app/core/database.py`、`app/main.py`
- **模型层**: 17 个模型文件中的 String 列需显式指定长度
- **测试**: 6+ 个测试文件的 DB fixture 需改造，1 个文件需删除
- **依赖**: 新增 `pymysql`、`alembic`
- **部署**: 需要准备 MySQL 实例（Docker 或外部服务）
- **数据**: 需要迁移现有 SQLite 数据到 MySQL
