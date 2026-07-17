"""工人档案 Skill 测试。"""

import importlib
from decimal import Decimal

import pytest
from skillify.core.context import SkillContext

from app.models.planting import Worker

_manage_workers_mod = importlib.import_module(
    "app.skills.manage-workers.scripts.main"
)

ManageWorkersSkill = _manage_workers_mod.ManageWorkersSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


@pytest.fixture
def worker_skill_sessions(monkeypatch, db_session):
    monkeypatch.setattr(_manage_workers_mod, "SessionLocal", lambda: db_session)
    return db_session


def _add_worker(db, name: str, status: str = "active") -> Worker:
    worker = Worker(
        farm_id=1,
        name=name,
        status=status,
        default_pay_type="daily",
        default_unit_price=Decimal("150"),
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


@pytest.mark.asyncio
async def test_manage_workers_empty_params_queries_active_workers(
    worker_skill_sessions, ctx
):
    _add_worker(worker_skill_sessions, "李四")
    _add_worker(worker_skill_sessions, "王五", status="inactive")

    result = await ManageWorkersSkill().execute({}, ctx)

    assert result.status.value == "success"
    assert "李四" in result.reply
    assert "王五" not in result.reply
    assert "创建工人需要姓名" not in result.reply


@pytest.mark.asyncio
async def test_manage_workers_query_action_queries_workers(worker_skill_sessions, ctx):
    _add_worker(worker_skill_sessions, "李四")

    result = await ManageWorkersSkill().execute({"action": "query"}, ctx)

    assert result.status.value == "success"
    assert "李四" in result.reply


@pytest.mark.asyncio
async def test_manage_workers_query_operation_queries_workers(worker_skill_sessions, ctx):
    _add_worker(worker_skill_sessions, "李四")

    result = await ManageWorkersSkill().execute({"operation": "query_workers"}, ctx)

    assert result.status.value == "success"
    assert "李四" in result.reply


@pytest.mark.asyncio
async def test_manage_workers_query_can_include_inactive(worker_skill_sessions, ctx):
    _add_worker(worker_skill_sessions, "王五", status="inactive")

    result = await ManageWorkersSkill().execute({"active_only": False}, ctx)

    assert result.status.value == "success"
    assert "王五" in result.reply
    assert "已停用" in result.reply


@pytest.mark.asyncio
async def test_manage_workers_creates_worker(worker_skill_sessions, ctx):
    result = await ManageWorkersSkill().execute(
        {
            "action": "create",
            "name": "赵六",
            "default_pay_type": "daily",
            "default_unit_price": 180,
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "赵六" in result.reply
    worker = worker_skill_sessions.query(Worker).filter(Worker.name == "赵六").one()
    assert worker.default_unit_price == Decimal("180.00")


@pytest.mark.asyncio
async def test_manage_workers_preserves_full_worker_name(worker_skill_sessions, ctx):
    result = await ManageWorkersSkill().execute(
        {
            "action": "create",
            "name": "刘俊男",
            "default_pay_type": "daily",
            "default_unit_price": 200,
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "刘俊男" in result.reply
    assert "刘俊（" not in result.reply
    worker = worker_skill_sessions.query(Worker).filter(Worker.name == "刘俊男").one()
    assert worker.name == "刘俊男"


@pytest.mark.asyncio
async def test_manage_workers_deactivates_without_hard_delete(
    worker_skill_sessions, ctx
):
    worker = _add_worker(worker_skill_sessions, "李四")

    result = await ManageWorkersSkill().execute(
        {"action": "deactivate", "worker_id": worker.id},
        ctx,
    )

    assert result.status.value == "success"
    assert "已停用工人" in result.reply
    saved = worker_skill_sessions.query(Worker).filter(Worker.id == worker.id).one()
    assert saved.status == "inactive"


@pytest.mark.asyncio
async def test_manage_workers_restores_worker(worker_skill_sessions, ctx):
    worker = _add_worker(worker_skill_sessions, "王五", status="inactive")

    result = await ManageWorkersSkill().execute(
        {"action": "restore", "worker_id": worker.id},
        ctx,
    )

    assert result.status.value == "success"
    saved = worker_skill_sessions.query(Worker).filter(Worker.id == worker.id).one()
    assert saved.status == "active"


@pytest.mark.asyncio
async def test_create_inactive_duplicate_requires_clarification(
    worker_skill_sessions, ctx
):
    _add_worker(worker_skill_sessions, "李四", status="inactive")

    result = await ManageWorkersSkill().execute(
        {"action": "create", "name": "李四", "default_unit_price": 150},
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "已停用" in result.reply
