## 1. 依赖与配置

- [x] 1.1 在 `requirements.txt` 中添加 `pymysql>=1.1.0` 和 `alembic>=1.13.0`
- [x] 1.2 运行 `.venv/bin/pip install` 安装新依赖
- [x] 1.3 在 `config.yaml` 中添加 MySQL 连接串配置示例（注释形式）

## 2. 数据库引擎改造

- [x] 2.1 修改 `app/core/database.py`，为 MySQL 分支添加连接池参数（pool_size、max_overflow、pool_recycle、pool_pre_ping）
- [x] 2.2 修改 `app/core/config.py`，将 `DatabaseConfig.url` 默认值保持 SQLite 不变，确保通过 config.yaml 可覆盖为 MySQL

## 3. Alembic 迁移框架

- [x] 3.1 在 backend 目录初始化 Alembic：`alembic init alembic`
- [x] 3.2 配置 `alembic.ini` 和 `alembic/env.py`，读取 `settings.database_url`，引入 `Base.metadata`
- [x] 3.3 生成初始迁移脚本：`alembic revision --autogenerate -m "initial schema"`
- [x] 3.4 将 `seed.py` 中的 `migrate_cost_records()` 逻辑迁移为 Alembic 迁移脚本
- [x] 3.5 修改 `main.py` lifespan，将 `Base.metadata.create_all()` 替换为 `alembic upgrade head`
- [x] 3.6 验证 `alembic upgrade head` 和 `alembic downgrade -1` 正常工作

## 4. 模型层修复

- [x] 4.1 扫描所有模型文件，为无长度参数的 `Column(String)` 指定显式长度
- [x] 4.2 审查 6 个使用 `autoincrement=True` 的模型，确认 MySQL 兼容性
- [x] 4.3 审查 `DateTime(timezone=True)` 列在 MySQL 下的行为，确认时区处理正确
- [x] 4.4 运行 `alembic revision --autogenerate` 验证模型变更检测正常

## 5. 测试改造

- [x] 5.1 修改 `tests/conftest.py`，将 SQLite 测试 fixture 条件化（支持 SQLite/MySQL 双模式）
- [x] 5.2 删除 `tests/test_database_wal.py`（SQLite 专有测试）
- [x] 5.3 审查并修复 6+ 个硬编码 SQLite 连接的测试文件
- [x] 5.4 验证所有测试在 SQLite 模式下通过
- [x] 5.5 验证生产 MySQL 模式下通过迁移、启动和健康检查

## 6. 数据迁移脚本

- [x] 6.1 创建 `scripts/migrate_sqlite_to_mysql.py`，实现按外键顺序逐表迁移
- [x] 6.2 实现自动备份 SQLite 文件功能
- [x] 6.3 实现迁移后数据校验（行数对比 + 抽样内容对比）
- [x] 6.4 编写迁移脚本的使用文档（README 或注释）

## 7. 文档更新

- [x] 7.1 更新 `docs/architecture/overview.md` 中的数据库架构描述
- [x] 7.2 更新 CLAUDE.md 中的常用命令（添加 Alembic 命令）
- [x] 7.3 更新 `docs/architecture/evolution-roadmap.md` 标记此迁移完成
