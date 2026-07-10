"""三层权限依赖链测试。"""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.dependencies import get_current_user, require_admin
from app.modules.farm.dependencies import get_current_farm, verify_resource_owner
from app.modules.auth.tokens import create_access_token
from app.models.farm import Farm
from app.models.user import User


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
