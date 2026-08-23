from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from business.models import (
    CropCycle,
    CropTemplate,
    Farm,
    FarmLog,
    FarmLogWorker,
    PlantingUnit,
    Worker,
)
from business.services import worker_service, work_order_service


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Farm.metadata.create_all(
        engine,
        tables=[
            Farm.__table__,
            CropTemplate.__table__,
            CropCycle.__table__,
            Worker.__table__,
            PlantingUnit.__table__,
            FarmLog.__table__,
            FarmLogWorker.__table__,
        ],
    )
    return sessionmaker(bind=engine, expire_on_commit=False)


def _add_farm_and_cycle(db: Session, cycle_name: str = "春茬") -> CropCycle:
    farm = Farm(id=1, uid="farm-1", name="测试农场")
    template = CropTemplate(name="番茄", farm_id=1)
    db.add_all([farm, template])
    db.flush()
    cycle = CropCycle(
        farm_id=farm.id,
        name=cycle_name,
        crop_template_id=template.id,
        start_date=date(2026, 3, 1),
    )
    db.add(cycle)
    db.flush()
    return cycle


def test_worker_same_name_is_allowed_but_phone_is_unique(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        _add_farm_and_cycle(db)
        first = worker_service.create_worker(
            db, farm_id=1, name="张 三", phone="138 001-00001"
        )
        second = worker_service.create_worker(
            db, farm_id=1, name="张三", phone="13900100002"
        )

        assert first["id"] != second["id"]
        assert first["name"] == second["name"] == "张三"

        with pytest.raises(worker_service.WorkerIdentityError) as error:
            worker_service.create_worker(
                db, farm_id=1, name="李四", phone="13800100001"
            )

    assert error.value.code == "duplicate_worker_phone"
    assert error.value.meta["existing_id"] == first["id"]


def test_same_name_without_phone_requires_disambiguation(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        _add_farm_and_cycle(db)
        worker_service.create_worker(db, farm_id=1, name="王五")

        with pytest.raises(worker_service.WorkerIdentityError) as error:
            worker_service.create_worker(db, farm_id=1, name=" 王 五 ")

    assert error.value.code == "worker_identity_ambiguous"


def test_name_resolution_never_guesses_between_workers(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        _add_farm_and_cycle(db)
        first = worker_service.create_worker(
            db, farm_id=1, name="赵六", phone="13800100001"
        )
        second = worker_service.create_worker(
            db, farm_id=1, name="赵六", phone="13800100002"
        )

        with pytest.raises(worker_service.WorkerIdentityError) as error:
            worker_service.resolve_worker_by_name(db, 1, "赵六")

    assert error.value.code == "worker_identity_ambiguous"
    assert error.value.meta["candidate_ids"] == [first["id"], second["id"]]


def test_log_worker_reference_does_not_create_missing_worker(
    session_factory: sessionmaker[Session],
) -> None:
    from business.services.log_service import _resolve_worker_ids

    with session_factory.begin() as db:
        _add_farm_and_cycle(db)
        worker = worker_service.create_worker(
            db, farm_id=1, name="孙七", phone="13800100007"
        )
        assert _resolve_worker_ids(db, 1, worker_names=["孙七"]) == [worker["id"]]

        with pytest.raises(worker_service.WorkerIdentityError) as error:
            _resolve_worker_ids(db, 1, worker_names=["不存在的人"])

        assert db.query(Worker).count() == 1

    assert error.value.code == "worker_not_found"


def test_planting_unit_name_is_unique_within_cycle(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as db:
        first_cycle = _add_farm_and_cycle(db, cycle_name="春茬")
        second_cycle = CropCycle(
            farm_id=1,
            name="秋茬",
            crop_template_id=first_cycle.crop_template_id,
            start_date=date(2026, 9, 1),
        )
        db.add(second_cycle)
        db.flush()

        first_unit = work_order_service.create_unit(
            db, farm_id=1, cycle_id=first_cycle.id, name="东 棚"
        )
        with pytest.raises(work_order_service.PlantingUnitConflictError):
            work_order_service.create_unit(
                db, farm_id=1, cycle_id=first_cycle.id, name="东棚"
            )

        second_unit = work_order_service.create_unit(
            db, farm_id=1, cycle_id=second_cycle.id, name="东棚"
        )

    assert first_unit["name"] == second_unit["name"] == "东棚"
    assert first_unit["cycle_id"] != second_unit["cycle_id"]
