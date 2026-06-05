"""更新茬口 Skill (update_crop_cycle) 单元测试。"""

import importlib
from datetime import date

import pytest
from skillify.core.context import SkillContext

from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle, CycleStage
from app.models.farm import Farm

_mod = importlib.import_module("app.agent.skills.update-crop-cycle.scripts.main")
UpdateCropCycleSkill = _mod.UpdateCropCycleSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


@pytest.fixture
def skill_session(monkeypatch, db_session):
    """让 Skill 使用当前测试会话，便于验证真实数据库状态。"""
    monkeypatch.setattr(_mod, "SessionLocal", lambda: db_session)
    return db_session


def _create_template(db, farm_id: int, name: str = "玉米") -> CropTemplate:
    """创建包含两个阶段的作物模板。"""
    template = CropTemplate(farm_id=farm_id, name=name)
    db.add(template)
    db.flush()
    db.add_all(
        [
            GrowthStage(
                crop_template_id=template.id,
                name="播种期",
                duration_days=10,
                order_index=0,
                key_tasks="播种",
            ),
            GrowthStage(
                crop_template_id=template.id,
                name="生长期",
                duration_days=20,
                order_index=1,
                key_tasks="管理",
            ),
        ]
    )
    db.flush()
    return template


def _create_cycle(
    db,
    *,
    farm_id: int = 1,
    name: str = "夏季玉米",
    crop_name: str = "玉米",
    start_date: date = date(2026, 6, 1),
    status: str = "active",
) -> CropCycle:
    """创建带两个阶段的茬口。"""
    template = _create_template(db, farm_id=farm_id, name=crop_name)
    cycle = CropCycle(
        farm_id=farm_id,
        name=name,
        crop_template_id=template.id,
        start_date=start_date,
        status=status,
    )
    db.add(cycle)
    db.flush()
    db.add_all(
        [
            CycleStage(
                cycle_id=cycle.id,
                name="播种期",
                start_date=start_date,
                end_date=date(2026, 6, 10),
                duration_days=10,
                order_index=0,
                is_current=False,
            ),
            CycleStage(
                cycle_id=cycle.id,
                name="生长期",
                start_date=date(2026, 6, 11),
                end_date=date(2026, 6, 30),
                duration_days=20,
                order_index=1,
                is_current=False,
            ),
        ]
    )
    db.commit()
    db.refresh(cycle)
    return cycle


def test_metadata_declares_write_confirmation():
    skill = UpdateCropCycleSkill()
    metadata = skill.metadata()

    assert metadata["permission_level"] == SkillPermissionLevel.WRITE_CONFIRM
    assert metadata["risk_level"] == SkillRiskLevel.MEDIUM
    assert "crop_cycle" in metadata["cache_invalidation"]
    assert "get_farm_status" in metadata["cache_invalidation"]
    schema = metadata["confirmation_schema"]
    assert "cycle_id" in schema["target_fields"]
    assert "cycle_name" in schema["target_fields"]
    assert "crop_name" in schema["target_fields"]
    assert "start_date" in schema["changed_fields"]


@pytest.mark.asyncio
async def test_missing_start_date_fails(ctx):
    result = await UpdateCropCycleSkill().execute({"cycle_id": 1}, ctx)

    assert result.status.value == "failed"
    assert "start_date" in result.reply


@pytest.mark.asyncio
async def test_invalid_start_date_fails(ctx):
    result = await UpdateCropCycleSkill().execute(
        {"cycle_id": 1, "start_date": "2026-09-31"},
        ctx,
    )

    assert result.status.value == "failed"
    assert "YYYY-MM-DD" in result.reply


@pytest.mark.asyncio
async def test_updates_start_date_by_cycle_id_and_recalculates_stages(
    skill_session, ctx
):
    cycle = _create_cycle(skill_session)

    result = await UpdateCropCycleSkill().execute(
        {"cycle_id": cycle.id, "start_date": "2026-09-01"},
        ctx,
    )

    assert result.status.value == "success"
    assert "夏季玉米" in result.reply
    assert "2026-06-01" in result.reply
    assert "2026-09-01" in result.reply
    assert "阶段日期已同步重算" in result.reply

    updated = skill_session.get(CropCycle, cycle.id)
    stages = sorted(updated.stages, key=lambda stage: stage.order_index)
    assert updated.start_date == date(2026, 9, 1)
    assert stages[0].start_date == date(2026, 9, 1)
    assert stages[0].end_date == date(2026, 9, 10)
    assert stages[1].start_date == date(2026, 9, 11)
    assert stages[1].end_date == date(2026, 9, 30)


@pytest.mark.asyncio
async def test_auto_matches_unique_active_cycle_by_crop_name(skill_session, ctx):
    cycle = _create_cycle(skill_session, name="夏季玉米", crop_name="玉米")
    _create_cycle(skill_session, name="春季辣椒", crop_name="辣椒")

    result = await UpdateCropCycleSkill().execute(
        {"crop_name": "玉米", "start_date": "2026-09-01"},
        ctx,
    )

    assert result.status.value == "success"
    assert skill_session.get(CropCycle, cycle.id).start_date == date(2026, 9, 1)


@pytest.mark.asyncio
async def test_multiple_active_cycles_return_need_clarify(skill_session, ctx):
    first = _create_cycle(skill_session, name="夏季玉米", crop_name="玉米")
    second = _create_cycle(skill_session, name="秋季玉米", crop_name="玉米")

    result = await UpdateCropCycleSkill().execute(
        {"crop_name": "玉米", "start_date": "2026-09-01"},
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "多个" in result.reply
    assert f"ID: {first.id}" in result.reply
    assert f"ID: {second.id}" in result.reply


@pytest.mark.asyncio
async def test_does_not_update_cycle_from_other_farm(skill_session):
    skill_session.add(Farm(id=2, name="隔壁农场", user_id="test-user-002"))
    skill_session.commit()
    other_cycle = _create_cycle(skill_session, farm_id=2, name="隔壁玉米")

    result = await UpdateCropCycleSkill().execute(
        {"cycle_id": other_cycle.id, "start_date": "2026-09-01"},
        SkillContext(farm_id=1),
    )

    assert result.status.value == "failed"
    assert skill_session.get(CropCycle, other_cycle.id).start_date == date(2026, 6, 1)
