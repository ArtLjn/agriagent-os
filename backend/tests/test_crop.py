from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.agent.prompt_registry import get_registry
from app.main import app
from app.schemas.crop import CropTemplateParseResponse, GrowthStageCreate

# 确保 prompt 模板在测试中已加载
_registry = get_registry()
if not _registry.list_versions("crop_template_parse"):
    _registry.reload(Path(__file__).parent.parent / "prompts")

client = TestClient(app)


def _mock_llm_response(text: str):
    """构造一个模拟 LLM 返回的 response 对象。"""
    mock_resp = AsyncMock()
    mock_resp.content = text
    return mock_resp


def _mock_structured_response(name, variety=None, stages=None):
    """构造一个 with_structured_output 直接返回的 Pydantic model。"""
    if stages is None:
        stages = [
            GrowthStageCreate(
                name="育苗期", duration_days=30, order_index=0, key_tasks="温湿度管理"
            ),
        ]
    return CropTemplateParseResponse(name=name, variety=variety, stages=stages)


def _build_llm_with_structured_output(structured_result):
    """构造一个 LLM mock，with_structured_output 返回可直接 ainvoke 的对象。"""
    mock_llm = MagicMock()
    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    return mock_llm


def _build_llm_fallback(mock_raw_response):
    """构造一个 structured output 失败后 fallback 到普通 ainvoke 的 LLM mock。"""
    mock_llm = MagicMock()

    # with_structured_output 抛异常
    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock(side_effect=RuntimeError("不支持"))
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    # fallback 路径：普通 ainvoke 返回 JSON 文本
    mock_llm.ainvoke = AsyncMock(return_value=mock_raw_response)
    return mock_llm


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


class TestParseCropTemplateStructured:
    """测试作物模板解析端点 — with_structured_output 路径。"""

    @patch("app.api.crop.get_llm")
    def test_structured_output_normal(self, mock_get_llm):
        """structured output 正常路径：直接返回 Pydantic model。"""
        result = _mock_structured_response("西瓜", variety=None)
        mock_llm = _build_llm_with_structured_output(result)
        mock_get_llm.return_value = mock_llm

        response = client.post(
            "/crops/templates/parse", json={"description": "我要种西瓜"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "西瓜"
        assert data["variety"] is None
        assert len(data["stages"]) == 1
        assert data["stages"][0]["name"] == "育苗期"
        # 应走 with_structured_output，不直接调 llm.ainvoke
        mock_llm.with_structured_output.assert_called_once()
        mock_llm.ainvoke.assert_not_called()

    @patch("app.api.crop.get_llm")
    def test_structured_output_with_variety(self, mock_get_llm):
        """structured output 含品种：正确提取品种信息。"""
        result = _mock_structured_response(
            "西瓜",
            variety="8424",
            stages=[
                GrowthStageCreate(
                    name="育苗期",
                    duration_days=30,
                    order_index=0,
                    key_tasks="温湿度管理",
                ),
                GrowthStageCreate(
                    name="定植期",
                    duration_days=1,
                    order_index=1,
                    key_tasks="浇定根水",
                ),
            ],
        )
        mock_llm = _build_llm_with_structured_output(result)
        mock_get_llm.return_value = mock_llm

        response = client.post(
            "/crops/templates/parse", json={"description": "我要种8424西瓜"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "西瓜"
        assert data["variety"] == "8424"
        assert len(data["stages"]) == 2

    @patch("app.api.crop.get_llm")
    def test_structured_output_empty_stages(self, mock_get_llm):
        """structured output 返回空 stages 时应返回 422。"""
        result = _mock_structured_response("未知", variety=None, stages=[])
        mock_llm = _build_llm_with_structured_output(result)
        mock_get_llm.return_value = mock_llm

        response = client.post(
            "/crops/templates/parse", json={"description": "随便说点什么"}
        )

        assert response.status_code == 422


class TestParseCropTemplateFallback:
    """测试作物模板解析端点 — structured output 失败后的 fallback 路径。"""

    @patch("app.api.crop.get_llm")
    def test_fallback_to_safe_parse_json(self, mock_get_llm):
        """with_structured_output 异常时，fallback 到 safe_parse_json。"""
        mock_llm = _build_llm_fallback(
            _mock_llm_response(
                '{"name": "西瓜", "variety": null, '
                '"stages": [{"name": "育苗期", "duration_days": 30, '
                '"order_index": 0, "key_tasks": "温湿度管理"}]}'
            )
        )
        mock_get_llm.return_value = mock_llm

        response = client.post(
            "/crops/templates/parse", json={"description": "我要种西瓜"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "西瓜"
        assert data["variety"] is None
        assert len(data["stages"]) == 1

    @patch("app.api.crop.get_llm")
    def test_fallback_invalid_json(self, mock_get_llm):
        """fallback 路径返回无效 JSON 时应返回 422。"""
        mock_llm = _build_llm_fallback(_mock_llm_response("这不是有效的 JSON"))
        mock_get_llm.return_value = mock_llm

        response = client.post(
            "/crops/templates/parse", json={"description": "随便说点什么"}
        )

        assert response.status_code == 422


class TestParseCropTemplateIdempotency:
    """测试幂等键缓存逻辑（两种路径均适用）。"""

    @patch("app.api.crop.get_llm")
    def test_idempotency_cache_hit(self, mock_get_llm):
        """幂等键缓存：相同 key 直接返回缓存结果，不重复调用 AI。"""
        result = _mock_structured_response("番茄", variety=None)
        mock_llm = _build_llm_with_structured_output(result)
        mock_get_llm.return_value = mock_llm

        idempotency_key = "test-key-abc123"
        headers = {"X-Idempotency-Key": idempotency_key}

        # 第一次请求
        response1 = client.post(
            "/crops/templates/parse",
            json={"description": "种番茄"},
            headers=headers,
        )
        assert response1.status_code == 200

        # 第二次请求（相同 key）
        response2 = client.post(
            "/crops/templates/parse",
            json={"description": "种番茄"},
            headers=headers,
        )
        assert response2.status_code == 200
        assert response2.json() == response1.json()


def test_parse_crop_template_returns_422_on_invalid_data():
    """当 LLM 返回不合法数据时，应返回 422 而非 500。"""
    from unittest.mock import patch
    from app.schemas.crop import CropTemplateParseResponse

    with patch("app.api.crop._parse_crop_with_llm") as mock_parse:
        mock_parse.return_value = CropTemplateParseResponse(
            name="未知作物", variety=None, stages=[]
        )
        response = client.post("/crops/templates/parse", json={"description": "hhhhhh"})

    assert response.status_code == 422
    assert "无法识别作物信息" in response.json()["detail"]
