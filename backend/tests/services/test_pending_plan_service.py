"""Pending plan service 测试。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.shared.database import Base
from app.models.farm import Farm
from app.services.pending_plan_service import (
    cancel_active_plan,
    create_pending_plan,
    expire_stale_plans,
    get_active_plan,
    mark_step_executed,
)

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_pending_plan_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()


def test_create_and_get_active_plan_with_steps():
    db = Session()
    plan = create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-plan",
        raw_user_input="王大妈工资100一天，去5号棚收水稻",
        router_decision={
            "selected_tools": ["manage_workers", "create_operation_work_order"]
        },
        steps=[
            {
                "skill_name": "manage_workers",
                "params": {"name": "王大妈", "daily_wage": 100},
                "confirmation_text": "确认创建工人王大妈吗？",
            },
            {
                "skill_name": "create_operation_work_order",
                "params": {"field_name": "5号棚", "crop_name": "水稻"},
                "confirmation_text": "确认安排作业吗？",
            },
        ],
        ttl_seconds=300,
    )

    loaded = get_active_plan(db, farm_id=1, session_id="sess-plan")
    assert loaded is not None
    assert loaded.plan_id == plan.plan_id
    assert len(loaded.steps) == 2
    assert loaded.steps[0].params_json["daily_wage"] == 100
    db.close()


def test_mark_step_executed_advances_current_step():
    db = Session()
    plan = create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-exec",
        raw_user_input="记一笔支出",
        router_decision={"selected_tools": ["create_cost_record"]},
        steps=[
            {
                "skill_name": "create_cost_record",
                "params": {"amount": 20},
                "confirmation_text": "确认记账吗？",
            }
        ],
        ttl_seconds=300,
    )

    mark_step_executed(
        db,
        plan_id=plan.plan_id,
        step_index=0,
        result={"record_id": 9},
    )

    loaded = get_active_plan(db, farm_id=1, session_id="sess-exec")
    assert loaded is None
    db.close()


def test_cancel_active_plan():
    db = Session()
    create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-cancel",
        raw_user_input="停用李一凡",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[{"skill_name": "manage_workers", "params": {"name": "李一凡"}}],
        ttl_seconds=300,
    )

    cancelled = cancel_active_plan(db, farm_id=1, session_id="sess-cancel")

    assert cancelled is True
    assert get_active_plan(db, farm_id=1, session_id="sess-cancel") is None
    db.close()


def test_expire_stale_plans():
    db = Session()
    plan = create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-expire",
        raw_user_input="停用李一凡",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[{"skill_name": "manage_workers", "params": {"name": "李一凡"}}],
        ttl_seconds=1,
    )
    plan.expires_at = datetime.now() - timedelta(seconds=1)
    db.commit()

    count = expire_stale_plans(db, now=datetime.now())

    assert count == 1
    assert get_active_plan(db, farm_id=1, session_id="sess-expire") is None
    db.close()
