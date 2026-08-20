"""Business REST 路由与 service 契约回归。"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from business import server
from business.api import (
    costs,
    crop_cycles,
    crop_templates,
    farm_logs,
    farms,
    work_orders,
)
from business.api.deps import get_current_user
from business.db import get_db


@pytest.fixture
def db_marker() -> object:
    return object()


@pytest.fixture
def client(db_marker: object):
    app = server.create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-1",
        "farm_id": 7,
        "role": "user",
    }

    def override_db():
        yield db_marker

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client


def test_create_template_passes_validated_payload_to_service(
    client: TestClient, db_marker: object, monkeypatch
) -> None:
    monkeypatch.setattr(
        crop_templates.crop_service, "find_exact_duplicate", lambda *a, **k: None
    )
    captured = {}

    def create(db, **kwargs):
        captured.update({"db": db, **kwargs})
        return {"id": 11, "name": kwargs["name"]}

    monkeypatch.setattr(crop_templates.crop_service, "create_crop_template", create)
    response = client.post(
        "/api/agri_backend_v2/crop-templates",
        json={
            "name": "西瓜",
            "category": "瓜果",
            "stages": [{"name": "育苗期", "duration_days": 15, "order_index": 0}],
        },
    )

    assert response.status_code == 201
    assert captured["db"] is db_marker
    assert captured["farm_id"] == 7
    assert captured["stages"][0]["duration_days"] == 15


def test_update_cycle_merges_partial_request(
    client: TestClient, db_marker: object, monkeypatch
) -> None:
    monkeypatch.setattr(
        crop_cycles.cycle_service,
        "get_crop_cycle",
        lambda *a, **k: {
            "id": 3,
            "name": "旧茬口",
            "crop_template_id": 2,
            "start_date": "2026-08-01",
            "field_name": "一号棚",
            "total_area_mu": 2.5,
            "season": "秋茬",
            "batch_note": None,
        },
    )
    captured = {}

    def update(db, cycle_id, **kwargs):
        captured.update({"db": db, "cycle_id": cycle_id, **kwargs})
        return {"id": cycle_id, "name": kwargs["name"]}

    monkeypatch.setattr(crop_cycles.cycle_service, "update_crop_cycle", update)
    response = client.patch("/api/agri_backend_v2/crop-cycles/3", json={"name": "新茬口"})

    assert response.status_code == 200
    assert captured["db"] is db_marker
    assert captured["name"] == "新茬口"
    assert captured["crop_template_id"] == 2
    assert captured["start_date"] == date(2026, 8, 1)


def test_create_log_maps_date_and_worker_names(client: TestClient, monkeypatch) -> None:
    captured = {}

    def create_log(**kwargs):
        captured.update(kwargs)
        return {"id": 5, **kwargs}

    monkeypatch.setattr(farm_logs.log_service, "create_log", create_log)
    response = client.post(
        "/api/agri_backend_v2/farm-logs",
        json={
            "cycle_id": 2,
            "operation_type": "浇水",
            "operation_date": "2026-08-09",
            "worker_names": ["张三"],
        },
    )

    assert response.status_code == 201
    assert captured["farm_id"] == 7
    assert captured["operation_date"] == "2026-08-09"
    assert captured["worker_names"] == ["张三"]


def test_create_cost_record_injects_database_session(
    client: TestClient, db_marker: object, monkeypatch
) -> None:
    captured = {}

    def create_record(db, **kwargs):
        captured.update({"db": db, **kwargs})
        return {"id": 6}

    monkeypatch.setattr(costs.cost_service, "create_record", create_record)
    response = client.post(
        "/api/agri_backend_v2/cost-records",
        json={
            "record_type": "cost",
            "category": "农资",
            "amount": 100,
            "record_date": "2026-08-09",
        },
    )

    assert response.status_code == 201
    assert captured["db"] is db_marker
    assert captured["farm_id"] == 7
    assert captured["record_date"] == date(2026, 8, 9)


def test_create_work_order_keeps_nested_labor_contract(
    client: TestClient, db_marker: object, monkeypatch
) -> None:
    captured = {}

    def create_order(db, **kwargs):
        captured.update({"db": db, **kwargs})
        return {"id": 9}

    monkeypatch.setattr(
        work_orders.work_order_service, "create_work_order", create_order
    )
    response = client.post(
        "/api/agri_backend_v2/work-orders",
        json={
            "operation_type": "施肥",
            "operation_date": "2026-08-09",
            "cycle_id": 3,
            "labor_entries": [
                {"worker_name": "李四", "quantity": 1, "unit_price": 200}
            ],
        },
    )

    assert response.status_code == 201
    assert captured["db"] is db_marker
    assert captured["labor_entries"][0]["worker_name"] == "李四"


def test_farm_path_cannot_cross_token_farm(client: TestClient, monkeypatch) -> None:
    called = False

    def get_farm(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(farms.farm_crud_service, "get_farm_with_user", get_farm)
    response = client.get("/api/agri_backend_v2/farms/8")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"
    assert called is False


def test_unknown_request_field_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/agri_backend_v2/workers",
        json={"name": "王五", "unexpected": True},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"
