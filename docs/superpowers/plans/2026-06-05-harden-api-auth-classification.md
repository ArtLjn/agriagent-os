# Harden API Auth Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有 HTTP API 显式归类为公开、登录用户、农场资源或管理员接口，并用行为测试与路由审计测试防止 `/admin/*` 和业务资源接口重新退回匿名访问。

**Architecture:** 继续使用 FastAPI dependency injection，不引入全局认证中间件或新权限模型；管理路由使用 router 级 `Depends(require_admin)`，业务路由继续依赖 `get_current_user` 或 `get_current_farm`。新增测试 helper 在单个鉴权测试中清理全局 dependency overrides，用真实 JWT 覆盖匿名、普通用户、管理员三类行为；新增审计测试扫描 FastAPI 实际注册的 `APIRoute` dependency graph，输出未归类路由的方法和路径。

**Tech Stack:** FastAPI, SQLAlchemy, PyJWT, pytest, FastAPI TestClient, ruff, OpenSpec。

---

## File Structure

- Create: `backend/tests/api/auth_helpers.py`
  - 提供真实 JWT 鉴权测试 helper：创建普通用户、管理员、请求头，并在测试作用域内保留数据库 override、移除用户/farm override。
- Create: `backend/tests/api/test_admin_auth_classification.py`
  - 覆盖 `/admin/skills`、`/admin/prompts`、`/admin/config`、`/admin/cache/clear`、`/admin/prompts/reload`、`/admin/traces`、`/admin/traces/{request_id}/timeline`、`/admin/traces/{request_id}/nodes/{node_id}`、`/admin/guardrails-logs` 的 401/403/200 行为。
- Create: `backend/tests/api/test_route_auth_classification.py`
  - 扫描 `app.routes`，排除 OpenAPI/docs 内置路由，维护公开白名单，识别 `get_current_user`、`get_current_farm`、`require_admin`，失败时输出未归类路由。
- Modify: `backend/tests/api/test_admin_config.py`
  - 业务成功用例改为携带管理员 token，不再依赖全局 `get_current_user` override。
- Modify: `backend/tests/api/test_admin_trace.py`
  - mock DB 成功用例改为携带管理员 token，并避免每个测试结束时误清空其他 fixture 设置。
- Modify: `backend/app/api/admin_config.py`
  - router 级添加 `Depends(require_admin)`。
- Modify: `backend/app/api/admin_trace.py`
  - router 级添加 `Depends(require_admin)`。
- Modify: `backend/app/api/admin.py`
  - router 级添加 `Depends(require_admin)`。
- Read-only check: `backend/app/api/admin_stats.py`
  - 确认已有 endpoint 继续使用 `require_admin`。
- Read-only check: `backend/app/api/admin_users.py`
  - 确认已有 endpoint 继续使用 `require_admin`。
- Read-only check: `admin-web/src/api/client.ts`
  - 确认请求 interceptor 注入 `Authorization: Bearer <token>`，401 时清 token 并跳转 `/login`。

---

### Task 1: 真实 JWT 鉴权测试 Helper

**Files:**
- Create: `backend/tests/api/auth_helpers.py`
- Test: `backend/tests/api/test_admin_auth_classification.py`

- [ ] **Step 1: Write failing helper consumer test**

Create `backend/tests/api/test_admin_auth_classification.py`:

```python
"""Admin API 鉴权分类行为测试。"""

from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import (
    admin_headers,
    auth_override_scope,
    ensure_admin_user,
    ensure_regular_user,
    regular_headers,
)


def test_admin_skills_rejects_anonymous_with_real_auth(db_session):
    """匿名访问管理接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).get("/admin/skills")

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py::test_admin_skills_rejects_anonymous_with_real_auth -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tests.api.auth_helpers'`。

- [ ] **Step 3: Implement the helper**

Create `backend/tests/api/auth_helpers.py`:

```python
"""API 鉴权测试辅助函数。"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_current_user
from app.core.security import create_access_token
from app.models.farm import Farm
from app.models.user import User


REGULAR_USER_ID = "auth-regular-001"
ADMIN_USER_ID = "auth-admin-001"


@contextmanager
def auth_override_scope(app: FastAPI) -> Iterator[None]:
    """只移除用户/farm override，保留测试数据库 override。"""
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_farm, None)
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def ensure_regular_user(db: Session) -> User:
    """确保普通用户和对应农场存在。"""
    user = db.query(User).filter(User.id == REGULAR_USER_ID).first()
    if user is None:
        user = User(
            id=REGULAR_USER_ID,
            phone="18800000001",
            password_hash="h",
            nickname="普通用户",
            role="user",
            status="active",
        )
        db.add(user)
        db.flush()
    _ensure_farm(db, user.id, "普通用户农场")
    db.commit()
    db.refresh(user)
    return user


def ensure_admin_user(db: Session) -> User:
    """确保管理员用户和对应农场存在。"""
    user = db.query(User).filter(User.id == ADMIN_USER_ID).first()
    if user is None:
        user = User(
            id=ADMIN_USER_ID,
            phone="18800000002",
            password_hash="h",
            nickname="管理员",
            role="admin",
            status="active",
        )
        db.add(user)
        db.flush()
    _ensure_farm(db, user.id, "管理员农场")
    db.commit()
    db.refresh(user)
    return user


def regular_headers() -> dict[str, str]:
    """普通用户 Bearer token 请求头。"""
    token = create_access_token(user_id=REGULAR_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict[str, str]:
    """管理员 Bearer token 请求头。"""
    token = create_access_token(user_id=ADMIN_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _ensure_farm(db: Session, user_id: str, name: str) -> Farm:
    farm = db.query(Farm).filter(Farm.user_id == user_id).first()
    if farm is None:
        farm = Farm(name=name, user_id=user_id)
        db.add(farm)
        db.flush()
    return farm
```

- [ ] **Step 4: Run test to verify current bug is exposed**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py::test_admin_skills_rejects_anonymous_with_real_auth -v
```

Expected: FAIL with `assert 200 == 401` because `/admin/skills` is still anonymous.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/api/auth_helpers.py backend/tests/api/test_admin_auth_classification.py
git commit -m "test: add admin auth classification helper"
```

---

### Task 2: Admin Config Router 管理员鉴权

**Files:**
- Modify: `backend/app/api/admin_config.py`
- Modify: `backend/tests/api/test_admin_config.py`
- Modify: `backend/tests/api/test_admin_auth_classification.py`

- [ ] **Step 1: Add failing behavior tests for admin config endpoints**

Replace `backend/tests/api/test_admin_auth_classification.py` with:

```python
"""Admin API 鉴权分类行为测试。"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import (
    admin_headers,
    auth_override_scope,
    ensure_admin_user,
    ensure_regular_user,
    regular_headers,
)


AdminRequest = tuple[str, str, Callable[[str], dict]]


ADMIN_CONFIG_REQUESTS: list[AdminRequest] = [
    ("GET", "/admin/skills", lambda _method: {}),
    ("GET", "/admin/prompts", lambda _method: {}),
    ("GET", "/admin/config", lambda _method: {}),
    ("POST", "/admin/cache/clear", lambda _method: {}),
    ("POST", "/admin/prompts/reload", lambda _method: {}),
]


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_CONFIG_REQUESTS)
def test_admin_config_endpoints_reject_anonymous(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """匿名访问 admin config 相关接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).request(method, path, **kwargs_factory(method))

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_CONFIG_REQUESTS)
def test_admin_config_endpoints_reject_regular_user(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """普通用户访问 admin config 相关接口返回 403。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=regular_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_ADMIN_REQUIRED"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_CONFIG_REQUESTS)
def test_admin_config_endpoints_allow_admin(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """管理员访问 admin config 相关接口返回业务结果。"""
    ensure_admin_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=admin_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify failures**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py -v
```

Expected: anonymous and regular-user cases FAIL with `200` instead of `401`/`403` for admin config endpoints.

- [ ] **Step 3: Add router-level admin dependency**

Modify `backend/app/api/admin_config.py` imports and router:

```python
"""Admin 配置管理 API — Skills/Prompts/Config/Cache。"""

import logging

from fastapi import APIRouter, Depends

from app.agent.prompt_registry import get_registry
from app.agent.skills import get_skill_manager
from app.agent.skills.metadata import metadata_to_dict
from app.api.deps import require_admin
from app.core.config import settings
from app.infra.skill_cache import clear_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin-config"],
    dependencies=[Depends(require_admin)],
)
```

Keep the existing endpoint functions unchanged.

- [ ] **Step 4: Update existing admin config success tests to use real admin token**

Replace `backend/tests/api/test_admin_config.py` with:

```python
"""Tests for Admin Config API。"""

from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import admin_headers, auth_override_scope, ensure_admin_user


class TestListSkills:
    def test_returns_skill_list(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/skills", headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["items"]
        metadata = data["items"][0]["metadata"]
        assert "permission_level" in metadata
        assert "risk_level" in metadata
        assert "metadata_incomplete" in metadata


class TestListPrompts:
    def test_returns_prompt_list(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/prompts", headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetConfig:
    def test_config_masks_api_key(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()
        key = data["ai"]["api_key"]
        assert "***" in key

    def test_config_returns_monthly_and_weekly_quota(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_quota"]["monthly_limit"] == 3000000
        assert data["token_quota"]["weekly_limit"] == 750000
        assert data["token_quota"]["over_quota_action"] == "reject"
        assert "daily_limit" not in data["token_quota"]


class TestClearCache:
    def test_clear_cache(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).post("/admin/cache/clear", headers=admin_headers())
        assert resp.status_code == 200
        assert "cleared" in resp.json()


class TestReloadPrompts:
    def test_reload(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).post("/admin/prompts/reload", headers=admin_headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py tests/api/test_admin_config.py -v
```

Expected: PASS for admin config 401/403/200 behavior and existing success assertions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/admin_config.py backend/tests/api/test_admin_auth_classification.py backend/tests/api/test_admin_config.py
git commit -m "fix: require admin auth for config APIs"
```

---

### Task 3: Admin Trace Router 管理员鉴权

**Files:**
- Modify: `backend/app/api/admin_trace.py`
- Modify: `backend/tests/api/test_admin_trace.py`
- Modify: `backend/tests/api/test_admin_auth_classification.py`

- [ ] **Step 1: Extend behavior tests for trace endpoints**

Append these constants and tests to `backend/tests/api/test_admin_auth_classification.py` below `ADMIN_CONFIG_REQUESTS`:

```python
ADMIN_TRACE_REQUESTS: list[AdminRequest] = [
    ("GET", "/admin/traces?limit=10", lambda _method: {}),
    ("GET", "/admin/traces/missing-request/timeline", lambda _method: {}),
    ("GET", "/admin/traces/missing-request/nodes/1", lambda _method: {}),
    ("DELETE", "/admin/traces?before=2026-05-20", lambda _method: {}),
]
```

Append these parametrized tests to the same file:

```python
@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_TRACE_REQUESTS)
def test_admin_trace_endpoints_reject_anonymous(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """匿名访问 trace 管理接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).request(method, path, **kwargs_factory(method))

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_TRACE_REQUESTS)
def test_admin_trace_endpoints_reject_regular_user(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """普通用户访问 trace 管理接口返回 403。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=regular_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_ADMIN_REQUIRED"
```

- [ ] **Step 2: Run behavior tests to verify failures**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py -v
```

Expected: trace anonymous and regular-user cases FAIL with non-auth responses because `admin_trace.router` has no admin dependency.

- [ ] **Step 3: Add router-level admin dependency**

Modify `backend/app/api/admin_trace.py` imports and router:

```python
"""Admin Trace 查询 API — 链路查询、Gantt 时间线、清理。"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.trace import TraceRecord

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin-trace"],
    dependencies=[Depends(require_admin)],
)
```

Keep the existing models, helpers and endpoint functions unchanged.

- [ ] **Step 4: Update existing trace success tests to use admin token and scoped overrides**

Replace `backend/tests/api/test_admin_trace.py` with:

```python
"""Tests for Admin Trace API。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from tests.api.auth_helpers import admin_headers, auth_override_scope, ensure_admin_user


def _mock_db():
    """创建 mock 数据库会话。"""
    return MagicMock()


@contextmanager
def _db_override(mock_db) -> Iterator[None]:
    """临时替换数据库依赖并在退出时恢复。"""
    original_overrides = dict(app.dependency_overrides)

    def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


class TestGetTraces:
    def test_list_traces(self, db_session) -> None:
        ensure_admin_user(db_session)
        mock_db = _mock_db()
        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get("/admin/traces?limit=10", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetTimeline:
    def test_timeline_returns_rounds(self, db_session) -> None:
        ensure_admin_user(db_session)
        mock_record = MagicMock()
        mock_record.request_id = "abc12345"
        mock_record.round_index = 0
        mock_record.node_type = "llm_call"
        mock_record.node_name = "qwen"
        mock_record.duration_ms = 100
        mock_record.status = "success"
        mock_record.token_usage = '{"total_tokens": 150}'
        mock_record.start_time = "2026-05-26T10:00:00"
        mock_record.end_time = "2026-05-26T10:00:00"
        mock_record.error_message = None
        mock_record.input_data = None
        mock_record.output_data = None

        mock_db = _mock_db()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_record
        ]

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get(
                "/admin/traces/abc12345/timeline",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "request_id" in data
        assert "rounds" in data

    def test_timeline_serializes_trace_json_and_datetime(self, db_session) -> None:
        ensure_admin_user(db_session)
        mock_record = MagicMock()
        mock_record.request_id = "abc12345"
        mock_record.round_index = 0
        mock_record.node_type = "prompt_render"
        mock_record.node_name = "context_builder"
        mock_record.duration_ms = 42
        mock_record.status = "success"
        mock_record.token_usage = {"total_tokens": 150}
        mock_record.start_time = datetime(2026, 6, 4, 14, 3, 22)
        mock_record.end_time = datetime(2026, 6, 4, 14, 3, 23)
        mock_record.error_message = None
        mock_record.input_data = {"block_count": 6}
        mock_record.output_data = {"blocks": [{"key": "farm"}]}

        mock_db = _mock_db()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_record
        ]

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get(
                "/admin/traces/abc12345/timeline",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        node = resp.json()["rounds"][0]["nodes"][0]
        assert node["start_time"] == "2026-06-04T14:03:22"
        assert node["input_data"] == {"block_count": 6}
        assert node["output_data"] == {"blocks": [{"key": "farm"}]}


class TestDeleteTraces:
    def test_delete_before_date(self, db_session) -> None:
        ensure_admin_user(db_session)
        mock_db = _mock_db()
        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).delete(
                "/admin/traces?before=2026-05-20",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py tests/api/test_admin_trace.py -v
```

Expected: PASS for trace 401/403 behavior and existing trace success tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/admin_trace.py backend/tests/api/test_admin_auth_classification.py backend/tests/api/test_admin_trace.py
git commit -m "fix: require admin auth for trace APIs"
```

---

### Task 4: Guardrails Log Router 管理员鉴权

**Files:**
- Modify: `backend/app/api/admin.py`
- Modify: `backend/tests/api/test_admin_auth_classification.py`

- [ ] **Step 1: Add failing behavior tests for guardrails log endpoint**

Append this constant to `backend/tests/api/test_admin_auth_classification.py`:

```python
ADMIN_GUARDRAILS_REQUESTS: list[AdminRequest] = [
    ("GET", "/admin/guardrails-logs", lambda _method: {}),
]
```

Append these tests to the same file:

```python
@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_GUARDRAILS_REQUESTS)
def test_admin_guardrails_endpoints_reject_anonymous(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """匿名访问 guardrails 管理接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).request(method, path, **kwargs_factory(method))

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_GUARDRAILS_REQUESTS)
def test_admin_guardrails_endpoints_reject_regular_user(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """普通用户访问 guardrails 管理接口返回 403。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=regular_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_ADMIN_REQUIRED"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_GUARDRAILS_REQUESTS)
def test_admin_guardrails_endpoints_allow_admin(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """管理员访问 guardrails 管理接口返回业务结果。"""
    ensure_admin_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=admin_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 200
```

- [ ] **Step 2: Run behavior tests to verify failures**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py -v
```

Expected: guardrails anonymous and regular-user cases FAIL with `200` instead of `401`/`403`。

- [ ] **Step 3: Add router-level admin dependency**

Modify `backend/app/api/admin.py`:

```python
"""Admin API — 运维接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.guardrails_log import GuardrailsLog

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
```

Keep `list_guardrails_logs()` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py -v
```

Expected: PASS for all admin config, trace and guardrails auth behavior tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin.py backend/tests/api/test_admin_auth_classification.py
git commit -m "fix: require admin auth for guardrails logs"
```

---

### Task 5: 全量路由鉴权分类审计传感器

**Files:**
- Create: `backend/tests/api/test_route_auth_classification.py`

- [ ] **Step 1: Write failing route classification audit**

Create `backend/tests/api/test_route_auth_classification.py`:

```python
"""全量 API 路由鉴权分类审计。"""

from collections.abc import Iterable

from fastapi.routing import APIRoute

from app.api.deps import get_current_farm, get_current_user, require_admin
from app.main import app


PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("GET", "/api/app/version"),
    ("GET", "/weather/forecast"),
    ("GET", "/planting/operation-types"),
}

IGNORED_ROUTES: set[str] = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

PROTECTION_DEPENDENCIES = {
    get_current_user,
    get_current_farm,
    require_admin,
}


def test_all_http_routes_have_auth_classification():
    """每个业务 HTTP 路由都必须公开白名单或受鉴权依赖保护。"""
    unclassified: list[str] = []

    for route in _api_routes():
        for method in _route_methods(route):
            route_key = (method, route.path)
            if route.path in IGNORED_ROUTES or route_key in PUBLIC_ROUTES:
                continue
            if not _route_has_protection(route):
                unclassified.append(f"{method} {route.path}")

    assert unclassified == [], (
        "发现未归类或未受保护的 API 路由：\n"
        + "\n".join(sorted(unclassified))
    )


def test_public_routes_are_explicit_and_limited():
    """公开白名单只能包含真实存在的路由。"""
    registered = {
        (method, route.path)
        for route in _api_routes()
        for method in _route_methods(route)
        if route.path not in IGNORED_ROUTES
    }

    missing = sorted(PUBLIC_ROUTES - registered)

    assert missing == []


def _api_routes() -> Iterable[APIRoute]:
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route


def _route_methods(route: APIRoute) -> set[str]:
    return {method for method in route.methods if method not in {"HEAD", "OPTIONS"}}


def _route_has_protection(route: APIRoute) -> bool:
    return any(call in PROTECTION_DEPENDENCIES for call in _dependency_calls(route))


def _dependency_calls(route: APIRoute) -> set[object]:
    calls: set[object] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dependency = stack.pop()
        calls.add(dependency.call)
        stack.extend(dependency.dependencies)
    return calls
```

- [ ] **Step 2: Run audit to expose remaining unclassified routes**

Run:

```bash
cd backend && poetry run pytest tests/api/test_route_auth_classification.py -v
```

Expected: FAIL if any route is neither public nor protected. The failure message lists entries such as `GET /...` one per line.

- [ ] **Step 3: Classify failures by existing dependency pattern**

For each failure, inspect the corresponding route file and apply exactly one of these actions:

```text
公开接口：只 add to PUBLIC_ROUTES when response contains no private farm/user/admin data and no management mutation.
登录用户接口：route function or router depends on get_current_user.
农场资源接口：route function or router depends on get_current_farm.
管理员接口：route function or router depends on require_admin.
```

If the failure list contains only known public endpoints from the OpenSpec whitelist, update `PUBLIC_ROUTES` with the exact `(method, path)` tuple from the failure output. If the failure list contains business data endpoints, add a separate implementation task before continuing because this change would exceed the admin hardening surface.

- [ ] **Step 4: Run audit until it passes**

Run:

```bash
cd backend && poetry run pytest tests/api/test_route_auth_classification.py -v
```

Expected: PASS with both audit tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/api/test_route_auth_classification.py
git commit -m "test: add route auth classification audit"
```

---

### Task 6: 公开接口匿名行为回归

**Files:**
- Modify: `backend/tests/api/test_route_auth_classification.py`

- [ ] **Step 1: Add public route anonymous smoke tests**

Append this code to `backend/tests/api/test_route_auth_classification.py`:

```python
from fastapi.testclient import TestClient


PUBLIC_ROUTE_SMOKE_REQUESTS: list[tuple[str, str, dict, set[int]]] = [
    ("GET", "/health", {}, {200}),
    (
        "POST",
        "/auth/login",
        {"json": {"phone": "18899990000", "password": "wrong-password"}},
        {401, 422},
    ),
    (
        "POST",
        "/auth/register",
        {
            "json": {
                "phone": "18899990000",
                "password": "password123",
                "nickname": "公开注册用户",
            }
        },
        {200, 201, 400, 422},
    ),
    ("GET", "/api/app/version", {}, {200}),
    ("GET", "/weather/forecast?city=上海", {}, {200, 502}),
    ("GET", "/planting/operation-types", {}, {200}),
]


def test_public_whitelist_routes_do_not_require_token():
    """公开白名单接口匿名请求不返回认证错误。"""
    client = TestClient(app)

    for method, path, kwargs, allowed_statuses in PUBLIC_ROUTE_SMOKE_REQUESTS:
        resp = client.request(method, path, **kwargs)
        assert resp.status_code in allowed_statuses, f"{method} {path}: {resp.text}"
        if resp.status_code == 401:
            detail = resp.json().get("detail", {})
            assert detail.get("code") != "AUTH_MISSING_TOKEN"
```

- [ ] **Step 2: Run public route smoke tests**

Run:

```bash
cd backend && poetry run pytest tests/api/test_route_auth_classification.py::test_public_whitelist_routes_do_not_require_token -v
```

Expected: PASS. A `401` is only allowed for invalid login credentials, not for `AUTH_MISSING_TOKEN`; the assertion catches accidental login requirement.

- [ ] **Step 3: Run full route classification tests**

Run:

```bash
cd backend && poetry run pytest tests/api/test_route_auth_classification.py -v
```

Expected: PASS for route audit and public whitelist smoke tests.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/api/test_route_auth_classification.py
git commit -m "test: verify public route whitelist behavior"
```

---

### Task 7: Admin 现有保护与前端兼容检查

**Files:**
- Read: `backend/app/api/admin_stats.py`
- Read: `backend/app/api/admin_users.py`
- Read: `admin-web/src/api/client.ts`
- Read: `admin-web/src/stores/authStore.ts`
- Modify: `openspec/changes/harden-api-auth-classification/tasks.md`

- [ ] **Step 1: Verify existing admin routers still use require_admin**

Run:

```bash
cd /Users/ljn/Documents/demo/explore && rg -n "require_admin" backend/app/api/admin_stats.py backend/app/api/admin_users.py
```

Expected output includes endpoint-level `Depends(require_admin)` lines in both files.

- [ ] **Step 2: Verify admin-web still injects Bearer token and handles 401**

Run:

```bash
cd /Users/ljn/Documents/demo/explore && rg -n "Authorization|Bearer|clearToken|/login|status === 401" admin-web/src/api/client.ts admin-web/src/stores/authStore.ts
```

Expected output includes:

```text
admin-web/src/api/client.ts: config.headers.Authorization = `Bearer ${token}`;
admin-web/src/api/client.ts: if (status === 401) {
admin-web/src/api/client.ts: authStore.clearToken();
admin-web/src/api/client.ts: window.location.href = "/login";
```

- [ ] **Step 3: Update OpenSpec task checkboxes for completed non-code checks**

Modify `openspec/changes/harden-api-auth-classification/tasks.md` so these lines are checked after the command output matches expectations:

```markdown
- [x] 1.4 确认现有 `admin_stats.py` 和 `admin_users.py` 继续使用管理员鉴权
- [x] 5.1 确认 admin-web 统一 API client 对 `/admin/*` 请求注入 Bearer token
- [x] 5.2 确认未登录或 token 过期时 admin-web 能处理 401 并回到登录态
```

- [ ] **Step 4: Commit**

```bash
git add openspec/changes/harden-api-auth-classification/tasks.md
git commit -m "docs: record auth compatibility checks"
```

---

### Task 8: 对象级授权抽查

**Files:**
- Read: `backend/app/api/cost.py`
- Read: `backend/app/api/crop.py`
- Read: `backend/app/api/cycle.py`
- Read: `backend/app/api/debt.py`
- Read: `backend/app/api/log.py`
- Read: `backend/app/api/planting.py`
- Read: `backend/app/api/agent.py`
- Read: `backend/app/simulation/routes.py`
- Modify: `openspec/changes/harden-api-auth-classification/tasks.md`

- [ ] **Step 1: Locate path-id routes and farm dependency usage**

Run:

```bash
cd /Users/ljn/Documents/demo/explore && rg -n "@router\\.(get|post|put|patch|delete)\\(.*\\{.*id|Depends\\(get_current_farm\\)|verify_resource_owner" backend/app/api backend/app/simulation/routes.py
```

Expected: path-id business routes either depend on `get_current_farm` directly or call services with `farm.id`/`current_farm.id`.

- [ ] **Step 2: Inspect operation-types public endpoint**

Run:

```bash
cd /Users/ljn/Documents/demo/explore && rg -n "operation-types|OPERATION|作业类型|get_current_farm" backend/app/api/planting.py
```

Expected: `/planting/operation-types` returns fixed operation type data and does not read user private records.

- [ ] **Step 3: Record audit outcome**

If Step 1 finds no missing farm scope and Step 2 confirms fixed public data, modify `openspec/changes/harden-api-auth-classification/tasks.md`:

```markdown
- [x] 4.1 抽查含路径 ID 的农场资源接口，确认服务层查询带当前 `farm.id`
- [x] 4.3 确认 `/planting/operation-types` 仅返回内置类型且保留公开白名单
```

If Step 1 finds a route that reads or mutates farm resources without `get_current_farm`, stop this plan and create a separate OpenSpec task for that exact route because object-level authorization repair can alter business behavior.

- [ ] **Step 4: Commit**

```bash
git add openspec/changes/harden-api-auth-classification/tasks.md
git commit -m "docs: record object authorization audit"
```

---

### Task 9: Final Verification and OpenSpec Status

**Files:**
- Modify: `openspec/changes/harden-api-auth-classification/tasks.md`

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_auth_classification.py tests/api/test_admin_config.py tests/api/test_admin_trace.py tests/api/test_route_auth_classification.py tests/api/test_admin_users.py -v
```

Expected: PASS.

- [ ] **Step 2: Run auth dependency tests**

Run:

```bash
cd backend && poetry run pytest tests/test_deps.py tests/test_auth_api.py -v
```

Expected: PASS.

- [ ] **Step 3: Run lint and formatting check**

Run:

```bash
cd backend && poetry run ruff check . && poetry run ruff format . --check
```

Expected: PASS with no lint or format changes required.

- [ ] **Step 4: Run harness checks**

Run:

```bash
cd /Users/ljn/Documents/demo/explore && bash scripts/harness-check.sh
```

Expected: PASS or documented pre-existing failures unrelated to this change. If failures are caused by files modified in this plan, fix them before continuing.

- [ ] **Step 5: Run OpenSpec validation**

Run:

```bash
cd /Users/ljn/Documents/demo/explore && openspec validate harden-api-auth-classification --strict
```

Expected: PASS.

- [ ] **Step 6: Mark OpenSpec implementation tasks complete**

Modify `openspec/changes/harden-api-auth-classification/tasks.md` and check off completed tasks:

```markdown
- [x] 1.1 在 `admin_config.py` 的 router 上添加 `require_admin` 管理员鉴权
- [x] 1.2 在 `admin_trace.py` 的 router 上添加 `require_admin` 管理员鉴权
- [x] 1.3 在 `admin.py` 的 router 上添加 `require_admin` 管理员鉴权
- [x] 2.1 更新 admin config API 测试：匿名访问返回 401，普通用户返回 403，管理员返回 200
- [x] 2.2 更新 admin trace API 测试：匿名访问返回 401，普通用户返回 403，管理员返回 200
- [x] 2.3 新增 guardrails log API 鉴权测试：匿名访问返回 401，普通用户返回 403，管理员返回 200
- [x] 2.4 确认公开白名单接口匿名访问行为不变
- [x] 3.1 新增全量 API 路由鉴权分类测试，扫描 FastAPI 实际注册路由
- [x] 3.2 在审计测试中维护公开接口白名单，并排除 OpenAPI/docs 内置路由
- [x] 3.3 审计测试应识别 `get_current_user`、`get_current_farm`、`require_admin` 及 router 级依赖
- [x] 3.4 审计失败时输出未归类路由的方法和路径
- [x] 6.1 运行 `ruff check . && ruff format .`
- [x] 6.2 运行后端相关 API 测试
- [x] 6.3 运行 `bash scripts/harness-check.sh`
- [x] 6.4 运行 OpenSpec 状态或校验命令，确认 change apply-ready
```

- [ ] **Step 7: Commit final task status**

```bash
git add openspec/changes/harden-api-auth-classification/tasks.md
git commit -m "docs: complete auth classification tasks"
```

---

## Self-Review

**Spec coverage:**
- `api-auth-classification`: Tasks 1-6 cover default route classification, public whitelist, Bearer token 401 code, admin protection and audit failure output.
- `admin-user-api`: Tasks 2-4 cover anonymous 401, regular user 403 and admin 200 for all newly exposed admin surfaces; Task 7 confirms existing admin users/stats protection.
- `trace-monitor-ui`: Task 3 covers `/admin/traces*` unauthorized behavior and admin success tests for list, timeline and delete.
- `app-auth-integration`: Task 7 confirms admin-web Bearer token injection and 401 login redirect; Task 6 confirms public interfaces can remain anonymous.
- Object-level authorization: Task 8 performs required audit and explicitly stops for a separate route-specific change if a missing farm scope is found.

**Placeholder scan:**
- The plan contains no `TBD`, `TODO`, `implement later`, or undefined function names in code snippets.
- Every code-changing step includes concrete code blocks or exact commands and expected results.

**Type consistency:**
- `auth_override_scope()`, `ensure_regular_user()`, `ensure_admin_user()`, `regular_headers()` and `admin_headers()` are defined in Task 1 and reused with the same signatures.
- Route audit helper names `_api_routes()`, `_route_methods()`, `_route_has_protection()` and `_dependency_calls()` are defined in Task 5 before reuse.
- Admin request tuple type is consistently `tuple[str, str, Callable[[str], dict]]`.
