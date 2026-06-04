## Context

当前后端使用 SQLite 作为唯一数据库，通过 SQLAlchemy 2.0（legacy Query API）进行 ORM 操作。数据库层代码已经有条件分支（`startswith("sqlite")`）来区分 SQLite 和其他数据库的行为。

现状：
- 19 张表，17 个模型文件
- 无迁移框架，靠 `Base.metadata.create_all()` + `seed.py` 的 ad-hoc `ALTER TABLE`
- 测试使用 SQLite 文件数据库
- 20+ 个 Skill/Service 文件直接 `SessionLocal()` 创建独立 session

## Goals / Non-Goals

**Goals:**
- 将数据库引擎从 SQLite 切换到 MySQL 8.x
- 引入 Alembic 管理数据库 schema 演进
- 保持向后兼容（开发环境仍可用 SQLite）
- 提供数据迁移脚本（SQLite → MySQL）

**Non-Goals:**
- 不做异步数据库驱动改造（保持同步 SQLAlchemy）
- 不重构 session 管理模式（独立 `SessionLocal()` 调用暂不改）
- 不做读写分离或多数据库路由
- 不改 ORM 查询风格（暂不升级到 2.0-style `select()`）

## Decisions

### 1. 数据库驱动选择：pymysql

**选择**: `pymysql`（纯 Python 实现）

**替代方案**:
- `mysqlclient`：C 扩展，性能更好但需要系统级依赖，部署复杂
- `aiomysql`：异步驱动，但当前代码全是同步 SQLAlchemy，引入异步需大规模重构

**理由**: 纯 Python 无编译依赖，Docker 部署零额外配置，性能对当前并发量足够。

### 2. 迁移框架：Alembic

**选择**: 引入 Alembic，生成初始迁移替代 `create_all()`

**理由**:
- 当前 `seed.py` 的 ad-hoc `ALTER TABLE` 无法追踪 schema 历史
- Alembic 是 SQLAlchemy 生态的标准迁移工具
- 支持 downgrade 回滚，便于 CI/CD 流程

**改动点**:
- `main.py` 中 `Base.metadata.create_all()` → `alembic upgrade head`
- `seed.py` 中 `migrate_cost_records()` → 迁移到 Alembic 迁移脚本
- 新增 `alembic.ini` + `alembic/` 目录

### 3. 双数据库支持策略

**选择**: 通过 `config.yaml` 配置切换，代码保持条件分支

**理由**:
- 开发环境可继续用 SQLite（零依赖）
- 生产/测试环境用 MySQL
- 已有的 `startswith("sqlite")` 分支保留，新增 MySQL 分支

### 4. String 列长度策略

**选择**: 显式指定所有 `String` 列长度

**理由**: MySQL 要求 VARCHAR 有长度，SQLAlchemy 默认映射为 `VARCHAR(255)` 但不够明确。按业务语义指定合理长度。

### 5. 测试策略

**选择**: 测试保持 SQLite + 新增 MySQL CI 验证

**理由**:
- 单元测试跑 SQLite 文件数据库，速度快
- CI 中额外跑一次 MySQL 测试（Docker service）
- 删除 SQLite 专有测试（`test_database_wal.py`）

### 6. 数据迁移方式

**选择**: 编写 Python 脚本，通过 ORM 逐表迁移

**理由**:
- SQLAlchemy 的 `bulk_insert_mappings` 批量写入效率高
- 自动处理类型转换（DateTime、Boolean、Numeric）
- 19 张表数据量小，无需考虑增量同步

## Risks / Trade-offs

- **[连接池耗尽]** 20+ 个独立 `SessionLocal()` 调用在 MySQL 下可能触及 `max_connections` → 设置 `pool_size=10, max_overflow=20, pool_pre_ping=True`
- **[DateTime 时区]** MySQL 的 `TIMESTAMP` 有 2038 年限制，`DATETIME` 无时区信息 → 使用 `DATETIME` 列 + 应用层统一 UTC
- **[字符集]** MySQL 默认 `latin1` 可能导致中文乱码 → 连接串强制 `charset=utf8mb4`
- **[ Alembic 学习曲线]** 团队需熟悉 Alembic 工作流 → 文档化常用命令
