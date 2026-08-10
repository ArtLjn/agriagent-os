from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from business.models import (
    CropCycle,
    CropTemplate,
    CycleStage,
    Farm,
    GrowthStage,
    PlantingPlanExecution,
    PlantingUnit,
)
from business.services import cycle_service, planting_plan_service


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        Farm.__table__,
        CropTemplate.__table__,
        GrowthStage.__table__,
        CropCycle.__table__,
        CycleStage.__table__,
        PlantingUnit.__table__,
        PlantingPlanExecution.__table__,
    ]
    Farm.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(Farm(id=1, uid="farm-1", name="测试农场"))
    return factory


def _add_template(
    db: Session,
    *,
    name: str,
    farm_id: int | None,
) -> CropTemplate:
    template = CropTemplate(name=name, farm_id=farm_id, category="瓜果类")
    db.add(template)
    db.flush()
    db.add(
        GrowthStage(
            crop_template_id=template.id,
            name="育苗期",
            duration_days=20,
            order_index=0,
        )
    )
    db.flush()
    db.refresh(template, attribute_names=["growth_stages"])
    return template


def test_prepare_and_commit_use_matching_template_atomically(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        unrelated = _add_template(db, name="橘子", farm_id=1)
        system_watermelon = _add_template(db, name="西瓜", farm_id=None)

    with session_factory.begin() as db:
        prepared = planting_plan_service.prepare_planting_plan(
            db,
            farm_id=1,
            crop_name=" 西 瓜 ",
            total_area_mu=5,
            field_name="东棚",
            start_date="2026-08-10",
        )

    assert prepared["plan"]["template_action"] == "import_system"
    assert prepared["plan"]["template"]["system_template_id"] == system_watermelon.id
    assert prepared["plan"]["template"]["id"] != unrelated.id

    with session_factory.begin() as db:
        committed = planting_plan_service.commit_planting_plan(
            db,
            farm_id=1,
            client_request_id=prepared["client_request_id"],
            approval_fingerprint=prepared["approval_fingerprint"],
            plan=prepared["plan"],
        )

    assert committed["status"] == "committed"
    assert committed["template"]["name"] == "西瓜"
    assert committed["planting_unit"]["name"] == "东棚"

    with session_factory.begin() as db:
        cycle = db.get(CropCycle, committed["cycle"]["id"])
        bound_template = db.get(CropTemplate, cycle.crop_template_id)
        assert bound_template.farm_id == 1
        assert bound_template.name == "西瓜"
        assert db.query(PlantingUnit).count() == 1
        assert db.query(PlantingPlanExecution).count() == 1

        replay = planting_plan_service.commit_planting_plan(
            db,
            farm_id=1,
            client_request_id=prepared["client_request_id"],
            approval_fingerprint=prepared["approval_fingerprint"],
            plan=prepared["plan"],
        )
        assert replay["idempotent_replay"] is True
        assert db.query(CropCycle).count() == 1
        assert db.query(PlantingUnit).count() == 1


def test_cycle_rejects_template_for_another_crop(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        orange = _add_template(db, name="橘子", farm_id=1)
        with pytest.raises(ValueError, match="crop_template_mismatch"):
            cycle_service.create_crop_cycle(
                db,
                farm_id=1,
                name="西瓜种植计划",
                crop_template_id=orange.id,
                start_date=date(2026, 8, 10),
                expected_crop_name="西瓜",
            )


def test_cycle_rejects_direct_system_template_binding(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        system_template = _add_template(db, name="西瓜", farm_id=None)
        with pytest.raises(ValueError, match="system_template_not_imported"):
            cycle_service.create_crop_cycle(
                db,
                farm_id=1,
                name="西瓜种植计划",
                crop_template_id=system_template.id,
                start_date=date(2026, 8, 10),
                expected_crop_name="西瓜",
            )


def test_failed_commit_rolls_back_all_new_entities(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        prepared = planting_plan_service.prepare_planting_plan(
            db,
            farm_id=1,
            crop_name="榴莲",
            total_area_mu=3,
            field_name="西棚",
            start_date="2026-08-11",
            template_strategy="create_custom",
            custom_template={
                "name": "榴莲",
                "category": "果树",
                "stages": [{"name": "幼苗期", "duration_days": 365}],
            },
        )

    broken_plan = dict(prepared["plan"])
    broken_plan["planting_unit"] = dict(broken_plan["planting_unit"])
    broken_plan["planting_unit"].pop("name")
    fingerprint = planting_plan_service._fingerprint(broken_plan)

    with pytest.raises(
        planting_plan_service.PlantingPlanError,
        match="事务已回滚",
    ):
        with session_factory.begin() as db:
            planting_plan_service.commit_planting_plan(
                db,
                farm_id=1,
                client_request_id="rollback-case",
                approval_fingerprint=fingerprint,
                plan=broken_plan,
            )

    with session_factory() as db:
        assert db.query(CropTemplate).count() == 0
        assert db.query(CropCycle).count() == 0
        assert db.query(PlantingUnit).count() == 0
        assert db.query(PlantingPlanExecution).count() == 0


def test_approval_stale_and_idempotency_conflict_do_not_write_again(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        watermelon = _add_template(db, name="西瓜", farm_id=1)
        prepared = planting_plan_service.prepare_planting_plan(
            db,
            farm_id=1,
            crop_name="西瓜",
            total_area_mu=2,
            field_name="南棚",
            start_date="2026-08-12",
            template_strategy="existing",
            template_id=watermelon.id,
        )

    changed_plan = dict(prepared["plan"])
    changed_plan["cycle"] = dict(changed_plan["cycle"])
    changed_plan["cycle"]["total_area_mu"] = 4
    with session_factory() as db:
        with pytest.raises(
            planting_plan_service.PlantingPlanError,
            match="审批后的种植计划内容已发生变化",
        ) as exc_info:
            planting_plan_service.commit_planting_plan(
                db,
                farm_id=1,
                client_request_id=prepared["client_request_id"],
                approval_fingerprint=prepared["approval_fingerprint"],
                plan=changed_plan,
            )
    assert exc_info.value.code == "approval_stale"

    with session_factory.begin() as db:
        planting_plan_service.commit_planting_plan(
            db,
            farm_id=1,
            client_request_id=prepared["client_request_id"],
            approval_fingerprint=prepared["approval_fingerprint"],
            plan=prepared["plan"],
        )

    with session_factory() as db:
        with pytest.raises(
            planting_plan_service.PlantingPlanError,
            match="另一份种植计划",
        ) as exc_info:
            planting_plan_service.commit_planting_plan(
                db,
                farm_id=1,
                client_request_id=prepared["client_request_id"],
                approval_fingerprint=planting_plan_service._fingerprint(changed_plan),
                plan=changed_plan,
            )
        assert db.query(CropCycle).count() == 1
        assert db.query(PlantingUnit).count() == 1
    assert exc_info.value.code == "idempotency_conflict"


def test_prepare_rejects_conflicting_farm_and_field_locations(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        farm = db.get(Farm, 1)
        farm.location = "江苏省苏州市"
        _add_template(db, name="西瓜", farm_id=1)

    with session_factory() as db:
        with pytest.raises(
            planting_plan_service.PlantingPlanError,
            match="目标地块位置不一致",
        ) as exc_info:
            planting_plan_service.prepare_planting_plan(
                db,
                farm_id=1,
                crop_name="西瓜",
                total_area_mu=5,
                field_name="睢宁地块",
                field_location="江苏省徐州市睢宁县",
                start_date="2026-08-10",
            )
    assert exc_info.value.code == "planting_location_ambiguous"

    with session_factory() as db:
        prepared = planting_plan_service.prepare_planting_plan(
            db,
            farm_id=1,
            crop_name="西瓜",
            total_area_mu=5,
            field_name="睢宁地块",
            field_location="江苏省徐州市睢宁县",
            field_location_confirmed=True,
            start_date="2026-08-10",
        )
    assert prepared["status"] == "ready"
    assert prepared["plan"]["field_location_confirmed"] is True
