"""三层权限依赖链测试。"""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_farm,
    get_current_user,
    get_db,
    verify_resource_owner,
)
from app.core.security import create_access_token
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


def test_get_current_user_invalid_token():
    """无效 token 返回 401。"""
    app = FastAPI()

    @app.get("/test")
    def endpoint(u=Depends(get_current_user)):
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/test", headers={"Authorization": "Bearer invalid"})
    assert resp.status_code == 401


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
