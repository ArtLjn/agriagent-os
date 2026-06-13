from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.prompt_registry import get_registry
from app.agent.application.smart_fill import _build_cache_key, parse_with_llm
from app.main import app
from app.schemas.cost import CostParseResult
from app.schemas.planting import WorkerCreate

client = TestClient(app)
get_registry().reload(Path(__file__).parent.parent / "prompts")


def _build_llm_with_structured_output(structured_result):
    """构造 structured output 成功的 LLM mock。"""
    mock_llm = MagicMock()
    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock(return_value=structured_result)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    return mock_llm


def _build_llm_with_structured_failure_and_fallback(
    structured_error,
    fallback_content: str,
):
    mock_llm = MagicMock()
    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock(side_effect=structured_error)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fallback_content))
    return mock_llm


def test_list_smart_fill_scenarios_exposes_registered_business_scenes():
    response = client.get("/smart-fill/scenarios")

    assert response.status_code == 200
    data = response.json()
    scene_keys = {item["key"] for item in data["items"]}
    assert {
        "ledger.record",
        "crop.template",
        "crop.cycle",
        "labor.worker",
    } <= scene_keys
    ledger = next(item for item in data["items"] if item["key"] == "ledger.record")
    assert ledger["legacy_endpoint"] == "/costs/parse"
    assert ledger["enabled"] is True
    worker = next(item for item in data["items"] if item["key"] == "labor.worker")
    assert worker["legacy_endpoint"] == "/planting/workers"
    assert "工人" in worker["title"]


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


def test_smart_fill_cache_key_is_isolated_by_farm_and_scene():
    first = _build_cache_key("same-key", "labor.worker", farm_id=1)
    second = _build_cache_key("same-key", "labor.worker", farm_id=2)
    third = _build_cache_key("same-key", "ledger.record", farm_id=1)

    assert first != second
    assert first != third
    assert first == "smart_fill:farm:1:labor.worker:same-key"


@pytest.mark.asyncio
async def test_parse_with_llm_logs_structured_validation_failure_without_traceback(
    caplog,
):
    try:
        WorkerCreate.model_validate_json('{"name":"","default_unit_price":""}')
    except ValidationError as exc:
        structured_error = exc
    mock_llm = _build_llm_with_structured_failure_and_fallback(
        structured_error,
        (
            '{"name":"李树梅","phone":null,"default_pay_type":"daily",'
            '"default_unit_price":"100","note":"长工","status":"active"}'
        ),
    )

    with caplog.at_level("WARNING", logger="app.agent.application.smart_fill"):
        result = await parse_with_llm(mock_llm, "prompt", WorkerCreate)

    assert result.name == "李树梅"
    record = next(
        item
        for item in caplog.records
        if "with_structured_output 校验失败" in item.message
    )
    assert record.exc_info is None
    assert "ValidationError" not in caplog.text


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_returns_create_draft(mock_get_llm):
    result = WorkerCreate(
        name="老王",
        phone="13800138000",
        default_pay_type="daily",
        default_unit_price="200",
        note="擅长授粉",
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "labor.worker",
            "text": "新增工人老王，电话 13800138000，日薪 200，擅长授粉",
        },
        headers={"X-Idempotency-Key": "smart-fill-worker-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["scene"] == "labor.worker"
    assert data["draft"] == {
        "name": "老王",
        "phone": "13800138000",
        "default_pay_type": "daily",
        "default_unit_price": "200",
        "note": "擅长授粉",
        "status": "active",
    }


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_normalizes_pay_type_and_status(mock_get_llm):
    result = WorkerCreate(
        name="李师傅",
        default_pay_type="计件",
        default_unit_price="50",
        note="临时工",
        status="停用",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "招了李师傅，计件每亩50，先停用"},
        headers={"X-Idempotency-Key": "smart-fill-worker-normalize-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["draft"]["default_pay_type"] == "piece"
    assert data["draft"]["status"] == "inactive"


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_returns_422_when_name_missing(mock_get_llm):
    result = WorkerCreate(
        name="未知",
        default_pay_type="daily",
        default_unit_price=None,
        note=None,
        status="active",
    )
    result.name = ""
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "随便说点什么"},
        headers={"X-Idempotency-Key": "smart-fill-worker-invalid-001"},
    )

    assert response.status_code == 422
    assert "无法识别工人信息" in response.json()["detail"]


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_idempotency_uses_cached_draft(mock_get_llm):
    result = WorkerCreate(
        name="张三",
        default_pay_type="daily",
        default_unit_price="180",
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    headers = {"X-Idempotency-Key": "smart-fill-worker-cache-001"}
    first = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增张三，日薪180"},
        headers=headers,
    )
    second = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增张三，日薪180"},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["draft"]["name"] == "张三"
    assert mock_get_llm.call_count == 1


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_batch_cases(mock_get_llm):
    cases = [
        (
            "新增工人赵六，日薪180",
            WorkerCreate(
                name="赵六", default_pay_type="daily", default_unit_price="180"
            ),
            {"name": "赵六", "default_pay_type": "daily", "default_unit_price": "180"},
        ),
        (
            "招了周师傅，时薪25，下午能来",
            WorkerCreate(
                name="周师傅",
                default_pay_type="hourly",
                default_unit_price="25",
                note="下午能来",
            ),
            {"name": "周师傅", "default_pay_type": "hourly", "note": "下午能来"},
        ),
        (
            "新增临时工小刘，按件每棵0.5",
            WorkerCreate(
                name="小刘", default_pay_type="piece", default_unit_price="0.5"
            ),
            {"name": "小刘", "default_pay_type": "piece", "default_unit_price": "0.5"},
        ),
    ]

    for index, (text, llm_result, expected) in enumerate(cases):
        mock_get_llm.return_value = _build_llm_with_structured_output(llm_result)
        response = client.post(
            "/smart-fill/parse",
            json={"scene": "labor.worker", "text": text},
            headers={"X-Idempotency-Key": f"smart-fill-worker-batch-{index}"},
        )

        assert response.status_code == 200
        draft = response.json()["draft"]
        for key, value in expected.items():
            assert draft[key] == value


def test_parse_smart_fill_request_rejects_empty_and_oversized_text():
    empty_response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": ""},
    )
    long_response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增工人" + "老王" * 250},
    )

    assert empty_response.status_code == 422
    assert long_response.status_code == 422


def test_parse_smart_fill_request_rejects_oversized_scene_key():
    response = client.post(
        "/smart-fill/parse",
        json={"scene": "x" * 81, "text": "新增工人老王"},
    )

    assert response.status_code == 422


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_boundary_accepts_max_lengths(mock_get_llm):
    result = WorkerCreate(
        name="工" * 100,
        phone="1" * 30,
        default_pay_type="daily",
        default_unit_price="100000",
        note="备" * 500,
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增一个字段接近上限的工人"},
        headers={"X-Idempotency-Key": "smart-fill-worker-boundary-max-001"},
    )

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert len(draft["name"]) == 100
    assert len(draft["phone"]) == 30
    assert len(draft["note"]) == 500
    assert draft["default_unit_price"] == "100000"


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_boundary_trims_optional_text(mock_get_llm):
    result = WorkerCreate.model_construct(
        name="老王",
        phone=" " + "1" * 35 + " ",
        default_pay_type="daily",
        default_unit_price="200",
        note=" " + "备注" * 260 + " ",
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增工人老王，补充信息很长"},
        headers={"X-Idempotency-Key": "smart-fill-worker-boundary-trim-001"},
    )

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert len(draft["phone"]) == 30
    assert draft["phone"] == "1" * 30
    assert len(draft["note"]) == 500
    assert draft["note"].startswith("备注")


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_marks_invalid_mobile_phone(mock_get_llm):
    result = WorkerCreate(
        name="张桂梅",
        phone="19083106293222222",
        default_pay_type="daily",
        default_unit_price="100",
        note="长工",
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "labor.worker",
            "text": "新来工人张桂梅长工日薪100电话19083106293222222",
        },
        headers={"X-Idempotency-Key": "smart-fill-worker-invalid-phone-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["draft"]["phone"] is None
    assert "phone" in data["missing_fields"]
    assert any("手机号格式不正确" in item for item in data["warnings"])


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_handles_crop_words_in_worker_description(mock_get_llm):
    result = WorkerCreate(
        name="李树梅",
        phone="190831062933",
        default_pay_type="daily",
        default_unit_price="100",
        note="长工，西瓜压瓜厉害",
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "labor.worker",
            "text": "新来一个工人李树梅长工100一天电话190831062933西瓜压瓜厉害",
        },
        headers={"X-Idempotency-Key": "smart-fill-worker-crop-word-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["scene"] == "labor.worker"
    assert data["draft"]["name"] == "李树梅"
    assert data["draft"]["phone"] is None
    assert "西瓜压瓜厉害" in data["draft"]["note"]
    assert "phone" in data["missing_fields"]


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_phone_boundary_matrix(mock_get_llm):
    cases = [
        (
            "新来工人老王电话13800138000",
            WorkerCreate(name="老王", phone="13800138000", status="active"),
            "13800138000",
            [],
        ),
        (
            "新来工人老李电话12345678901",
            WorkerCreate(name="老李", phone="12345678901", status="active"),
            None,
            ["phone"],
        ),
        (
            "新来工人老赵电话057188888888",
            WorkerCreate(name="老赵", phone="057188888888", status="active"),
            "057188888888",
            [],
        ),
        (
            "新来工人老周电话888888",
            WorkerCreate(name="老周", phone="888888", status="active"),
            "888888",
            [],
        ),
    ]

    for index, (text, result, expected_phone, expected_missing) in enumerate(cases):
        mock_get_llm.return_value = _build_llm_with_structured_output(result)
        response = client.post(
            "/smart-fill/parse",
            json={"scene": "labor.worker", "text": text},
            headers={"X-Idempotency-Key": f"smart-fill-worker-phone-matrix-{index}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["draft"]["phone"] == expected_phone
        assert data["missing_fields"] == expected_missing


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_marks_missing_unit_price_when_pay_mentioned(
    mock_get_llm,
):
    result = WorkerCreate(
        name="老王",
        phone="13800138000",
        default_pay_type="daily",
        default_unit_price=None,
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={
            "scene": "labor.worker",
            "text": "新增工人老王，日薪面议，电话13800138000",
        },
        headers={"X-Idempotency-Key": "smart-fill-worker-missing-price-001"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "default_unit_price" in data["missing_fields"]
    assert any("默认单价" in item for item in data["warnings"])


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_boundary_rejects_name_too_long(mock_get_llm):
    result = WorkerCreate.model_construct(
        name="工" * 101,
        default_pay_type="daily",
        default_unit_price=None,
        status="active",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增超长姓名工人"},
        headers={"X-Idempotency-Key": "smart-fill-worker-boundary-name-001"},
    )

    assert response.status_code == 422
    assert "无法识别工人信息" in response.json()["detail"]


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_boundary_rejects_invalid_prices(mock_get_llm):
    cases = [
        WorkerCreate.model_construct(
            name="负数工人",
            default_pay_type="daily",
            default_unit_price="-1",
            status="active",
        ),
        WorkerCreate.model_construct(
            name="超额工人",
            default_pay_type="daily",
            default_unit_price="100000.01",
            status="active",
        ),
    ]

    for index, result in enumerate(cases):
        mock_get_llm.return_value = _build_llm_with_structured_output(result)
        response = client.post(
            "/smart-fill/parse",
            json={"scene": "labor.worker", "text": "新增单价异常的工人"},
            headers={"X-Idempotency-Key": f"smart-fill-worker-boundary-price-{index}"},
        )

        assert response.status_code == 422
        assert "无法识别工人信息" in response.json()["detail"]


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_worker_boundary_defaults_unknown_enums(mock_get_llm):
    result = WorkerCreate(
        name="枚举工人",
        default_pay_type="weekly",
        default_unit_price="300",
        status="pending",
    )
    mock_get_llm.return_value = _build_llm_with_structured_output(result)

    response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增枚举值不标准的工人"},
        headers={"X-Idempotency-Key": "smart-fill-worker-boundary-enum-001"},
    )

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["default_pay_type"] == "daily"
    assert draft["status"] == "active"


@patch("app.agent.application.smart_fill.get_llm")
def test_parse_smart_fill_idempotency_cache_is_isolated_by_scene(mock_get_llm):
    worker_result = WorkerCreate(
        name="隔离工人",
        default_pay_type="daily",
        default_unit_price="160",
        status="active",
    )
    cost_result = CostParseResult(
        record_type="cost",
        category="人工",
        amount="160",
        record_date="2026-06-08",
        note="人工费",
    )
    mock_get_llm.side_effect = [
        _build_llm_with_structured_output(worker_result),
        _build_llm_with_structured_output(cost_result),
    ]
    headers = {"X-Idempotency-Key": "smart-fill-shared-boundary-001"}

    worker_response = client.post(
        "/smart-fill/parse",
        json={"scene": "labor.worker", "text": "新增隔离工人，日薪160"},
        headers=headers,
    )
    cost_response = client.post(
        "/smart-fill/parse",
        json={"scene": "ledger.record", "text": "今天付人工费160"},
        headers=headers,
    )

    assert worker_response.status_code == 200
    assert cost_response.status_code == 200
    assert worker_response.json()["draft"]["name"] == "隔离工人"
    assert cost_response.json()["draft"]["category"] == "人工"
    assert mock_get_llm.call_count == 2
