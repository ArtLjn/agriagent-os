from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agent.prompt_registry import get_registry
from app.main import app

# 确保 prompt 模板在测试中已加载
_registry = get_registry()
if not _registry.list_versions("crop_template_parse"):
    _registry.reload(Path(__file__).parent.parent / "prompts")

client = TestClient(app)


def test_create_crop_template():
    payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 30,
                "order_index": 0,
                "key_tasks": "温湿度管理",
            },
            {
                "name": "定植期",
                "duration_days": 1,
                "order_index": 1,
                "key_tasks": "浇定根水",
            },
        ],
    }
    response = client.post("/crops/templates", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "西瓜"
    assert len(data["stages"]) == 2
    assert data["stages"][0]["name"] == "育苗期"


def test_list_crop_templates():
    payload = {
        "name": "豆角",
        "variety": "长豆角",
        "stages": [
            {
                "name": "播种期",
                "duration_days": 7,
                "order_index": 0,
                "key_tasks": "浇水保湿",
            },
        ],
    }
    client.post("/crops/templates", json=payload)

    response = client.get("/crops/templates")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "豆角"


def test_get_template_not_found():
    response = client.get("/crops/templates/99999")
    assert response.status_code == 404


def test_update_crop_template():
    """测试更新作物模板。"""
    create_payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 30,
                "order_index": 0,
                "key_tasks": "温湿度管理",
            },
        ],
    }
    create_resp = client.post("/crops/templates", json=create_payload)
    template_id = create_resp.json()["id"]

    update_payload = {
        "name": "改良西瓜",
        "variety": "麒麟",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 25,
                "order_index": 0,
                "key_tasks": "改良温湿度管理",
            },
            {
                "name": "定植期",
                "duration_days": 1,
                "order_index": 1,
                "key_tasks": "浇定根水",
            },
        ],
    }
    response = client.put(f"/crops/templates/{template_id}", json=update_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "改良西瓜"
    assert data["variety"] == "麒麟"
    assert len(data["stages"]) == 2
    assert data["stages"][0]["duration_days"] == 25


def test_update_template_not_found():
    """测试更新不存在的模板返回 404。"""
    payload = {
        "name": "不存在",
        "variety": "无",
        "stages": [],
    }
    response = client.put("/crops/templates/99999", json=payload)
    assert response.status_code == 404


def test_delete_crop_template():
    """测试删除作物模板。"""
    create_payload = {
        "name": "临时作物",
        "variety": "测试",
        "stages": [],
    }
    create_resp = client.post("/crops/templates", json=create_payload)
    template_id = create_resp.json()["id"]

    response = client.delete(f"/crops/templates/{template_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "删除成功"

    get_resp = client.get(f"/crops/templates/{template_id}")
    assert get_resp.status_code == 404


def test_delete_template_not_found():
    """测试删除不存在的模板返回 404。"""
    response = client.delete("/crops/templates/99999")
    assert response.status_code == 404


class TestParseCropTemplate:
    """测试作物模板解析端点。"""

    @patch("app.api.crop.invoke_advisor")
    def test_parse_normal(self, mock_invoke):
        """正常解析：返回结构化作物模板数据。"""
        mock_invoke.return_value = (
            '{"name": "西瓜", "variety": null, '
            '"stages": [{"name": "育苗期", "duration_days": 30, '
            '"order_index": 0, "key_tasks": "温湿度管理"}]}'
        )

        response = client.post("/crops/templates/parse", json={"description": "我要种西瓜"})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "西瓜"
        assert data["variety"] is None
        assert len(data["stages"]) == 1
        assert data["stages"][0]["name"] == "育苗期"
        mock_invoke.assert_called_once()

    @patch("app.api.crop.invoke_advisor")
    def test_parse_with_variety(self, mock_invoke):
        """含品种解析：正确提取品种信息。"""
        mock_invoke.return_value = (
            '{"name": "西瓜", "variety": "8424", '
            '"stages": [{"name": "育苗期", "duration_days": 30, '
            '"order_index": 0, "key_tasks": "温湿度管理"}, '
            '{"name": "定植期", "duration_days": 1, '
            '"order_index": 1, "key_tasks": "浇定根水"}]}'
        )

        response = client.post(
            "/crops/templates/parse", json={"description": "我要种8424西瓜"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "西瓜"
        assert data["variety"] == "8424"
        assert len(data["stages"]) == 2

    @patch("app.api.crop.invoke_advisor")
    def test_parse_invalid_json(self, mock_invoke):
        """解析失败回退：AI 返回无效 JSON 时返回 422。"""
        mock_invoke.return_value = "这不是有效的 JSON"

        response = client.post(
            "/crops/templates/parse", json={"description": "随便说点什么"}
        )

        assert response.status_code == 422

    @patch("app.api.crop.invoke_advisor")
    def test_parse_idempotency_cache(self, mock_invoke):
        """幂等键缓存：相同 key 直接返回缓存结果，不重复调用 AI。"""
        mock_invoke.return_value = (
            '{"name": "番茄", "variety": null, '
            '"stages": [{"name": "育苗期", "duration_days": 25, '
            '"order_index": 0, "key_tasks": "保温保湿"}]}'
        )

        idempotency_key = "test-key-abc123"
        headers = {"X-Idempotency-Key": idempotency_key}

        # 第一次请求
        response1 = client.post(
            "/crops/templates/parse",
            json={"description": "种番茄"},
            headers=headers,
        )
        assert response1.status_code == 200
        assert mock_invoke.call_count == 1

        # 第二次请求（相同 key）
        response2 = client.post(
            "/crops/templates/parse",
            json={"description": "种番茄"},
            headers=headers,
        )
        assert response2.status_code == 200
        # 缓存命中，不再调用 AI
        assert mock_invoke.call_count == 1
        assert response2.json() == response1.json()
