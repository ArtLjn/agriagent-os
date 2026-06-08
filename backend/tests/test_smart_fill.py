from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.agent.prompt_registry import get_registry
from app.main import app
from app.schemas.cost import CostParseResult

client = TestClient(app)
get_registry().reload(Path(__file__).parent.parent / "prompts")


def _build_llm_with_structured_output(structured_result):
    """构造 structured output 成功的 LLM mock。"""
    mock_llm = MagicMock()
    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    return mock_llm


def test_list_smart_fill_scenarios_exposes_registered_business_scenes():
    response = client.get("/smart-fill/scenarios")

    assert response.status_code == 200
    data = response.json()
    scene_keys = {item["key"] for item in data["items"]}
    assert {"ledger.record", "crop.template", "crop.cycle"} <= scene_keys
    ledger = next(item for item in data["items"] if item["key"] == "ledger.record")
    assert ledger["legacy_endpoint"] == "/costs/parse"
    assert ledger["enabled"] is True


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_ledger_record_returns_unified_draft(mock_get_llm):
    result = CostParseResult(
        record_type="cost",
        category="肥料",
        amount="128.50",
        record_date="2026-06-08",
        note="买复合肥",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "ledger.record",
            "text": "今天买复合肥128.5元，记到春季西瓜",
        },
        headers={"X-Idempotency-Key": "smart-fill-ledger-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["scene"] == "ledger.record"
    assert data["draft"]["category"] == "肥料"
    assert data["draft"]["amount"] == "128.50"
    assert data["missing_fields"] == []
    assert data["warnings"] == []


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_ledger_record_infers_note_when_llm_omits_it(mock_get_llm):
    result = CostParseResult(
        record_type="cost",
        category="化肥",
        amount="100",
        record_date="2026-06-08",
        note=None,
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "ledger.record",
            "text": "今天买化肥100",
        },
        headers={"X-Idempotency-Key": "smart-fill-ledger-note-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["scene"] == "ledger.record"
    assert data["draft"]["category"] == "化肥"
    assert data["draft"]["amount"] == "100"
    assert data["draft"]["note"] == "买化肥"


def test_parse_smart_fill_unknown_scene_returns_404():
    response = client.post(
        "/smart-fill/parse",
        json={"scene": "unknown.scene", "text": "随便填点什么"},
    )

    assert response.status_code == 404
    assert "不支持的智能填写场景" in response.json()["detail"]
