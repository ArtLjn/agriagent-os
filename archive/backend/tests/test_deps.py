"""三层权限依赖链测试。"""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.users.dependencies import (
    get_current_user,
    require_admin,
    require_admin_context,
    require_auth_context,
    require_effective_user_context,
    optional_auth_context,
)
from app.domains.farm.dependencies import get_current_farm, verify_resource_owner
from app.domains.users.tokens import create_access_token
from app.domains.farm.models import Farm
from app.domains.users.models import User


def _create_user_and_farm(
    db: Session, *, role: str = "user", status: str = "active"
) -> tuple[User, Farm]:
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        phone=f"13{uid.replace('-', '')[:9]}",
        password_hash="h",
        nickname="测试",
        role=role,
        status=status,
    )
    db.add(user)
    farm = Farm(name="测试农场", user_id=uid)
    db.add(farm)
    db.commit()
    db.refresh(user)
    db.refresh(farm)
    return user, farm


def _override_db(app: FastAPI, db: Session) -> None:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db


def test_get_current_user_valid_token(db_session):
    """有效 token 返回 User 对象。"""
    user, _ = _create_user_and_farm(db_session)
    token = create_access_token(user_id=user.id)

    app = FastAPI()
    _override_db(app, db_session)

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
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


def test_get_current_user_invalid_token():
    """无效 token 返回 401。"""
    app = FastAPI()

    @app.get("/test")
    def endpoint(u=Depends(get_current_user)):
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": "Bearer invalid"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_INVALID_TOKEN"


def test_get_current_user_expired_token(db_session):
    """过期 token 返回 401 和稳定错误码。"""
    user, _ = _create_user_and_farm(db_session)
    token = create_access_token(user_id=user.id, expires_minutes=-1)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(u=Depends(get_current_user)):
        return {"id": u.id}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_EXPIRED_TOKEN"


def test_get_current_user_disabled_user(db_session):
    """禁用用户返回 401 和稳定错误码。"""
    user, _ = _create_user_and_farm(db_session)
    user.status = "disabled"
    db_session.commit()
    token = create_access_token(user_id=user.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(u=Depends(get_current_user)):
        return {"id": u.id}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_USER_DISABLED"


def test_get_current_farm_success(db_session):
    """有效用户返回关联 Farm。"""
    user, farm = _create_user_and_farm(db_session)
    token = create_access_token(user_id=user.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(f=Depends(get_current_farm)):
        return {"farm_id": f.id}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["farm_id"] == farm.id


def test_verify_resource_owner_mismatch(db_session):
    """资源不属于当前用户返回 403。"""
    _user, farm = _create_user_and_farm(db_session)

    with pytest.raises(Exception) as exc_info:
        verify_resource_owner(resource_farm_id=999, current_farm=farm)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "FARM_RESOURCE_FORBIDDEN"


def test_require_admin_allows_admin():
    """管理员依赖允许 admin 用户。"""
    user = User(id="admin-id", phone="13800138001", password_hash="h", role="admin")
    assert require_admin(user) == user


def test_require_admin_rejects_user():
    """普通用户访问管理员依赖返回 403。"""
    user = User(id="user-id", phone="13800138002", password_hash="h", role="user")

    with pytest.raises(Exception) as exc_info:
        require_admin(user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "AUTH_ADMIN_REQUIRED"


def test_require_auth_context_valid_token(db_session):
    """有效 token 返回统一鉴权上下文。"""
    user, _ = _create_user_and_farm(db_session)
    token = create_access_token(user_id=user.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_auth_context)):
        return {
            "current_user_id": ctx.current_user_id,
            "effective_user_id": ctx.effective_user_id,
            "is_admin": ctx.is_admin,
            "is_simulated": ctx.is_simulated,
        }

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {
        "current_user_id": user.id,
        "effective_user_id": user.id,
        "is_admin": False,
        "is_simulated": False,
    }


def test_require_auth_context_ignores_simulation_parameter(db_session):
    """默认业务上下文不启用模拟能力，模拟参数会被忽略。"""
    user, _ = _create_user_and_farm(db_session)
    target, _ = _create_user_and_farm(db_session)
    token = create_access_token(user_id=user.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_auth_context)):
        return {
            "effective_user_id": ctx.effective_user_id,
            "is_simulated": ctx.is_simulated,
        }

    client = TestClient(app)
    resp = client.get(
        f"/test?simulate_user_id={target.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"effective_user_id": user.id, "is_simulated": False}


def test_require_auth_context_disabled_token_fails(db_session):
    """禁用当前用户统一返回 disabled 错误。"""
    user, _ = _create_user_and_farm(db_session, status="disabled")
    token = create_access_token(user_id=user.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_auth_context)):
        return {"id": ctx.current_user_id}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_USER_DISABLED"


def test_require_admin_context_allows_admin(db_session):
    """管理员上下文允许 admin 用户。"""
    admin, _ = _create_user_and_farm(db_session, role="admin")
    token = create_access_token(user_id=admin.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_admin_context)):
        return {"id": ctx.current_user_id, "is_admin": ctx.is_admin}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"id": admin.id, "is_admin": True}


def test_require_admin_context_rejects_user(db_session):
    """普通用户访问管理员上下文返回 403。"""
    user, _ = _create_user_and_farm(db_session)
    token = create_access_token(user_id=user.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_admin_context)):
        return {"id": ctx.current_user_id}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_ADMIN_REQUIRED"


def test_require_effective_user_context_admin_simulates_active_user(db_session):
    """管理员可通过 query 模拟 active 用户，query 优先于 header。"""
    admin, _ = _create_user_and_farm(db_session, role="admin")
    target, _ = _create_user_and_farm(db_session)
    ignored, _ = _create_user_and_farm(db_session)
    token = create_access_token(user_id=admin.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_effective_user_context)):
        return {
            "current_user_id": ctx.current_user_id,
            "effective_user_id": ctx.effective_user_id,
            "is_admin": ctx.is_admin,
            "is_simulated": ctx.is_simulated,
        }

    client = TestClient(app)
    resp = client.get(
        f"/test?simulate_user_id={target.id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Simulate-User-Id": ignored.id,
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "current_user_id": admin.id,
        "effective_user_id": target.id,
        "is_admin": True,
        "is_simulated": True,
    }


def test_require_effective_user_context_admin_simulates_disabled_user_fails(
    db_session,
):
    """模拟目标用户禁用时返回稳定错误码。"""
    admin, _ = _create_user_and_farm(db_session, role="admin")
    target, _ = _create_user_and_farm(db_session, status="disabled")
    token = create_access_token(user_id=admin.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_effective_user_context)):
        return {"effective_user_id": ctx.effective_user_id}

    client = TestClient(app)
    resp = client.get(
        "/test",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Simulate-User-Id": target.id,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_SIMULATED_USER_DISABLED"


def test_require_effective_user_context_missing_simulated_user_fails(db_session):
    """模拟目标不存在时不破坏当前登录态，返回模拟目标错误。"""
    admin, _ = _create_user_and_farm(db_session, role="admin")
    token = create_access_token(user_id=admin.id)

    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(require_effective_user_context)):
        return {"effective_user_id": ctx.effective_user_id}

    client = TestClient(app)
    resp = client.get(
        "/test?simulate_user_id=missing-user-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "AUTH_SIMULATED_USER_NOT_FOUND"


def test_optional_auth_context_without_token_returns_none(db_session):
    """可选鉴权没有 token 时返回 None。"""
    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(optional_auth_context)):
        return {"authenticated": ctx is not None}

    client = TestClient(app)
    resp = client.get("/test")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False}


def test_optional_auth_context_malformed_header_fails(db_session):
    """可选鉴权遇到坏认证头时仍拒绝，避免匿名降级。"""
    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(optional_auth_context)):
        return {"authenticated": ctx is not None}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": "Basic bad"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


def test_optional_auth_context_invalid_token_fails(db_session):
    """可选鉴权遇到无效 token 时不吞掉错误。"""
    app = FastAPI()
    _override_db(app, db_session)

    @app.get("/test")
    def endpoint(ctx=Depends(optional_auth_context)):
        return {"authenticated": ctx is not None}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": "Bearer invalid"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_INVALID_TOKEN"
