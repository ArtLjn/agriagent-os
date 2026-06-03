# SQLite → MySQL 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将后端数据库从 SQLite 迁移到 MySQL 8.x，引入 Alembic 迁移框架，保持开发环境 SQLite 兼容。

**Architecture:** 通过 SQLAlchemy 引擎的条件分支支持双数据库。生产用 MySQL + 连接池，开发用 SQLite。引入 Alembic 替代 `create_all()` + ad-hoc ALTER TABLE。数据迁移通过 Python 脚本逐表完成。

**Tech Stack:** SQLAlchemy 2.0, pymysql, Alembic, MySQL 8.x

---

## 1. 依赖安装

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 添加新依赖到 requirements.txt**

在 `backend/requirements.txt` 末尾添加：

```
pymysql>=1.1.0
alembic>=1.13.0
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend && pip install pymysql>=1.1.0 alembic>=1.13.0`
Expected: 成功安装

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add pymysql and alembic dependencies"
```

---

## 2. 数据库引擎改造

**Files:**
- Modify: `backend/app/core/database.py`

- [ ] **Step 1: 改写 database.py 支持双数据库**

将 `backend/app/core/database.py` 完整替换为：

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    """SQLite 连接级 PRAGMA 配置。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs = {}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    })

engine = create_engine(settings.database_url, **_engine_kwargs)

if _is_sqlite:
    event.listen(engine, "connect", _set_sqlite_pragma)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

- [ ] **Step 2: 验证 SQLite 模式不受影响**

Run: `cd backend && python -c "from app.core.database import engine, _is_sqlite; print('sqlite:', _is_sqlite, engine.url)"`
Expected: `sqlite: True sqlite:///...`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/database.py
git commit -m "refactor: dual database engine support with MySQL connection pool"
```

---

## 3. 初始化 Alembic

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/`（目录）

- [ ] **Step 1: 初始化 Alembic**

Run: `cd backend && alembic init alembic`
Expected: 创建 `alembic.ini` 和 `alembic/` 目录

- [ ] **Step 2: 配置 alembic.ini 的 sqlalchemy.url**

编辑 `backend/alembic.ini`，将 `sqlalchemy.url` 行替换为从配置读取：

找到：
```
sqlalchemy.url = driver://user:pass@localhost/dbname
```
替换为：
```
# sqlAlchemy.url 由 env.py 动态读取，此处留空
sqlalchemy.url =
```

- [ ] **Step 3: 改写 alembic/env.py**

将 `backend/alembic/env.py` 中的关键部分替换。在文件顶部 import 区域后、`target_metadata` 之前，添加：

```python
import sys
from pathlib import Path

# 将 backend/ 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import Base

# 导入所有模型以确保 Base.metadata 包含所有表
from app.models import *  # noqa: F401,F403

target_metadata = Base.metadata

# 覆盖 sqlalchemy.url
config.set_main_option("sqlalchemy.url", settings.database_url)
```

同时确保 `run_migrations_online` 函数中的 `connectable` 使用：

```python
connectable = engine
```

其中 `engine` 从 `app.core.database` 导入：

```python
from app.core.database import engine
```

完整替换 `run_migrations_online` 函数：

```python
def run_migrations_online() -> None:
    from app.core.database import engine

    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()
```

删除 `run_migrations_offline` 函数体中的原始实现（保留函数定义），改为直接调用 online 版本：

```python
def run_migrations_offline() -> None:
    run_migrations_online()
```

- [ ] **Step 4: 导入所有模型确保 Alembic 能检测到**

验证 `backend/app/models/__init__.py` 导入了所有模型。运行：

Run: `cd backend && python -c "from app.core.database import Base; print(len(Base.metadata.tables))"`
Expected: 输出数字 >= 19（对应 19+ 张表）

- [ ] **Step 5: 生成初始迁移**

Run: `cd backend && alembic revision --autogenerate -m "initial schema from sqlite"`
Expected: 生成 `alembic/versions/xxx_initial_schema_from_sqlite.py`，包含所有表的 create_table 操作

- [ ] **Step 6: 验证迁移可执行**

Run: `cd backend && alembic upgrade head`
Expected: 成功，无报错

Run: `cd backend && alembic downgrade -1`
Expected: 成功，所有表被删除

Run: `cd backend && alembic upgrade head`
Expected: 成功，重新创建所有表

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat: initialize Alembic migration framework"
```

---

## 4. 替换启动时的 create_all

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/seed.py`

- [ ] **Step 1: 改写 main.py 的 lifespan 中的数据库初始化**

在 `backend/app/main.py` 中，替换 lifespan 函数里的数据库初始化部分。

找到（约第 67-68 行）：
```python
    await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    await asyncio.to_thread(migrate_cost_records)
```

替换为：
```python
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext

    alembic_cfg = AlembicConfig(str(Path(__file__).resolve().parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

    def _run_alembic_upgrade():
        from alembic import command
        command.upgrade(alembic_cfg, "head")

    await asyncio.to_thread(_run_alembic_upgrade)
```

同时移除 `main.py` 顶部的无用导入（如果 `Base` 和 `engine` 不再被使用）：
- 移除 `from app.core.database import engine, Base`（如果只剩 `SessionLocal` 被用）
- 改为 `from app.core.database import SessionLocal`（仅保留实际使用的）
- 移除 `from app.core.seed import migrate_cost_records`（不再需要）

- [ ] **Step 2: 清理 seed.py 中的 migrate_cost_records**

`migrate_cost_records()` 函数的逻辑已由 Alembic 迁移脚本覆盖。在 `seed.py` 中删除该函数及其关联的 `_P1_NEW_COLUMNS` 常量。保留 `seed_default_farm` 和 `seed_admin_user`。

修改后的 `backend/app/core/seed.py`：

```python
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.farm import Farm
from app.models.user import User

logger = logging.getLogger(__name__)


def seed_default_farm(db: Session) -> None:
    """确保至少有一个默认农场（兼容旧数据无 user_id）。"""
    existing = db.query(Farm).filter(Farm.name == "默认农场").first()
    if existing:
        return
    db.add(Farm(name="默认农场"))
    db.commit()


def seed_admin_user(db: Session, phone: str, password: str) -> None:
    """根据配置自动创建管理员账号，并关联 Farm（仅当不存在时）。"""
    if not phone or not password:
        return
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
            db.commit()
            logger.info("已将用户 %s 提升为管理员", phone)
        farm = db.query(Farm).filter(Farm.user_id == existing.id).first()
        if not farm:
            db.add(Farm(name="管理员农场", user_id=existing.id))
            db.commit()
            logger.info("已为管理员 %s 创建关联农场", phone)
        return
    admin_id = str(uuid.uuid4())
    db.add(
        User(
            id=admin_id,
            phone=phone,
            password_hash=hash_password(password),
            nickname="系统管理员",
            role="admin",
            status="active",
        )
    )
    db.add(Farm(name="管理员农场", user_id=admin_id))
    db.commit()
    logger.info("已根据配置创建管理员账号 %s 并关联农场", phone)
```

- [ ] **Step 3: 验证应用启动正常**

Run: `cd backend && python -c "from app.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/core/seed.py
git commit -m "refactor: replace create_all with Alembic upgrade on startup"
```

---

## 5. 模型层修复 — String 列显式长度

**Files:**
- Modify: `backend/app/models/log.py`
- Modify: `backend/app/models/farm.py`
- Modify: `backend/app/models/crop.py`
- Modify: `backend/app/models/cost.py`
- Modify: `backend/app/models/conversation.py`
- Modify: `backend/app/models/cycle.py`

- [ ] **Step 1: 修复 log.py**

修改 `backend/app/models/log.py` 第 14、17、18 行：

```python
    operation_type = Column(String(50), nullable=False)
    operation_date = Column(Date, nullable=False)
    operation_time = Column(DateTime, nullable=True)
    note = Column(String(500), nullable=True)
    photo_urls = Column(String(2000), nullable=True)
```

- [ ] **Step 2: 修复 farm.py**

修改 `backend/app/models/farm.py` 第 14、15 行：

```python
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=True)
```

- [ ] **Step 3: 修复 crop.py**

修改 `backend/app/models/crop.py` 第 14、15、36、39 行：

```python
# CropTemplate:
    name = Column(String(100), nullable=False)
    variety = Column(String(100), nullable=True)

# GrowthStage:
    name = Column(String(100), nullable=False)
    key_tasks = Column(String(500), nullable=True)
```

- [ ] **Step 4: 修复 cost.py**

修改 `backend/app/models/cost.py` 第 23、24、27、28、29 行：

```python
    record_type = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    record_date = Column(Date, nullable=False)
    note = Column(String(500), nullable=True)
    record_subtype = Column(String(50), nullable=True)
    counterparty = Column(String(100), nullable=True)
```

- [ ] **Step 5: 修复 conversation.py**

修改 `backend/app/models/conversation.py` 第 26、27、49 行：

```python
# Conversation:
    session_id = Column(String(64), nullable=False, index=True, unique=True)
    status = Column(String(20), nullable=False, default=ConversationStatus.ACTIVE.value)

# ConversationMessage:
    role = Column(String(20), nullable=False)
```

- [ ] **Step 6: 修复 cycle.py**

修改 `backend/app/models/cycle.py` 第 14、17、18、35、40 行：

```python
# CropCycle:
    name = Column(String(100), nullable=False)
    field_name = Column(String(100), nullable=True)
    status = Column(String(20), default="active")

# CycleStage:
    name = Column(String(100), nullable=False)
    key_tasks = Column(String(500), nullable=True)
```

- [ ] **Step 7: 生成 Alembic 迁移脚本**

Run: `cd backend && alembic revision --autogenerate -m "add explicit string lengths for mysql"`
Expected: 生成迁移脚本，包含 ALTER TABLE 将 VARCHAR 列改为指定长度

- [ ] **Step 8: 验证迁移可执行**

Run: `cd backend && alembic upgrade head`
Expected: 成功

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/ backend/alembic/versions/
git commit -m "fix: add explicit string lengths for MySQL compatibility"
```

---

## 6. 测试改造

**Files:**
- Modify: `backend/tests/conftest.py`
- Delete: `backend/tests/test_database_wal.py`
- Modify: `backend/tests/test_cost_category.py`
- Modify: `backend/tests/test_agent_models.py`
- Modify: `backend/tests/test_advice_cache.py`
- Modify: `backend/tests/simulation/test_state_snapshot.py`
- Modify: `backend/tests/skills/test_settle_debt_structured.py`

- [ ] **Step 1: 改写 conftest.py，移除对 _set_sqlite_pragma 的依赖**

将 `backend/tests/conftest.py` 替换为：

```python
"""公共测试 fixtures。"""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_farm, get_current_user, get_db
from app.core.database import Base
from app.core.security import create_access_token
from app.main import app
from app.models.farm import Farm
from app.models.user import User


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    """SQLite 测试用 PRAGMA 配置。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_test_engine = create_engine(
    "sqlite:///tests/test_farm_manager.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)

    db = _TestSession()
    user = User(
        id="test-user-001",
        phone="00000000000",
        password_hash="h",
        nickname="测试用户",
        status="active",
    )
    db.add(user)
    farm = Farm(id=1, name="默认农场", user_id="test-user-001")
    db.add(farm)
    db.commit()
    db.close()

    def _override_get_db():
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        return User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            role="user",
            status="active",
        )

    def override_get_current_farm(db=Depends(_override_get_db)):
        return db.query(Farm).filter(Farm.id == 1).first()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_farm] = override_get_current_farm

    yield

    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    """API 测试客户端。"""
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    """带有效 JWT 的请求头。"""
    token = create_access_token(user_id="test-user-001")
    return {"Authorization": f"Bearer {token}"}
```

关键改动：从 `app.core.database` 导入改为本地定义 `_set_sqlite_pragma`，不再依赖生产代码中的 SQLite 特定函数。

- [ ] **Step 2: 删除 test_database_wal.py**

Run: `rm backend/tests/test_database_wal.py`

- [ ] **Step 3: 修复 test_cost_category.py**

在 `backend/tests/test_cost_category.py` 中，将导入行：
```python
from app.core.database import Base, _set_sqlite_pragma
```
改为：
```python
from app.core.database import Base
```

然后在文件中添加本地 pragma 函数（在 import 之后、engine 创建之前）：

```python
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
```

- [ ] **Step 4: 修复 test_agent_models.py**

同 Step 3 模式：将 `from app.core.database import Base, _set_sqlite_pragma` 改为 `from app.core.database import Base`，添加本地 `_set_sqlite_pragma` 函数。

- [ ] **Step 5: 修复 test_advice_cache.py**

在 `backend/tests/test_advice_cache.py` 中，检查是否有 `from app.core.database import _set_sqlite_pragma`。如果有，移除该导入并删除相关 pragma 调用（因为该文件用内存数据库，不需要 PRAGMA）。

- [ ] **Step 6: 修复 simulation/test_state_snapshot.py**

同 Step 3 模式：将 `_set_sqlite_pragma` 导入改为本地定义。

- [ ] **Step 7: 修复 skills/test_settle_debt_structured.py**

同 Step 3 模式：将 `_set_sqlite_pragma` 导入改为本地定义。

- [ ] **Step 8: 运行测试验证**

Run: `cd backend && python -m pytest tests/ -x -q --tb=short 2>&1 | head -50`
Expected: 所有测试通过或仅有与本次改动无关的已知失败

- [ ] **Step 9: Commit**

```bash
git add backend/tests/
git commit -m "test: decouple test fixtures from production SQLite pragma"
```

---

## 7. 配置文件更新

**Files:**
- Modify: `backend/config.yaml`

- [ ] **Step 1: 在 config.yaml 中添加 MySQL 配置示例**

在 `backend/config.yaml` 的 database 注释处（约第 9-10 行），添加 MySQL 配置示例：

```yaml
# database:
#   url: "sqlite:///./farm_manager.db"  # 默认使用项目根目录绝对路径，无需配置
#   url: "mysql+pymysql://user:password@localhost:3306/farm_manager?charset=utf8mb4"  # MySQL 8.x
```

- [ ] **Step 2: Commit**

```bash
git add backend/config.yaml
git commit -m "docs: add MySQL connection string example to config"
```

---

## 8. 数据迁移脚本

**Files:**
- Create: `backend/scripts/migrate_sqlite_to_mysql.py`

- [ ] **Step 1: 创建迁移脚本**

创建 `backend/scripts/migrate_sqlite_to_mysql.py`：

```python
"""SQLite → MySQL 数据迁移脚本。

用法:
    cd backend
    python scripts/migrate_sqlite_to_mysql.py \
        --source ../farm_manager.db \
        --target "mysql+pymysql://user:pass@localhost:3306/farm_manager?charset=utf8mb4"
"""

import argparse
import shutil
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker


# 按外键依赖顺序排列的表迁移顺序
TABLE_ORDER = [
    "farms",
    "users",
    "crop_templates",
    "growth_stages",
    "crop_cycles",
    "cycle_stages",
    "farm_logs",
    "cost_categories",
    "cost_records",
    "agent_records",
    "conversations",
    "conversation_messages",
    "feedback_records",
    "user_settings",
    "token_daily_stats",
    "trace_records",
    "guardrails_logs",
    "idempotency_keys",
    "simulation_runs",
    "simulation_results",
]


def backup_sqlite(source_path: str) -> str:
    """备份 SQLite 文件。"""
    src = Path(source_path)
    if not src.exists():
        print(f"错误: SQLite 文件不存在: {source_path}")
        sys.exit(1)
    backup_path = str(src) + ".bak"
    shutil.copy2(src, backup_path)
    print(f"已备份: {backup_path}")
    return backup_path


def check_target_not_empty(target_url: str) -> bool:
    """检查目标 MySQL 是否已有数据。"""
    engine = create_engine(target_url)
    insp = inspect(engine)
    total_rows = 0
    for table in insp.get_table_names():
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM `{table}`"))
            count = result.scalar()
            total_rows += count
    engine.dispose()
    return total_rows > 0


def migrate_table(src_session, dst_session, table: str) -> int:
    """迁移单张表。"""
    from sqlalchemy import text

    rows = src_session.execute(text(f"SELECT * FROM {table}")).mappings().all()
    if not rows:
        print(f"  {table}: 0 行 (跳过)")
        return 0

    cols = list(rows[0].keys())
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    insert_sql = text(f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})")

    dicts = [dict(row) for row in rows]
    dst_session.execute(insert_sql, dicts)
    dst_session.commit()
    print(f"  {table}: {len(dicts)} 行")
    return len(dicts)


def verify(src_engine, dst_engine) -> None:
    """验证迁移结果。"""
    from sqlalchemy import text

    insp = inspect(src_engine)
    tables = [t for t in TABLE_ORDER if t in insp.get_table_names()]

    print("\n校验结果:")
    all_ok = True
    for table in tables:
        with src_engine.connect() as conn:
            src_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        with dst_engine.connect() as conn:
            dst_count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
        status = "✓" if src_count == dst_count else "✗"
        if src_count != dst_count:
            all_ok = False
        print(f"  {status} {table}: SQLite={src_count} MySQL={dst_count}")

    if all_ok:
        print("\n迁移校验通过！")
    else:
        print("\n迁移校验存在差异，请检查！")


def main():
    parser = argparse.ArgumentParser(description="SQLite → MySQL 数据迁移")
    parser.add_argument("--source", required=True, help="SQLite 文件路径")
    parser.add_argument("--target", required=True, help="MySQL 连接串")
    parser.add_argument("--skip-backup", action="store_true", help="跳过备份")
    args = parser.parse_args()

    if not args.skip_backup:
        backup_sqlite(args.source)

    src_url = f"sqlite:///{args.source}"
    src_engine = create_engine(src_url)
    dst_engine = create_engine(args.target, pool_size=5, max_overflow=10)

    # 确保 MySQL schema 存在
    print("检查目标数据库 schema...")
    dst_insp = inspect(dst_engine)
    dst_tables = dst_insp.get_table_names()
    if not dst_tables:
        print("错误: 目标 MySQL 数据库为空，请先运行 alembic upgrade head")
        sys.exit(1)

    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)

    src_insp = inspect(src_engine)
    src_tables = set(src_insp.get_table_names())

    print("\n开始迁移:")
    total = 0
    for table in TABLE_ORDER:
        if table not in src_tables:
            print(f"  {table}: 源表不存在 (跳过)")
            continue
        src_session = SrcSession()
        dst_session = DstSession()
        try:
            count = migrate_table(src_session, dst_session, table)
            total += count
        except Exception as e:
            dst_session.rollback()
            print(f"  {table}: 失败 - {e}")
        finally:
            src_session.close()
            dst_session.close()

    print(f"\n迁移完成，共 {total} 行")

    verify(src_engine, dst_engine)

    src_engine.dispose()
    dst_engine.dispose()


if __name__ == "__main__":
    import sqlalchemy
    main()
```

- [ ] **Step 2: 验证脚本语法**

Run: `cd backend && python -c "import ast; ast.parse(open('scripts/migrate_sqlite_to_mysql.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/
git commit -m "feat: add SQLite to MySQL data migration script"
```

---

## 9. MySQL 连通性验证

**前置条件**: 需要一个运行中的 MySQL 8.x 实例。

- [ ] **Step 1: 创建 MySQL 数据库**

```sql
CREATE DATABASE farm_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

- [ ] **Step 2: 配置 config.yaml 指向 MySQL**

在 `backend/config.yaml` 中取消 database 部分注释并填入 MySQL 连接串：

```yaml
database:
  url: "mysql+pymysql://user:password@localhost:3306/farm_manager?charset=utf8mb4"
```

- [ ] **Step 3: 运行 Alembic 迁移**

Run: `cd backend && alembic upgrade head`
Expected: 成功，MySQL 中创建所有表

- [ ] **Step 4: 验证应用启动**

Run: `cd backend && timeout 5 python -m uvicorn app.main:app --host 0.0.0.0 --port 8099 || true`
Expected: 日志显示 Alembic upgrade 成功，应用正常启动

- [ ] **Step 5: 数据迁移（如有 SQLite 数据）**

Run: `cd backend && python scripts/migrate_sqlite_to_mysql.py --source ./farm_manager.db --target "mysql+pymysql://user:password@localhost:3306/farm_manager?charset=utf8mb4"`
Expected: 迁移完成，校验通过

- [ ] **Step 6: 切回 SQLite 配置（开发用）**

恢复 `backend/config.yaml` 的 database 部分为注释状态，确保开发环境不受影响。

---

## 10. 文档更新

**Files:**
- Modify: `.claude/CLAUDE.md`（项目级）
- Modify: `docs/architecture/overview.md`（如果存在）

- [ ] **Step 1: 更新 CLAUDE.md 常用命令表**

在常用命令表中添加 Alembic 相关命令：

```markdown
| Alembic 生成迁移 | ``alembic revision --autogenerate -m "描述"`` |
| Alembic 执行迁移 | ``alembic upgrade head`` |
| Alembic 回滚 | ``alembic downgrade -1`` |
| 数据迁移(SQLite→MySQL) | ``python scripts/migrate_sqlite_to_mysql.py --source ./farm_manager.db --target "mysql+pymysql://..."`` |
```

- [ ] **Step 2: Commit**

```bash
git add .claude/CLAUDE.md docs/
git commit -m "docs: add Alembic commands and MySQL migration docs"
```
