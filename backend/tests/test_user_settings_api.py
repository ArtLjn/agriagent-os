"""用户设置 API 测试。"""

from fastapi.testclient import TestClient

from app.models.user_setting import UserSetting


class TestGetSettings:
    """GET /settings 测试。"""

    def test_no_settings_returns_defaults(self, client: TestClient, auth_headers):
        """无设置记录时返回默认值。"""
        resp = client.get("/settings", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "测试用户"
        assert data["default_city"] is None
        assert data["default_lat"] is None
        assert data["default_lon"] is None


class TestUpdateSettings:
    """PUT /settings 测试。"""

    def test_create_city_settings(self, client: TestClient, auth_headers, db_session):
        """首次设置城市，自动创建记录。"""
        resp = client.put(
            "/settings",
            json={
                "default_city": "北京",
                "default_lat": 39.9,
                "default_lon": 116.41,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_city"] == "北京"
        assert data["default_lat"] == 39.9
        assert data["default_lon"] == 116.41

        # 验证数据库
        setting = (
            db_session.query(UserSetting).filter_by(user_id="test-user-001").first()
        )
        assert setting is not None
        assert setting.default_city == "北京"

    def test_partial_update_city_only(self, client: TestClient, auth_headers):
        """只更新城市名，坐标保持原值。"""
        # 先创建
        client.put(
            "/settings",
            json={"default_city": "北京", "default_lat": 39.9, "default_lon": 116.41},
            headers=auth_headers,
        )
        # 部分更新
        resp = client.put(
            "/settings",
            json={"default_city": "杭州"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_city"] == "杭州"
        assert data["default_lat"] == 39.9
        assert data["default_lon"] == 116.41

    def test_update_display_name(self, client: TestClient, auth_headers):
        """更新昵称。"""
        resp = client.put(
            "/settings",
            json={"display_name": "新名字"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "新名字"

    def test_get_after_update(self, client: TestClient, auth_headers):
        """更新后再获取，数据一致。"""
        client.put(
            "/settings",
            json={"default_city": "苏州", "default_lat": 31.3, "default_lon": 120.62},
            headers=auth_headers,
        )
        resp = client.get("/settings", headers=auth_headers)
        data = resp.json()
        assert data["default_city"] == "苏州"
        assert data["default_lat"] == 31.3
