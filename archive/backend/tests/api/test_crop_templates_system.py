from collections.abc import Iterator
from contextlib import contextmanager

from app.domains.planting.crop_models import CropTemplate, GrowthStage
from app.domains.users.dependencies import get_current_user
from app.domains.users.models import User
from app.main import app


def _stage(name: str, duration_days: int, order_index: int, key_tasks: str | None):
    return {
        "name": name,
        "duration_days": duration_days,
        "order_index": order_index,
        "key_tasks": key_tasks,
    }


def _payload(name: str = "西瓜", variety: str | None = "8424"):
    return {
        "name": name,
        "variety": variety,
        "stages": [
            _stage("育苗期", 30, 0, "控温 保湿"),
            _stage("定植期", 1, 1, "浇定根水"),
        ],
    }


def _create_system_template(
    db_session,
    name: str = "西瓜",
    variety: str | None = "8424",
    category: str | None = "水果",
) -> CropTemplate:
    template = CropTemplate(
        farm_id=None,
        name=name,
        variety=variety,
        category=category,
    )
    db_session.add(template)
    db_session.flush()
    db_session.add_all(
        [
            GrowthStage(
                crop_template_id=template.id,
                name="育苗期",
                duration_days=30,
                order_index=0,
                key_tasks="控温 保湿",
            ),
            GrowthStage(
                crop_template_id=template.id,
                name="定植期",
                duration_days=1,
                order_index=1,
                key_tasks="浇定根水",
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(template)
    return template


def test_create_template_returns_existing_template_for_exact_duplicate(client):
    first_response = client.post("/crops/templates", json=_payload())
    assert first_response.status_code == 201
    first = first_response.json()
    assert first["already_exists"] is False

    second_response = client.post(
        "/crops/templates",
        json={
            "name": "西瓜",
            "variety": "8424",
            "stages": [
                _stage("定植期", 1, 0, "浇定根水"),
                _stage("育苗期", 30, 1, "  控温\t保湿  "),
            ],
        },
    )

    assert second_response.status_code == 200
    second = second_response.json()
    assert second["id"] == first["id"]
    assert second["already_exists"] is True

    list_response = client.get("/crops/templates")
    assert list_response.json()["total"] == 1


def test_list_system_templates_returns_stages_and_filters_category(
    client,
    db_session,
):
    fruit_template = _create_system_template(db_session, category="水果")
    _create_system_template(
        db_session,
        name="番茄",
        variety=None,
        category="蔬菜",
    )

    all_response = client.get("/crops/templates/system")
    fruit_response = client.get("/crops/templates/system?category=水果")

    assert all_response.status_code == 200
    assert {item["category"] for item in all_response.json()} == {"水果", "蔬菜"}
    assert fruit_response.status_code == 200
    fruit_items = fruit_response.json()
    assert [item["id"] for item in fruit_items] == [fruit_template.id]
    assert fruit_items[0]["category"] == "水果"
    assert [stage["name"] for stage in fruit_items[0]["stages"]] == [
        "育苗期",
        "定植期",
    ]


def test_import_system_template_returns_new_id_and_duplicate_import_existing_id(
    client,
    db_session,
):
    system_template = _create_system_template(db_session)

    first_response = client.post(f"/crops/templates/system/{system_template.id}/import")
    second_response = client.post(
        f"/crops/templates/system/{system_template.id}/import"
    )

    assert first_response.status_code == 201
    first = first_response.json()
    assert first["id"] != system_template.id
    assert first["already_exists"] is False

    assert second_response.status_code == 200
    second = second_response.json()
    assert second["id"] == first["id"]
    assert second["already_exists"] is True

    list_response = client.get("/crops/templates")
    assert list_response.json()["total"] == 1


def test_import_system_template_not_found_returns_404(client):
    response = client.post("/crops/templates/system/99999/import")

    assert response.status_code == 404


def test_system_templates_are_write_protected_at_api(client, db_session):
    system_template = _create_system_template(db_session)

    update_response = client.put(
        f"/crops/templates/{system_template.id}",
        json=_payload(name="改名西瓜"),
    )
    delete_response = client.delete(f"/crops/templates/{system_template.id}")

    assert update_response.status_code == 403
    assert delete_response.status_code == 403

    list_response = client.get("/crops/templates/system")
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "西瓜"


def test_create_system_template_endpoint_creates_with_null_farm_id(client):
    with _admin_user_override():
        response = client.post("/crops/templates/system", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "西瓜"
    assert body["variety"] == "8424"
    assert [s["name"] for s in body["stages"]] == ["育苗期", "定植期"]

    list_response = client.get("/crops/templates/system")
    assert any(item["id"] == body["id"] for item in list_response.json())


def test_update_system_template_endpoint_replaces_stages(client, db_session):
    system_template = _create_system_template(db_session)

    with _admin_user_override():
        response = client.put(
            f"/crops/templates/system/{system_template.id}",
            json={
                "name": "改名西瓜",
                "variety": "8424",
                "stages": [
                    _stage("新育苗期", 20, 0, "新任务"),
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "改名西瓜"
    assert [s["name"] for s in body["stages"]] == ["新育苗期"]


def test_update_system_template_not_found_returns_404(client):
    with _admin_user_override():
        response = client.put(
            "/crops/templates/system/99999",
            json=_payload(),
        )
    assert response.status_code == 404


def test_delete_system_template_endpoint_removes_template(client, db_session):
    system_template = _create_system_template(db_session)

    with _admin_user_override():
        response = client.delete(f"/crops/templates/system/{system_template.id}")

    assert response.status_code == 200
    list_response = client.get("/crops/templates/system")
    assert all(item["id"] != system_template.id for item in list_response.json())


def test_delete_system_template_returns_409_when_imported_by_farm(client, db_session):
    system_template = _create_system_template(db_session)
    db_session.add(CropTemplate(farm_id=1, name="西瓜", variety="8424", category="水果"))
    db_session.commit()

    with _admin_user_override():
        response = client.delete(f"/crops/templates/system/{system_template.id}")

    assert response.status_code == 409
    assert "已被 1 个农场导入" in response.json()["detail"]


@contextmanager
def _admin_user_override() -> Iterator[None]:
    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="system-template-admin",
        phone="18800009999",
        password_hash="h",
        nickname="系统模板管理员",
        role="admin",
        status="active",
    )
    try:
        yield
    finally:
        if original is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original
