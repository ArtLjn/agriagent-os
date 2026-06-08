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


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_ledger_record_infers_structured_debt(mock_get_llm):
    result = CostParseResult(
        record_type="cost",
        category="种子",
        amount="195.30",
        record_date="2026-06-08",
        note="买苹果种子，向王秉着赊账",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "ledger.record",
            "text": "今天买苹果种子195.3 向 王秉着 赊账",
        },
        headers={"X-Idempotency-Key": "smart-fill-ledger-debt-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["draft"]["record_subtype"] == "赊账"
    assert data["draft"]["counterparty"] == "王秉着"
    assert data["draft"]["note"] == "买苹果种子，向王秉着赊账"


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_ledger_record_handles_owed_counterparty(mock_get_llm):
    result = CostParseResult(
        record_type="cost",
        category="农资",
        amount="2000",
        record_date="2026-06-08",
        note="欠张三2000买农资",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "ledger.record",
            "text": "欠张三2000买农资",
        },
        headers={"X-Idempotency-Key": "smart-fill-ledger-debt-owed-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["draft"]["record_subtype"] == "赊账"
    assert data["draft"]["counterparty"] == "张三"


@patch("app.agent.application.smart_fill.get_llm")
def test_parsed_debt_draft_can_create_unsettled_cost_record(mock_get_llm):
    result = CostParseResult(
        record_type="cost",
        category="种子",
        amount="195.30",
        record_date="2026-06-08",
        note="买苹果种子，向王秉着赊账",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    parse_response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "ledger.record",
            "text": "今天买苹果种子195.3 向王秉着赊账",
        },
        headers={"X-Idempotency-Key": "smart-fill-ledger-debt-create-001"},
    )
    assert parse_response.status_code == 200

    create_response = client.post("/costs", json=parse_response.json()["draft"])

    assert create_response.status_code == 200
    data = create_response.json()
    assert data["record_subtype"] == "赊账"
    assert data["counterparty"] == "王秉着"
    assert data["settled_amount"] == "0.00"
    assert data["settlement_status"] == "unsettled"


def test_parse_smart_fill_unknown_scene_returns_404():
    response = client.post(
        "/smart-fill/parse",
        json={"scene": "unknown.scene", "text": "随便填点什么"},
    )

    assert response.status_code == 404
    assert "不支持的智能填写场景" in response.json()["detail"]
