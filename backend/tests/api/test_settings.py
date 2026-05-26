"""用户设置 API 测试。"""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestGetSettings:
    """GET /settings 测试组。"""

    def test_returns_default_display_name(self):
        """未设置 display_name 时返回默认值'农友'。"""
        # Arrange: conftest 已播种默认农场，display_name 为 None

        # Act
        response = client.get("/settings")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "农友"

    def test_returns_custom_display_name(self):
        """设置 display_name 后返回自定义值。"""
        # Arrange: 先通过 PUT 设置
        client.put("/settings", json={"display_name": "老李"})

        # Act
        response = client.get("/settings")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "老李"


class TestPutSettings:
    """PUT /settings 测试组。"""

    def test_update_display_name_success(self):
        """正常更新 display_name。"""
        # Arrange
        payload = {"display_name": "王大叔"}

        # Act
        response = client.put("/settings", json=payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "王大叔"

    def test_update_persists_across_requests(self):
        """更新后的值在后续 GET 请求中保持一致。"""
        # Arrange
        client.put("/settings", json={"display_name": "老张"})

        # Act
        response = client.get("/settings")

        # Assert
        assert response.json()["display_name"] == "老张"

    def test_update_overwrites_previous_value(self):
        """多次更新，最后一次生效。"""
        # Arrange
        client.put("/settings", json={"display_name": "老李"})
        client.put("/settings", json={"display_name": "老王"})

        # Act
        response = client.get("/settings")

        # Assert
        assert response.json()["display_name"] == "老王"

    def test_empty_string_rejected(self):
        """空字符串被校验拒绝。"""
        # Arrange
        payload = {"display_name": ""}

        # Act
        response = client.put("/settings", json=payload)

        # Assert
        assert response.status_code == 422

    def test_too_long_display_name_rejected(self):
        """超过 20 字符被校验拒绝。"""
        # Arrange
        payload = {"display_name": "a" * 21}

        # Act
        response = client.put("/settings", json=payload)

        # Assert
        assert response.status_code == 422

    def test_missing_field_uses_default(self):
        """缺少 display_name 字段时使用默认值'农友'。"""
        # Arrange
        payload = {}

        # Act
        response = client.put("/settings", json=payload)

        # Assert
        assert response.status_code == 200
        assert response.json()["display_name"] == "农友"

    def test_boundary_length_20_accepted(self):
        """恰好 20 字符通过校验。"""
        # Arrange
        payload = {"display_name": "a" * 20}

        # Act
        response = client.put("/settings", json=payload)

        # Assert
        assert response.status_code == 200

    def test_boundary_length_1_accepted(self):
        """恰好 1 字符通过校验。"""
        # Arrange
        payload = {"display_name": "李"}

        # Act
        response = client.put("/settings", json=payload)

        # Assert
        assert response.status_code == 200
