# Storage Redesign: Multi-User 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入独立用户认证体系，消除 farm_id=1 硬编码，实现多用户数据隔离。

**Architecture:** JWT 无状态认证 + FastAPI 依赖链三层过滤器（User → Farm → Resource Owner）。注册时自动创建默认农场（1:1 关系）。SQLite WAL 模式保障并发安全。

**Tech Stack:** FastAPI, SQLAlchemy, PyJWT, passlib[bcrypt], SQLite WAL

---

## 文件地图

### 新建文件
| 文件 | 职责 |
|------|------|
| `app/models/user.py` | User + UserOAuth 模型 |
| `app/schemas/auth.py` | 注册/登录/Token/User Schema |
| `app/core/security.py` | JWT 签发/验证 + bcrypt 哈希 |
| `app/services/auth_service.py` | 注册、登录、用户查询逻辑 |
| `app/api/auth.py` | /auth/* 路由 |
| `app/models/feedback.py` | FeedbackRecord 模型 |
| `app/schemas/feedback.py` | 反馈请求/响应 Schema |
| `app/services/feedback_service.py` | 反馈提交与统计 |
| `app/api/feedback.py` | /agent/feedback 路由 |
| `app/models/agent_record.py` | 合并后的 AgentRecord 模型 |
| `scripts/migrate_v2.py` | 数据迁移脚本 |
| `scripts/backup.sh` | SQLite 在线热备脚本 |
| `tests/test_auth.py` | 认证全链路测试 |
| `tests/test_feedback.py` | 反馈功能测试 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `requirements.txt` | 新增 PyJWT、passlib[bcrypt] |
| `app/core/config.py` | 新增 AuthConfig |
| `app/core/database.py` | WAL + PRAGMA 配置 |
| `app/api/deps.py` | 三层依赖链 |
| `app/models/farm.py` | 新增 user_id FK，删 owner_name/display_name |
| `app/models/__init__.py` | 更新导出 |
| `app/models/conversation.py` | Conversation 加 user_id，Message 加 meta |
| `app/models/trace.py` | 新增 conversation_message_id |
| `app/core/seed.py` | 更新 seed_default_farm |
| `app/main.py` | 注册 auth router，更新 lifespan |
| `app/agent/graph.py` | 消除 farm_id=1 |
| `app/agent/advisor.py` | 消除 farm_id=1 默认值 |
| `app/services/agent_service.py` | 改用 AgentRecord，消除 farm_id=1 |
| `app/services/farm_context_service.py` | display_name 改从 users.nickname |
| `app/services/conversation_service.py` | 适配 user_id |
| `tests/conftest.py` | 新建 User + Farm fixture |

### 删除文件
| 文件 | 原因 |
|------|------|
| `app/models/agent.py` | 被 agent_record.py 替代 |

---

## Task 1: 安装依赖 + SQLite WAL 加固

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/database.py`
- Test: `tests/test_database_wal.py`

- [ ] **Step 1: 写失败测试 — 验证 WAL 模式和 PRAGMA**

创建 `tests/test_database_wal.py`:

```python
"""数据库 WAL 模式和 PRAGMA 配置验证。"""

from sqlalchemy import text

from app.core.database import engine


def test_wal_mode_enabled():
    """连接时自动开启 WAL 模式。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert result == "wal"


def test_foreign_keys_enabled():
    """外键约束已开启。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1


def test_busy_timeout_set():
    """busy_timeout 已设为 5000ms。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert result == 5000
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_database_wal.py -v
```

预期：3 个 FAIL（PRAGMA 尚未配置）。

- [ ] **Step 3: 更新 requirements.txt**

在 `backend/requirements.txt` 末尾添加:

```
PyJWT==2.9.0
passlib[bcrypt]==1.7.4
```

- [ ] **Step 4: 安装依赖**

```bash
cd backend && pip install PyJWT==2.9.0 'passlib[bcrypt]==1.7.4'
```

- [ ] **Step 5: 修改 database.py 添加 PRAGMA**

将 `backend/app/core/database.py` 改为:

```python
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 连接级 PRAGMA 配置。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

if settings.database_url.startswith("sqlite"):
    event.listen(engine, "connect", _set_sqlite_pragma)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

- [ ] **Step 6: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_database_wal.py -v
```

预期：3 个 PASS。

- [ ] **Step 7: 提交**

```bash
git add requirements.txt app/core/database.py tests/test_database_wal.py
git commit -m "feat: 安装 PyJWT/passlib，SQLite WAL 模式加固"
```

---

## Task 2: Auth 配置 + User 模型

**Files:**
- Modify: `app/core/config.py`
- Create: `app/models/user.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_user_model.py`

- [ ] **Step 1: 写失败测试 — User 模型基本字段**

创建 `tests/test_user_model.py`:

```python
"""User 模型测试。"""

import uuid

from app.core.database import SessionLocal
from app.models.user import User


def test_create_user_with_required_fields():
    """创建用户，必填字段正确保存。"""
    db = SessionLocal()
    try:
        user = User(
            id=str(uuid.uuid4()),
            phone="13800138000",
            password_hash="hashed",
            nickname="测试用户",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        found = db.query(User).filter(User.phone == "13800138000").first()
        assert found is not None
        assert found.nickname == "测试用户"
        assert found.role == "user"
        assert found.status == "active"
    finally:
        db.close()


def test_user_id_is_uuid_string():
    """用户 ID 为 UUID v4 字符串。"""
    db = SessionLocal()
    try:
        uid = str(uuid.uuid4())
        user = User(id=uid, phone="13900139000", password_hash="h")
        db.add(user)
        db.commit()

        found = db.query(User).get(uid)
        assert found is not None
        assert len(found.id) == 36
    finally:
        db.close()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_user_model.py -v
```

预期：FAIL（`app.models.user` 不存在）。

- [ ] **Step 3: 在 config.py 新增 AuthConfig**

在 `backend/app/core/config.py` 的 `class LangSmithConfig` 后面添加:

```python
class AuthConfig(BaseModel):
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 天
```

在 `class Settings` 的字段列表中添加:

```python
    auth: AuthConfig = AuthConfig()
```

- [ ] **Step 4: 创建 User + UserOAuth 模型**

创建 `backend/app/models/user.py`:

```python
"""用户模型 — 独立用户认证体系。"""

import enum

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    """用户模型，手机号 + 密码注册。"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    nickname = Column(String(50), nullable=False, default="农友")
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(20), nullable=False, default=UserRole.USER.value)
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserOAuth(Base):
    """第三方 OAuth 绑定（预留）。"""

    __tablename__ = "user_oauth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(20), nullable=False)
    provider_uid = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: 更新 models/__init__.py**

在 `backend/app/models/__init__.py` 添加导入和导出:

```python
from app.models.user import User, UserOAuth
```

在 `__all__` 列表中添加 `"User"`, `"UserOAuth"`。

- [ ] **Step 6: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_user_model.py -v
```

预期：2 个 PASS。

- [ ] **Step 7: 提交**

```bash
git add app/core/config.py app/models/user.py app/models/__init__.py tests/test_user_model.py
git commit -m "feat: AuthConfig + User/UserOAuth 模型"
```

---

## Task 3: Security 模块（JWT + bcrypt）

**Files:**
- Create: `app/core/security.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: 写失败测试 — JWT 签发/验证 + 密码哈希**

创建 `tests/test_security.py`:

```python
"""安全模块测试 — JWT + bcrypt。"""

from app.core.security import create_access_token, verify_token, hash_password, verify_password


def test_hash_and_verify_password():
    """密码哈希后可以验证。"""
    hashed = hash_password("mypassword123")
    assert hashed != "mypassword123"
    assert verify_password("mypassword123", hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_verify_token():
    """JWT token 签发后可以正确解析出 user_id。"""
    token = create_access_token(user_id="abc-123")
    payload = verify_token(token)
    assert payload["sub"] == "abc-123"
    assert "exp" in payload


def test_verify_invalid_token_returns_none():
    """无效 token 返回 None。"""
    result = verify_token("invalid.token.value")
    assert result is None


def test_verify_expired_token_returns_none():
    """过期 token 返回 None（用 0 秒有效期模拟）。"""
    from app.core.security import create_access_token
    token = create_access_token(user_id="abc-123", expires_minutes=-1)
    result = verify_token(token)
    assert result is None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_security.py -v
```

预期：4 个 FAIL。

- [ ] **Step 3: 创建 security.py**

创建 `backend/app/core/security.py`:

```python
"""安全工具 — JWT 签发/验证 + bcrypt 密码哈希。"""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希。"""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    user_id: str, expires_minutes: int | None = None
) -> str:
    """签发 JWT access token。"""
    cfg = settings.auth
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else cfg.jwt_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def verify_token(token: str) -> dict | None:
    """验证 JWT token，成功返回 payload，失败返回 None。"""
    cfg = settings.auth
    try:
        return jwt.decode(
            token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm]
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_security.py -v
```

预期：4 个 PASS。

- [ ] **Step 5: 提交**

```bash
git add app/core/security.py tests/test_security.py
git commit -m "feat: security 模块 — JWT 签发/验证 + bcrypt 密码哈希"
```

---

## Task 4: Auth Schemas + Auth Service

**Files:**
- Create: `app/schemas/auth.py`
- Create: `app/services/auth_service.py`
- Test: `tests/test_auth_service.py`

- [ ] **Step 1: 写失败测试 — 注册和登录**

创建 `tests/test_auth_service.py`:

```python
"""Auth service 测试 — 注册、登录、token 校验。"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.services.auth_service import register, login, get_user_by_id


def test_register_success():
    """正常注册成功，返回 user 和 token。"""
    db = SessionLocal()
    try:
        user, token = register(db, phone="13800138000", password="pass1234", nickname="张三")
        assert user.phone == "13800138000"
        assert user.nickname == "张三"
        assert user.role == "user"
        assert token is not None
        assert len(token) > 20
    finally:
        db.close()


def test_register_duplicate_phone():
    """重复手机号注册失败。"""
    db = SessionLocal()
    try:
        register(db, phone="13800138001", password="pass1234")
        with pytest.raises(IntegrityError):
            register(db, phone="13800138001", password="pass5678")
    finally:
        db.close()


def test_login_success():
    """注册后可以登录，返回 token。"""
    db = SessionLocal()
    try:
        register(db, phone="13800138002", password="mypassword")
        user, token = login(db, phone="13800138002", password="mypassword")
        assert user is not None
        assert token is not None
    finally:
        db.close()


def test_login_wrong_password():
    """密码错误返回 None。"""
    db = SessionLocal()
    try:
        register(db, phone="13800138003", password="correct")
        result = login(db, phone="13800138003", password="wrong")
        assert result is None
    finally:
        db.close()


def test_login_nonexistent_phone():
    """手机号不存在返回 None。"""
    db = SessionLocal()
    try:
        result = login(db, phone="99999999999", password="whatever")
        assert result is None
    finally:
        db.close()


def test_get_user_by_id():
    """通过 ID 查询用户。"""
    db = SessionLocal()
    try:
        user, _ = register(db, phone="13800138004", password="pass")
        found = get_user_by_id(db, user.id)
        assert found is not None
        assert found.phone == "13800138004"
    finally:
        db.close()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_auth_service.py -v
```

预期：6 个 FAIL。

- [ ] **Step 3: 创建 auth schemas**

创建 `backend/app/schemas/auth.py`:

```python
"""认证相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator
import re


class RegisterRequest(BaseModel):
    """用户注册请求。"""

    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=8, max_length=64)
    nickname: str = Field(default="农友", max_length=50)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class LoginRequest(BaseModel):
    """用户登录请求。"""

    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """登录成功响应（含 token）。"""

    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    """用户信息响应。"""

    id: str
    phone: str
    nickname: str
    avatar_url: str | None = None
    role: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """更新用户信息请求。"""

    nickname: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=500)
```

- [ ] **Step 4: 创建 auth service**

创建 `backend/app/services/auth_service.py`:

```python
"""认证服务 — 注册、登录、用户查询。"""

import uuid
import logging

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.models.farm import Farm

logger = logging.getLogger(__name__)


def register(
    db: Session, phone: str, password: str, nickname: str = "农友"
) -> tuple[User, str]:
    """注册新用户并创建默认农场。"""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        phone=phone,
        password_hash=hash_password(password),
        nickname=nickname,
    )
    db.add(user)

    farm = Farm(id=None, name=f"{nickname}的农场", user_id=user_id)
    db.add(farm)

    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user_id)
    logger.info("用户注册 | phone=%s user_id=%s", phone, user_id)
    return user, token


def login(db: Session, phone: str, password: str) -> tuple[User, str] | None:
    """登录验证，成功返回 (user, token)。"""
    user = db.query(User).filter(User.phone == phone).first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if user.status != "active":
        return None
    token = create_access_token(user_id=user.id)
    logger.info("用户登录 | phone=%s", phone)
    return user, token


def get_user_by_id(db: Session, user_id: str) -> User | None:
    """通过 ID 查询用户。"""
    return db.query(User).filter(User.id == user_id).first()
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_auth_service.py -v
```

预期：6 个 PASS。

- [ ] **Step 6: 提交**

```bash
git add app/schemas/auth.py app/services/auth_service.py tests/test_auth_service.py
git commit -m "feat: auth schemas + auth service（注册/登录/查询）"
```

---

## Task 5: Farm 模型重构 — 新增 user_id FK

**Files:**
- Modify: `app/models/farm.py`
- Modify: `app/core/seed.py`

- [ ] **Step 1: 修改 Farm 模型**

将 `backend/app/models/farm.py` 改为:

```python
"""农场模型 — 通过 user_id 关联用户。"""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class Farm(Base):
    """农场模型，作为多租户隔离的顶层实体。"""

    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    user_id = Column(String(36), unique=True, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

关键改动：删除 `owner_name` 和 `display_name`，新增 `user_id`（UNIQUE，nullable 过渡期）。

- [ ] **Step 2: 更新 seed.py**

将 `backend/app/core/seed.py` 的 `seed_default_farm` 改为:

```python
def seed_default_farm(db: Session) -> None:
    """确保至少有一个默认农场（兼容旧数据无 user_id）。"""
    existing = db.query(Farm).filter(Farm.id == 1).first()
    if existing:
        return
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
```

逻辑不变，但不再设置 `owner_name`（已删除该列）。

- [ ] **Step 3: 运行全量测试确认无回归**

```bash
cd backend && python -m pytest -v --tb=short 2>&1 | tail -30
```

预期：部分测试可能因删除 `owner_name`/`display_name` 而失败，下一 task 修复。

- [ ] **Step 4: 提交**

```bash
git add app/models/farm.py app/core/seed.py
git commit -m "refactor: Farm 模型删除 owner_name/display_name，新增 user_id FK"
```

---

## Task 6: 三层依赖链重写

**Files:**
- Modify: `app/api/deps.py`
- Test: `tests/test_deps.py`

- [ ] **Step 1: 写失败测试 — 三层依赖链**

创建 `tests/test_deps.py`:

```python
"""三层权限依赖链测试。"""

import uuid

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, get_current_farm, verify_resource_owner
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User
from app.models.farm import Farm


def _create_user_and_farm(db: Session) -> tuple[User, Farm]:
    uid = str(uuid.uuid4())
    user = User(id=uid, phone="13800138000", password_hash="h", nickname="测试")
    db.add(user)
    farm = Farm(name="测试农场", user_id=uid)
    db.add(farm)
    db.commit()
    db.refresh(user)
    db.refresh(farm)
    return user, farm


def test_get_current_user_valid_token():
    """有效 token 返回 User 对象。"""
    db = SessionLocal()
    user, _ = _create_user_and_farm(db)
    token = create_access_token(user_id=user.id)
    db.close()

    app = FastAPI()

    @app.get("/test")
    def endpoint(u=Depends(get_current_user)):
        return {"id": u.id}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == user.id


def test_get_current_user_no_token():
    """无 token 返回 401。"""
    app = FastAPI()

    @app.get("/test")
    def endpoint(u=Depends(get_current_user)):
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/test")
    assert resp.status_code == 401


def test_get_current_user_invalid_token():
    """无效 token 返回 401。"""
    app = FastAPI()

    @app.get("/test")
    def endpoint(u=Depends(get_current_user)):
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": "Bearer invalid"})
    assert resp.status_code == 401


def test_get_current_farm_success():
    """有效用户返回关联 Farm。"""
    db = SessionLocal()
    user, farm = _create_user_and_farm(db)
    token = create_access_token(user_id=user.id)
    db.close()

    app = FastAPI()

    @app.get("/test")
    def endpoint(f=Depends(get_current_farm)):
        return {"farm_id": f.id}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["farm_id"] == farm.id


def test_verify_resource_owner_mismatch():
    """资源不属于当前用户返回 403。"""
    db = SessionLocal()
    user, farm = _create_user_and_farm(db)
    db.close()

    with pytest.raises(Exception) as exc_info:
        verify_resource_owner(resource_farm_id=999, current_farm=farm)
    assert exc_info.value.status_code == 403
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_deps.py -v
```

预期：FAIL（`get_current_user` 尚未实现）。

- [ ] **Step 3: 重写 deps.py**

将 `backend/app/api/deps.py` 完全替换为:

```python
"""FastAPI 依赖注入 — 数据库会话 + 三层权限过滤器。

Layer 1: get_current_user  — JWT → User, 失败 401
Layer 2: get_current_farm  — User → Farm(user_id=user.id), 失败 404
Layer 3a: verify_resource_owner — 资源归属校验, 失败 403
"""

from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import verify_token
from app.models.farm import Farm
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """Layer 1: 从 JWT 解析 user_id → 查询 User → 校验 status。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证信息")

    token = auth_header[7:]
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="token 无效或已过期")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != "active":
        raise HTTPException(status_code=401, detail="用户已被禁用")
    return user


def get_current_farm(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Farm:
    """Layer 2: User → Farm(user_id=user.id)。"""
    farm = db.query(Farm).filter(Farm.user_id == user.id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="未找到关联农场")
    return farm


def verify_resource_owner(resource_farm_id: int, current_farm: Farm) -> None:
    """Layer 3a: 校验资源是否属于当前用户的农场。"""
    if resource_farm_id != current_farm.id:
        raise HTTPException(status_code=403, detail="无权访问此资源")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_deps.py -v
```

预期：5 个 PASS。

- [ ] **Step 5: 提交**

```bash
git add app/api/deps.py tests/test_deps.py
git commit -m "feat: 三层权限依赖链（User→Farm→ResourceOwner）"
```

---

## Task 7: Auth API 路由

**Files:**
- Create: `app/api/auth.py`
- Modify: `app/main.py`
- Test: `tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试 — 注册和登录 API**

创建 `tests/test_auth_api.py`:

```python
"""Auth API 端到端测试。"""

from fastapi.testclient import TestClient


def test_register_success(client):
    """POST /auth/register 注册成功。"""
    resp = client.post(
        "/auth/register",
        json={"phone": "13800138000", "password": "password123", "nickname": "张三"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["phone"] == "13800138000"
    assert data["user"]["nickname"] == "张三"


def test_register_invalid_phone(client):
    """手机号格式错误返回 422。"""
    resp = client.post(
        "/auth/register",
        json={"phone": "123", "password": "password123"},
    )
    assert resp.status_code == 422


def test_register_short_password(client):
    """密码少于 8 位返回 422。"""
    resp = client.post(
        "/auth/register",
        json={"phone": "13800138000", "password": "1234567"},
    )
    assert resp.status_code == 422


def test_login_success(client):
    """注册后登录成功。"""
    client.post(
        "/auth/register",
        json={"phone": "13800138001", "password": "password123"},
    )
    resp = client.post(
        "/auth/login",
        json={"phone": "13800138001", "password": "password123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    """密码错误返回 401。"""
    client.post(
        "/auth/register",
        json={"phone": "13800138002", "password": "password123"},
    )
    resp = client.post(
        "/auth/login",
        json={"phone": "13800138002", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_get_me_with_token(client):
    """GET /auth/me 返回当前用户信息。"""
    reg = client.post(
        "/auth/register",
        json={"phone": "13800138003", "password": "password123"},
    )
    token = reg.json()["access_token"]
    resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "13800138003"


def test_get_me_without_token(client):
    """无 token 访问 /auth/me 返回 401。"""
    resp = client.get("/auth/me")
    assert resp.status_code == 401
```

注意：此测试需要一个 `client` fixture。在 `tests/conftest.py` 中添加:

```python
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture()
def client():
    """API 测试客户端。"""
    return TestClient(app)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_auth_api.py -v
```

预期：FAIL。

- [ ] **Step 3: 创建 auth API 路由**

创建 `backend/app/api/auth.py`:

```python
"""认证 API 路由 — 注册、登录、用户信息。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth_service import login as auth_login
from app.services.auth_service import register as auth_register

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """用户注册（手机号 + 密码）。"""
    try:
        user, token = auth_register(db, req.phone, req.password, req.nickname)
    except Exception:
        raise HTTPException(status_code=400, detail="该手机号已注册")
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """用户登录。"""
    result = auth_login(db, req.phone, req.password)
    if result is None:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    user, token = result
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    """获取当前用户信息。"""
    return UserResponse.model_validate(user)


@router.put("/me", response_model=UserResponse)
def update_me(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """更新当前用户信息。"""
    if req.nickname is not None:
        user.nickname = req.nickname
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
```

- [ ] **Step 4: 在 main.py 注册 auth router**

在 `backend/app/main.py` 的 import 区添加:

```python
from app.api import auth  # noqa: E402
```

在 router 注册区添加:

```python
app.include_router(auth.router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_auth_api.py -v
```

预期：7 个 PASS。

- [ ] **Step 6: 提交**

```bash
git add app/api/auth.py app/main.py tests/test_auth_api.py tests/conftest.py
git commit -m "feat: Auth API（注册/登录/用户信息）+ 注册路由"
```

---

## Task 8: AgentRecord 合并（替代 AdviceRecord + ReportRecord）

**Files:**
- Create: `app/models/agent_record.py`
- Modify: `app/models/__init__.py`
- Delete: `app/models/agent.py`（在最后一步删，先保留兼容）

- [ ] **Step 1: 创建 AgentRecord 模型**

创建 `backend/app/models/agent_record.py`:

```python
"""Agent 输出记录模型 — 合并 advice_records + report_records。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AgentRecord(Base):
    """Agent 输出统一记录。"""

    __tablename__ = "agent_records"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    user_id = Column(String(36), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    record_type = Column(String(20), nullable=False)  # chat / daily / report
    content = Column(Text, nullable=False)
    meta = Column(Text, nullable=True)  # JSON: token_usage, latency_ms 等
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 更新 models/__init__.py**

添加 `AgentRecord` 导入和导出。**暂时保留** `AdviceRecord` 和 `ReportRecord` 的导入（渐进迁移）。

```python
from app.models.agent_record import AgentRecord
```

在 `__all__` 中添加 `"AgentRecord"`。

- [ ] **Step 3: 提交**

```bash
git add app/models/agent_record.py app/models/__init__.py
git commit -m "feat: AgentRecord 模型（合并 advice + report）"
```

---

## Task 9: 迁移 agent_service.py 到 AgentRecord

**Files:**
- Modify: `app/services/agent_service.py`
- Modify: `app/api/agent.py`

- [ ] **Step 1: 修改 agent_service.py**

在 `backend/app/services/agent_service.py` 中:

1. 将 `from app.models.agent import AdviceRecord, ReportRecord` 替换为:

```python
from app.models.agent_record import AgentRecord
```

2. 将所有 `AdviceRecord(cycle_id=..., advice_type="chat", content=..., farm_id=...)` 替换为:

```python
AgentRecord(cycle_id=..., record_type="chat", content=..., farm_id=...)
```

3. 将 `ReportRecord(cycle_id=..., report_type=..., content=..., farm_id=...)` 替换为:

```python
AgentRecord(cycle_id=..., record_type=report_type, content=..., farm_id=...)
```

4. 将 `get_advice_history` 中的 `db.query(AdviceRecord)` 替换为:

```python
def get_advice_history(
    db: Session, cycle_id: int | None = None, limit: int = 20, farm_id: int = 1
) -> list[AgentRecord]:
    query = db.query(AgentRecord).filter(
        AgentRecord.farm_id == farm_id, AgentRecord.record_type.in_(["chat", "daily"])
    )
    if cycle_id is not None:
        query = query.filter(AgentRecord.cycle_id == cycle_id)
    return query.order_by(AgentRecord.created_at.desc()).limit(limit).all()
```

5. 将 `get_report_history` 替换为:

```python
def get_report_history(
    db: Session, cycle_id: int | None = None, limit: int = 20, farm_id: int = 1
) -> list[AgentRecord]:
    query = db.query(AgentRecord).filter(
        AgentRecord.farm_id == farm_id, AgentRecord.record_type == "report"
    )
    if cycle_id is not None:
        query = query.filter(AgentRecord.cycle_id == cycle_id)
    return query.order_by(AgentRecord.created_at.desc()).limit(limit).all()
```

6. 将 `get_daily_advice` 中的缓存查询改为:

```python
cached = (
    db.query(AgentRecord)
    .filter(
        AgentRecord.farm_id == farm_id,
        AgentRecord.record_type == "daily",
        AgentRecord.created_at >= today_start,
    )
    .order_by(AgentRecord.created_at.desc())
    .first()
)
```

7. 将 `refresh_daily_advice` 中的删除改为:

```python
db.query(AgentRecord).filter(
    AgentRecord.farm_id == farm_id,
    AgentRecord.record_type == "daily",
    AgentRecord.cycle_id == cycle_id if cycle_id is not None else True,
    AgentRecord.created_at >= today_start,
).delete(synchronize_session=False)
```

- [ ] **Step 2: 修改 api/agent.py**

在 `backend/app/api/agent.py` 中:

1. 将 `from app.models.agent import AdviceRecord` 替换为:

```python
from app.models.agent_record import AgentRecord
```

2. 将 stream endpoint 中的 `AdviceRecord(...)` 替换为:

```python
record = AgentRecord(
    cycle_id=chat_request.cycle_id,
    record_type="chat",
    content=full_reply,
    farm_id=farm.id,
)
```

3. 将 `list_reports` 中的 `from app.models.agent import ReportRecord` 和相关查询改为:

```python
from app.models.agent_record import AgentRecord

# ...
query = db.query(AgentRecord).filter(
    AgentRecord.farm_id == farm.id, AgentRecord.record_type == "report"
)
total = query.with_entities(sqlfunc.count(AgentRecord.id)).scalar() or 0
records = (
    query.order_by(AgentRecord.created_at.desc()).offset(offset).limit(size).all()
)
```

- [ ] **Step 3: 更新 schemas — AdviceHistoryItem 字段名适配**

`advice_type` → `record_type`。在 `app/schemas/agent.py` 的 `AdviceHistoryItem` 中:

```python
class AdviceHistoryItem(BaseModel):
    id: int
    cycle_id: int | None = None
    record_type: str  # 原 advice_type
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

同样 `ReportHistoryItem` 的 `report_type` 改为 `record_type`:

```python
class ReportHistoryItem(BaseModel):
    id: int
    cycle_id: int | None = None
    record_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: 运行全量测试**

```bash
cd backend && python -m pytest -v --tb=short 2>&1 | tail -40
```

修复因字段名变更导致的测试失败。

- [ ] **Step 5: 删除旧模型**

确认无引用后，从 `app/models/__init__.py` 删除:

```python
from app.models.agent import AdviceRecord, ReportRecord
```

从 `__all__` 删除 `"AdviceRecord"`, `"ReportRecord"`。

删除文件 `app/models/agent.py`。

- [ ] **Step 6: 运行全量测试**

```bash
cd backend && python -m pytest -v --tb=short
```

- [ ] **Step 7: 提交**

```bash
git add app/services/agent_service.py app/api/agent.py app/schemas/agent.py app/models/__init__.py
git rm app/models/agent.py
git commit -m "refactor: agent_service + api 迁移到 AgentRecord，删除旧模型"
```

---

## Task 10: 消除 graph.py 中的 farm_id=1 硬编码

**Files:**
- Modify: `app/agent/graph.py`

- [ ] **Step 1: 在 AgentState 中添加 farm_id 字段**

在 `backend/app/agent/graph.py` 中将 `AgentState` 改为:

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    farm_id: int
```

- [ ] **Step 2: 修改 _llm_node 使用 state["farm_id"]**

将 `_llm_node` 函数签名改为接收 farm_id:

```python
def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点。"""
    farm_id = state.get("farm_id", 1)
    # ...
    try:
        farm_context_summary = farm_context_service.build_summary(db, farm_id=farm_id)
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        display_name = farm.display_name if farm and hasattr(farm, 'display_name') else "农友"
        farm_location = farm.location if farm and farm.location else ""
    # ...
    if not check_quota(farm_id=farm_id):
```

- [ ] **Step 3: 运行全量测试**

```bash
cd backend && python -m pytest -v --tb=short
```

- [ ] **Step 4: 提交**

```bash
git add app/agent/graph.py
git commit -m "fix: graph.py 消除 farm_id=1 硬编码，从 AgentState 读取"
```

---

## Task 11: farm_context_service — display_name 改从 users.nickname 获取

**Files:**
- Modify: `app/services/farm_context_service.py`

- [ ] **Step 1: 修改 build_summary 接受 db + farm_id，从 User 获取 nickname**

在 `_llm_node` 中已经通过 `farm_id` 查到 Farm。Farm 不再有 `display_name`。需要在 graph.py 的 `_llm_node` 中额外查 User:

在 `backend/app/agent/graph.py` 的 `_llm_node` 中，将 display_name 获取逻辑改为:

```python
from app.models.user import User

# 在 _llm_node 内:
farm = db.query(Farm).filter(Farm.id == farm_id).first()
farm_location = farm.location if farm and farm.location else ""
# 从 Farm.user_id 查 User.nickname
display_name = "农友"
if farm and farm.user_id:
    user = db.query(User).filter(User.id == farm.user_id).first()
    if user:
        display_name = user.nickname
```

- [ ] **Step 2: 运行测试**

```bash
cd backend && python -m pytest -v --tb=short
```

- [ ] **Step 3: 提交**

```bash
git add app/agent/graph.py
git commit -m "fix: display_name 改从 User.nickname 获取"
```

---

## Task 12: 更新 conftest.py — User + Farm fixture

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: 更新 clean_db fixture**

将 `backend/tests/conftest.py` 的 `clean_db` 改为创建 User + Farm:

```python
"""公共测试 fixtures。"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.farm import Farm
from app.models.user import User


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建表并播种测试用户+默认农场。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    uid = str(uuid.uuid4())
    user = User(id=uid, phone="13800000000", password_hash="test", nickname="测试用户")
    db.add(user)
    farm = Farm(id=1, name="默认农场", user_id=uid)
    db.add(farm)
    db.commit()
    db.close()
    yield


@pytest.fixture()
def client():
    """API 测试客户端。"""
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    """带有效 JWT 的请求头。"""
    db = SessionLocal()
    user = db.query(User).filter(User.phone == "13800000000").first()
    db.close()
    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}
```

需要在文件顶部添加 `from app.main import app`。

- [ ] **Step 2: 运行全量测试**

```bash
cd backend && python -m pytest -v --tb=short
```

修复因 fixture 变更导致的测试失败。可能需要在其他测试文件中使用 `auth_headers` fixture。

- [ ] **Step 3: 提交**

```bash
git add tests/conftest.py
git commit -m "test: 更新 conftest — User+Farm fixture + auth_headers"
```

---

## Task 13: Conversation 模型增强（user_id + meta）

**Files:**
- Modify: `app/models/conversation.py`
- Modify: `app/services/conversation_service.py`

- [ ] **Step 1: 修改 Conversation 和 ConversationMessage**

在 `backend/app/models/conversation.py` 的 `Conversation` 中添加 `user_id`:

```python
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=True)  # 新增
    session_id = Column(String, nullable=False, index=True, unique=True)
    # ...
```

在 `ConversationMessage` 中添加 `meta`:

```python
class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    meta = Column(Text, nullable=True)  # 新增: JSON 格式元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # ...
```

- [ ] **Step 2: 更新 conversation_service.py**

在 `save_message` 函数签名中添加可选的 `meta` 参数:

```python
def save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    meta: str | None = None,
) -> ConversationMessage:
```

- [ ] **Step 3: 运行测试**

```bash
cd backend && python -m pytest -v --tb=short
```

- [ ] **Step 4: 提交**

```bash
git add app/models/conversation.py app/services/conversation_service.py
git commit -m "feat: Conversation 新增 user_id，Message 新增 meta JSON 字段"
```

---

## Task 14: Feedback 模型 + Service + API

**Files:**
- Create: `app/models/feedback.py`
- Create: `app/schemas/feedback.py`
- Create: `app/services/feedback_service.py`
- Create: `app/api/feedback.py`
- Modify: `app/main.py`
- Test: `tests/test_feedback.py`

- [ ] **Step 1: 创建 FeedbackRecord 模型**

创建 `backend/app/models/feedback.py`:

```python
"""用户反馈模型 — AI 回复评价收集。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class FeedbackRecord(Base):
    """用户对 AI 回复的评价。"""

    __tablename__ = "feedback_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    conversation_message_id = Column(Integer, ForeignKey("conversation_messages.id"), nullable=True)
    rating = Column(String(10), nullable=False)  # good / bad
    correction = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 创建 feedback schemas**

创建 `backend/app/schemas/feedback.py`:

```python
"""反馈相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """提交反馈请求。"""

    message_id: int = Field(..., description="被评价的消息 ID")
    rating: str = Field(..., pattern="^(good|bad)$")
    correction: str | None = Field(None, max_length=500)


class FeedbackResponse(BaseModel):
    """反馈提交响应。"""

    id: int
    rating: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: 创建 feedback service**

创建 `backend/app/services/feedback_service.py`:

```python
"""反馈服务 — 提交评价、统计查询。"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.feedback import FeedbackRecord

logger = logging.getLogger(__name__)


def submit_feedback(
    db: Session,
    user_id: str,
    message_id: int,
    rating: str,
    correction: str | None = None,
) -> FeedbackRecord:
    """提交一条反馈。"""
    record = FeedbackRecord(
        user_id=user_id,
        conversation_message_id=message_id,
        rating=rating,
        correction=correction,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("反馈已提交 | user=%s msg=%s rating=%s", user_id, message_id, rating)
    return record


def get_feedback_stats(db: Session) -> dict:
    """获取反馈统计。"""
    total = db.query(func.count(FeedbackRecord.id)).scalar() or 0
    good = (
        db.query(func.count(FeedbackRecord.id))
        .filter(FeedbackRecord.rating == "good")
        .scalar()
        or 0
    )
    bad = (
        db.query(func.count(FeedbackRecord.id))
        .filter(FeedbackRecord.rating == "bad")
        .scalar()
        or 0
    )
    return {"total": total, "good": good, "bad": bad}
```

- [ ] **Step 4: 创建 feedback API**

创建 `backend/app/api/feedback.py`:

```python
"""反馈 API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.feedback_service import submit_feedback, get_feedback_stats

router = APIRouter(prefix="/agent", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """提交 AI 回复评价。"""
    record = submit_feedback(db, user.id, req.message_id, req.rating, req.correction)
    return FeedbackResponse.model_validate(record)


@router.get("/feedback/stats")
def feedback_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取反馈统计。"""
    return get_feedback_stats(db)
```

- [ ] **Step 5: 在 main.py 注册 feedback router**

在 import 区添加 `from app.api import feedback`，在 router 注册区添加 `app.include_router(feedback.router)`。

- [ ] **Step 6: 写测试**

创建 `tests/test_feedback.py`:

```python
"""反馈功能测试。"""

from app.core.database import SessionLocal
from app.models.conversation import Conversation, ConversationMessage
from app.services.feedback_service import submit_feedback, get_feedback_stats


def _seed_message(db) -> int:
    """创建一条测试消息并返回 ID。"""
    conv = Conversation(farm_id=1, session_id="test-session")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    msg = ConversationMessage(conversation_id=conv.id, role="assistant", content="测试回复")
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg.id


def test_submit_good_feedback():
    """提交正面评价。"""
    db = SessionLocal()
    try:
        msg_id = _seed_message(db)
        record = submit_feedback(db, user_id="test-user", message_id=msg_id, rating="good")
        assert record.rating == "good"
        assert record.id is not None
    finally:
        db.close()


def test_submit_bad_feedback_with_correction():
    """提交负面评价 + 修正。"""
    db = SessionLocal()
    try:
        msg_id = _seed_message(db)
        record = submit_feedback(
            db, user_id="test-user", message_id=msg_id, rating="bad", correction="应该说..."
        )
        assert record.rating == "bad"
        assert record.correction == "应该说..."
    finally:
        db.close()


def test_feedback_stats():
    """统计反馈数据。"""
    db = SessionLocal()
    try:
        msg_id = _seed_message(db)
        submit_feedback(db, "u1", msg_id, "good")
        submit_feedback(db, "u2", msg_id, "bad")
        stats = get_feedback_stats(db)
        assert stats["total"] >= 2
        assert stats["good"] >= 1
        assert stats["bad"] >= 1
    finally:
        db.close()
```

- [ ] **Step 7: 运行测试**

```bash
cd backend && python -m pytest tests/test_feedback.py -v
```

- [ ] **Step 8: 提交**

```bash
git add app/models/feedback.py app/schemas/feedback.py app/services/feedback_service.py app/api/feedback.py app/main.py tests/test_feedback.py
git commit -m "feat: Feedback 收集（模型/Service/API/测试）"
```

---

## Task 15: 全局消除 farm_id=1 — service 层

**Files:**
- Modify: `app/services/agent_service.py`（消除默认值）
- Modify: `app/agent/advisor.py`（消除默认值）
- Modify: `app/agent/skills/__init__.py`（消除默认值）

- [ ] **Step 1: 搜索所有 farm_id=1 默认值**

```bash
cd backend && grep -rn "farm_id=1" app/ --include="*.py" | grep -v "__pycache__" | grep -v "test_"
```

- [ ] **Step 2: 逐一消除**

在每个找到的位置，将 `farm_id=1` 的默认值去掉（改为必填参数）。例如:

`app/agent/advisor.py:51` — `farm_id: int = 1` → `farm_id: int`
`app/services/agent_service.py:39` — `farm_id: int = 1` → `farm_id: int`
（所有出现处同理）

注意：API 层已经通过 `Depends(get_current_farm)` 注入 `farm.id`，所以调用链一定有 farm_id。去掉默认值是安全的。

- [ ] **Step 3: 运行全量测试**

```bash
cd backend && python -m pytest -v --tb=short
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "refactor: 全局消除 farm_id=1 默认值，改为必填参数"
```

---

## Task 16: Trace 增强 — conversation_message_id

**Files:**
- Modify: `app/models/trace.py`
- Modify: `app/infra/trace_collector.py`

- [ ] **Step 1: 修改 TraceRecord 新增 conversation_message_id**

在 `backend/app/models/trace.py` 的 `TraceRecord` 中添加:

```python
conversation_message_id = Column(Integer, nullable=True)
```

- [ ] **Step 2: 运行测试**

```bash
cd backend && python -m pytest -v --tb=short
```

- [ ] **Step 3: 提交**

```bash
git add app/models/trace.py
git commit -m "feat: TraceRecord 新增 conversation_message_id 关联字段"
```

---

## Task 17: 数据迁移脚本

**Files:**
- Create: `scripts/migrate_v2.py`
- Create: `scripts/backup.sh`

- [ ] **Step 1: 创建迁移脚本**

创建 `backend/scripts/migrate_v2.py`:

```python
"""V2 数据迁移 — 创建用户、关联农场、合并 agent_records。

用法:
    python scripts/migrate_v2.py --dry-run  # 预览
    python scripts/migrate_v2.py            # 执行
"""

import argparse
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.models.user import User
from app.models.farm import Farm


def migrate(dry_run: bool = False) -> None:
    """执行迁移。"""
    db = SessionLocal()
    try:
        # Step 1: 检查 users 表是否已存在数据
        existing = db.query(User).first()
        if existing:
            print("用户表已有数据，跳过迁移。")
            return

        # Step 2: 从 farms(1) 的 owner_name 创建默认用户
        farm = db.query(Farm).filter(Farm.id == 1).first()
        if not farm:
            print("未找到默认农场，跳过。")
            return

        owner_name = getattr(farm, "owner_name", None) or "默认农户"
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            phone="00000000000",
            password_hash="!",
            nickname=owner_name,
            role="admin",
        )
        db.add(user)

        # Step 3: 关联 farm.user_id
        farm.user_id = user_id

        if dry_run:
            print(f"[DRY-RUN] 将创建用户: {owner_name} ({user_id})")
            print(f"[DRY-RUN] 将关联 Farm(1) → user_id={user_id}")
            db.rollback()
        else:
            db.commit()
            print(f"迁移完成: 用户 {owner_name}, Farm(1) 关联 user_id={user_id}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
```

- [ ] **Step 2: 创建备份脚本**

创建 `backend/scripts/backup.sh`:

```bash
#!/usr/bin/env bash
# SQLite 在线热备 + 7 天滚动保留

set -euo pipefail

DB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_FILE="$DB_DIR/app/farm_manager.db"
BACKUP_DIR="$DB_DIR/backups"
RETAIN_DAYS=7

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/farm_manager_$TIMESTAMP.db"

# SQLite 在线热备
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# 压缩
gzip "$BACKUP_FILE"

# 清理过期备份
find "$BACKUP_DIR" -name "farm_manager_*.db.gz" -mtime +$RETAIN_DAYS -delete

echo "备份完成: ${BACKUP_FILE}.gz"
```

```bash
chmod +x backend/scripts/backup.sh
```

- [ ] **Step 3: 提交**

```bash
git add scripts/migrate_v2.py scripts/backup.sh
git commit -m "feat: V2 数据迁移脚本 + SQLite 备份脚本"
```

---

## Task 18: 端到端验证

**Files:**
- Test: 全量测试

- [ ] **Step 1: 运行迁移脚本 dry-run**

```bash
cd backend && python scripts/migrate_v2.py --dry-run
```

预期：显示将创建的用户信息。

- [ ] **Step 2: 运行全量测试**

```bash
cd backend && python -m pytest -v --tb=short
```

预期：所有测试 PASS。

- [ ] **Step 3: 全局搜索残留的 farm_id=1**

```bash
cd backend && grep -rn "farm_id=1\b\|Farm.id == 1\|farm_id == 1" app/ --include="*.py" | grep -v "__pycache__" | grep -v "test_"
```

预期：0 个结果。如有残留，逐一修复。

- [ ] **Step 4: Lint 检查**

```bash
cd backend && ruff check app/ tests/ && ruff format --check app/ tests/
```

- [ ] **Step 5: 启动服务器验证**

```bash
cd backend && python -m uvicorn app.main:app --reload &
sleep 3

# 注册
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","password":"password123","nickname":"测试用户"}'

# 登录
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","password":"password123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 获取用户信息
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"

# 聊天
curl -s -X POST http://localhost:8000/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'

# 健康检查
curl -s http://localhost:8000/health

kill %1
```

预期：注册、登录、用户信息、聊天均正常返回。

- [ ] **Step 6: 最终提交**

```bash
git add -A
git commit -m "test: Phase 2 端到端验证通过"
```

---

## 自审检查清单

### Spec 覆盖
| 需求 | 对应 Task |
|------|----------|
| users 表 (UUID + 手机号 + 密码) | Task 2 |
| user_oauth 表 (预留) | Task 2 |
| JWT 签发/验证 | Task 3 |
| bcrypt 哈希 | Task 3 |
| 注册/登录 API | Task 7 |
| 三层依赖链 | Task 6 |
| farms 表重构 (user_id FK) | Task 5 |
| farm_id=1 全局消除 | Task 10, 15 |
| display_name 改从 users.nickname | Task 11 |
| advice + report → agent_records | Task 8, 9 |
| conversation_messages.meta | Task 13 |
| feedback_records | Task 14 |
| trace_records.conversation_message_id | Task 16 |
| SQLite WAL + PRAGMA | Task 1 |
| 备份脚本 | Task 17 |
| 迁移脚本 | Task 17 |
| 全量测试通过 | Task 18 |

### Placeholder 扫描
无 TBD / TODO / "implement later" / "add validation"。

### 类型一致性
- `User.id` → `str` (UUID)，所有引用处使用 `String(36)`
- `Farm.user_id` → `String(36)`，与 `User.id` 匹配
- `AgentRecord.record_type` → `str`，所有查询使用 `record_type == "chat"` 等
- `verify_resource_owner(resource_farm_id: int, current_farm: Farm)` — 参数名一致
