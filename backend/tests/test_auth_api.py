"""Auth API 端到端测试。"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.models.agent_record import AgentRecord
from app.models.farm import Farm
from app.main import app
from app.models.user import User
from app.models.user_setting import UserSetting


@pytest.fixture
def client():
    """创建测试客户端，使用完整应用（清除 get_current_user 覆盖，测试真实 JWT 流程）。"""
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestAuthRegister:
    """测试注册接口。"""

    def test_register_success(self, client, clean_db):
        """POST /auth/register 注册成功。"""
        resp = client.post(
            "/auth/register",
            json={
                "phone": "13800138000",
                "password": "password123",
                "nickname": "张三",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["phone"] == "13800138000"
        assert data["user"]["nickname"] == "张三"

    def test_register_invalid_phone(self, client, clean_db):
        """手机号格式错误返回 422。"""
        resp = client.post(
            "/auth/register",
            json={"phone": "123", "password": "password123"},
        )

        assert resp.status_code == 422

    def test_register_short_password(self, client, clean_db):
        """密码少于 8 位返回 422。"""
        resp = client.post(
            "/auth/register",
            json={"phone": "13800138000", "password": "1234567"},
        )

        assert resp.status_code == 422

    def test_register_duplicate_phone(self, client, clean_db):
        """重复注册同一手机号返回 400。"""
        client.post(
            "/auth/register",
            json={"phone": "13800138000", "password": "password123"},
        )
        resp = client.post(
            "/auth/register",
            json={"phone": "13800138000", "password": "password123"},
        )

        assert resp.status_code == 400


class TestAuthLogin:
    """测试登录接口。"""

    def test_login_success(self, client, clean_db):
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

    def test_login_wrong_password(self, client, clean_db):
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

    def test_login_nonexistent_user(self, client, clean_db):
        """登录不存在的用户返回 401。"""
        resp = client.post(
            "/auth/login",
            json={"phone": "13800999999", "password": "password123"},
        )

        assert resp.status_code == 401


class TestAuthMe:
    """测试 /auth/me 接口。"""

    def test_get_me_with_token(self, client, clean_db):
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
        assert resp.json()["farm"]["name"] == "农友的农场"
        assert resp.json()["farm"]["location"] is None

    def test_get_me_returns_farm_location(self, client, clean_db):
        """GET /auth/me 返回当前用户默认农场经营地区。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138013", "password": "password123"},
        )
        token = reg.json()["access_token"]
        from app.api.deps import get_db

        db = next(app.dependency_overrides[get_db]())
        try:
            user = db.query(User).filter(User.phone == "13800138013").first()
            farm = db.query(Farm).filter(Farm.user_id == user.id).first()
            farm.location = "睢宁县"
            db.commit()
        finally:
            db.close()

        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["farm"]["location"] == "睢宁县"

    def test_get_me_backfills_farm_location_from_user_settings(self, client, clean_db):
        """默认农场地区为空时，从旧 user_settings 城市回填。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138014", "password": "password123"},
        )
        token = reg.json()["access_token"]
        from app.api.deps import get_db

        db = next(app.dependency_overrides[get_db]())
        try:
            user = db.query(User).filter(User.phone == "13800138014").first()
            db.add(UserSetting(user_id=user.id, default_city="寿光"))
            db.commit()
        finally:
            db.close()

        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["farm"]["location"] == "寿光"

    def test_get_me_without_token(self, client, clean_db):
        """无 token 访问 /auth/me 返回 401。"""
        resp = client.get("/auth/me")

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"

    def test_get_me_with_expired_token(self, client, clean_db):
        """过期 token 访问 /auth/me 返回稳定错误码。"""
        token = create_access_token(user_id="test-user-001", expires_minutes=-1)
        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "AUTH_EXPIRED_TOKEN"

    def test_get_me_disabled_user(self, client, clean_db):
        """禁用用户访问 /auth/me 返回稳定错误码。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138005", "password": "password123"},
        )
        token = reg.json()["access_token"]
        from app.api.deps import get_db

        db = next(app.dependency_overrides[get_db]())
        try:
            user = db.query(User).filter(User.phone == "13800138005").first()
            user.status = "disabled"
            db.commit()
        finally:
            db.close()

        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "AUTH_USER_DISABLED"


class TestAuthUpdateMe:
    """测试更新用户信息接口。"""

    def test_update_nickname(self, client, clean_db):
        """PUT /auth/me 更新昵称成功。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138004", "password": "password123"},
        )
        token = reg.json()["access_token"]
        resp = client.put(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"nickname": "新昵称"},
        )

        assert resp.status_code == 200
        assert resp.json()["nickname"] == "新昵称"

    def test_update_me_without_token(self, client, clean_db):
        """无 token 更新 /auth/me 返回 401。"""
        resp = client.put(
            "/auth/me",
            json={"nickname": "新昵称"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


class TestAuthFarmLocation:
    """测试当前用户默认农场经营地区更新。"""

    def test_update_own_default_farm_location(self, client, clean_db):
        """PUT /auth/me/farm-location 更新当前用户默认农场地区。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138015", "password": "password123"},
        )
        token = reg.json()["access_token"]

        resp = client.put(
            "/auth/me/farm-location",
            headers={"Authorization": f"Bearer {token}"},
            json={"location": "邳州市", "lat": 34.3142, "lon": 117.9586},
        )

        assert resp.status_code == 200
        assert resp.json()["farm"]["location"] == "邳州市"

    def test_update_farm_location_syncs_user_default_city(self, client, clean_db):
        """更新经营地区时同步旧用户设置默认城市，确保相关上下文读到新城市。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138018", "password": "password123"},
        )
        token = reg.json()["access_token"]
        from app.api.deps import get_db

        db = next(app.dependency_overrides[get_db]())
        try:
            user = db.query(User).filter(User.phone == "13800138018").first()
            db.add(UserSetting(user_id=user.id, default_city="睢宁县"))
            db.commit()
        finally:
            db.close()

        resp = client.put(
            "/auth/me/farm-location",
            headers={"Authorization": f"Bearer {token}"},
            json={"location": "邳州市"},
        )

        assert resp.status_code == 200
        db = next(app.dependency_overrides[get_db]())
        try:
            user = db.query(User).filter(User.phone == "13800138018").first()
            farm = db.query(Farm).filter(Farm.user_id == user.id).first()
            setting = (
                db.query(UserSetting).filter(UserSetting.user_id == user.id).first()
            )
            assert farm.location == "邳州市"
            assert setting.default_city == "邳州市"
            assert setting.default_lat == 34.3142
            assert setting.default_lon == 117.9586
        finally:
            db.close()

    def test_update_farm_location_deletes_daily_advice_cache(self, client, clean_db):
        """更新经营地区后删除该农场每日建议缓存。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138017", "password": "password123"},
        )
        token = reg.json()["access_token"]
        from app.api.deps import get_db

        db = next(app.dependency_overrides[get_db]())
        try:
            user = db.query(User).filter(User.phone == "13800138017").first()
            farm = db.query(Farm).filter(Farm.user_id == user.id).first()
            db.add(
                AgentRecord(
                    farm_id=farm.id,
                    record_type="daily",
                    content='{"items":[]}',
                )
            )
            db.commit()
            farm_id = farm.id
        finally:
            db.close()

        resp = client.put(
            "/auth/me/farm-location",
            headers={"Authorization": f"Bearer {token}"},
            json={"location": "邳州市"},
        )

        assert resp.status_code == 200
        db = next(app.dependency_overrides[get_db]())
        try:
            remaining = (
                db.query(AgentRecord)
                .filter(
                    AgentRecord.farm_id == farm_id,
                    AgentRecord.record_type == "daily",
                )
                .count()
            )
        finally:
            db.close()
        assert remaining == 0

    def test_update_other_farm_location_returns_403_code(self, client, clean_db):
        """传入其他 farm_id 时返回 403 结构化错误码。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138016", "password": "password123"},
        )
        token = reg.json()["access_token"]
        from app.api.deps import get_db

        db = next(app.dependency_overrides[get_db]())
        try:
            other = User(
                id="other-farm-location-user",
                phone="13800138999",
                password_hash="hash",
                nickname="别人",
                status="active",
            )
            db.add(other)
            db.flush()
            other_farm = Farm(name="别人农场", user_id=other.id, location="南京")
            db.add(other_farm)
            db.commit()
            db.refresh(other_farm)
            other_farm_id = other_farm.id
        finally:
            db.close()

        resp = client.put(
            "/auth/me/farm-location",
            headers={"Authorization": f"Bearer {token}"},
            json={"farm_id": other_farm_id, "location": "邳州市"},
        )

        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "FARM_LOCATION_FORBIDDEN"
