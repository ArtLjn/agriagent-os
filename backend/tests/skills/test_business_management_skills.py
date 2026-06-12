"""普通业务补齐 Skill 执行测试。"""

import importlib
from datetime import date
from decimal import Decimal

import pytest
from skillify.core.context import SkillContext

from app.models.cost import CostRecord
from app.models.cost_category import CostCategory
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle, CycleStage
from app.models.log import FarmLog
from app.models.planting import PlantingUnit
from app.models.user import User
from app.models.user_setting import UserSetting

_delete_cost_mod = importlib.import_module(
    "app.agent.skills.delete-cost-record.scripts.main"
)
_get_categories_mod = importlib.import_module(
    "app.agent.skills.get-cost-categories.scripts.main"
)
_manage_categories_mod = importlib.import_module(
    "app.agent.skills.manage-cost-categories.scripts.main"
)
_get_units_mod = importlib.import_module(
    "app.agent.skills.get-planting-units.scripts.main"
)
_manage_units_mod = importlib.import_module(
    "app.agent.skills.manage-planting-units.scripts.main"
)
_get_templates_mod = importlib.import_module(
    "app.agent.skills.get-crop-templates.scripts.main"
)
_manage_templates_mod = importlib.import_module(
    "app.agent.skills.manage-crop-templates.scripts.main"
)
_manage_logs_mod = importlib.import_module(
    "app.agent.skills.manage-farm-logs.scripts.main"
)
_delete_cycle_mod = importlib.import_module(
    "app.agent.skills.delete-crop-cycle.scripts.main"
)
_get_settings_mod = importlib.import_module(
    "app.agent.skills.get-user-settings.scripts.main"
)
_manage_settings_mod = importlib.import_module(
    "app.agent.skills.manage-user-settings.scripts.main"
)

DeleteCostRecordSkill = _delete_cost_mod.DeleteCostRecordSkill
GetCostCategoriesSkill = _get_categories_mod.GetCostCategoriesSkill
ManageCostCategoriesSkill = _manage_categories_mod.ManageCostCategoriesSkill
GetPlantingUnitsSkill = _get_units_mod.GetPlantingUnitsSkill
ManagePlantingUnitsSkill = _manage_units_mod.ManagePlantingUnitsSkill
GetCropTemplatesSkill = _get_templates_mod.GetCropTemplatesSkill
ManageCropTemplatesSkill = _manage_templates_mod.ManageCropTemplatesSkill
ManageFarmLogsSkill = _manage_logs_mod.ManageFarmLogsSkill
DeleteCropCycleSkill = _delete_cycle_mod.DeleteCropCycleSkill
GetUserSettingsSkill = _get_settings_mod.GetUserSettingsSkill
ManageUserSettingsSkill = _manage_settings_mod.ManageUserSettingsSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1, user_id="test-user-001")


@pytest.fixture
def patched_skill_sessions(monkeypatch, db_session):
    for module in (
        _delete_cost_mod,
        _get_categories_mod,
        _manage_categories_mod,
        _get_units_mod,
        _manage_units_mod,
        _get_templates_mod,
        _manage_templates_mod,
        _manage_logs_mod,
        _delete_cycle_mod,
        _get_settings_mod,
        _manage_settings_mod,
    ):
        monkeypatch.setattr(module, "SessionLocal", lambda: db_session)
    return db_session


def _create_template(db, name: str = "西瓜") -> CropTemplate:
    template = CropTemplate(farm_id=1, name=name, variety="早佳")
    db.add(template)
    db.flush()
    db.add_all(
        [
            GrowthStage(
                crop_template_id=template.id,
                name="苗期",
                duration_days=10,
                order_index=0,
            ),
            GrowthStage(
                crop_template_id=template.id,
                name="伸蔓期",
                duration_days=20,
                order_index=1,
            ),
        ]
    )
    db.commit()
    db.refresh(template)
    return template


def _create_cycle(db, template: CropTemplate | None = None) -> CropCycle:
    template = template or _create_template(db)
    cycle = CropCycle(
        farm_id=1,
        name="春茬西瓜",
        crop_template_id=template.id,
        start_date=date(2026, 3, 1),
        total_area_mu=Decimal("8"),
        season="春季",
        status="active",
    )
    db.add(cycle)
    db.flush()
    db.add(
        CycleStage(
            cycle_id=cycle.id,
            name="苗期",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 10),
            duration_days=10,
            order_index=0,
            is_current=True,
        )
    )
    db.commit()
    db.refresh(cycle)
    return cycle


@pytest.mark.asyncio
async def test_delete_cost_record_soft_deletes_record(patched_skill_sessions, ctx):
    record = CostRecord(
        farm_id=1,
        record_type="cost",
        category="化肥",
        amount=Decimal("120"),
        record_date=date(2026, 6, 1),
    )
    patched_skill_sessions.add(record)
    patched_skill_sessions.commit()

    result = await DeleteCostRecordSkill().execute({"record_id": record.id}, ctx)

    assert result.status.value == "success"
    saved = patched_skill_sessions.get(CostRecord, record.id)
    assert saved.deleted_at is not None


@pytest.mark.asyncio
async def test_cost_category_skills_create_list_delete(patched_skill_sessions, ctx):
    created = await ManageCostCategoriesSkill().execute(
        {"action": "create", "name": "农机", "type": "cost", "icon": "tractor"},
        ctx,
    )
    assert created.status.value == "success"
    category = patched_skill_sessions.query(CostCategory).filter_by(name="农机").one()

    listed = await GetCostCategoriesSkill().execute({}, ctx)
    assert listed.status.value == "success"
    assert "农机" in listed.reply

    deleted = await ManageCostCategoriesSkill().execute(
        {"action": "delete", "category_id": category.id},
        ctx,
    )
    assert deleted.status.value == "success"
    assert patched_skill_sessions.get(CostCategory, category.id) is None


@pytest.mark.asyncio
async def test_planting_unit_skills_create_list_update_delete(
    patched_skill_sessions, ctx
):
    cycle = _create_cycle(patched_skill_sessions)
    cycle_id = cycle.id

    created = await ManagePlantingUnitsSkill().execute(
        {
            "action": "create",
            "cycle_id": cycle_id,
            "name": "东大棚",
            "area_mu": 3.5,
            "planted_date": "2026-03-02",
        },
        ctx,
    )
    assert created.status.value == "success"
    unit = patched_skill_sessions.query(PlantingUnit).filter_by(name="东大棚").one()
    unit_id = unit.id

    listed = await GetPlantingUnitsSkill().execute({"cycle_id": cycle_id}, ctx)
    assert listed.status.value == "success"
    assert "东大棚" in listed.reply

    updated = await ManagePlantingUnitsSkill().execute(
        {"action": "update", "unit_id": unit_id, "area_mu": 4.2},
        ctx,
    )
    assert updated.status.value == "success"
    assert patched_skill_sessions.get(PlantingUnit, unit_id).area_mu == Decimal("4.20")

    deleted = await ManagePlantingUnitsSkill().execute(
        {"action": "delete", "unit_id": unit_id},
        ctx,
    )
    assert deleted.status.value == "success"
    assert patched_skill_sessions.get(PlantingUnit, unit_id) is None


@pytest.mark.asyncio
async def test_crop_template_skills_list_update_delete(patched_skill_sessions, ctx):
    template = _create_template(patched_skill_sessions)

    listed = await GetCropTemplatesSkill().execute({}, ctx)
    assert listed.status.value == "success"
    assert "西瓜" in listed.reply

    updated = await ManageCropTemplatesSkill().execute(
        {"action": "update", "template_id": template.id, "name": "麒麟西瓜"},
        ctx,
    )
    assert updated.status.value == "success"
    assert patched_skill_sessions.get(CropTemplate, template.id).name == "麒麟西瓜"

    deleted = await ManageCropTemplatesSkill().execute(
        {"action": "delete", "template_id": template.id},
        ctx,
    )
    assert deleted.status.value == "success"
    assert patched_skill_sessions.get(CropTemplate, template.id) is None


@pytest.mark.asyncio
async def test_manage_farm_logs_updates_and_deletes_log(patched_skill_sessions, ctx):
    cycle = _create_cycle(patched_skill_sessions)
    log = FarmLog(
        farm_id=1,
        cycle_id=cycle.id,
        operation_type="浇水",
        operation_date=date(2026, 3, 3),
        note="上午",
    )
    patched_skill_sessions.add(log)
    patched_skill_sessions.commit()

    updated = await ManageFarmLogsSkill().execute(
        {"action": "update", "log_id": log.id, "operation_type": "施肥"},
        ctx,
    )
    assert updated.status.value == "success"
    assert patched_skill_sessions.get(FarmLog, log.id).operation_type == "施肥"

    deleted = await ManageFarmLogsSkill().execute(
        {"action": "delete", "log_id": log.id},
        ctx,
    )
    assert deleted.status.value == "success"
    assert patched_skill_sessions.get(FarmLog, log.id) is None


@pytest.mark.asyncio
async def test_delete_crop_cycle_removes_related_records(patched_skill_sessions, ctx):
    cycle = _create_cycle(patched_skill_sessions)
    patched_skill_sessions.add(
        CostRecord(
            farm_id=1,
            cycle_id=cycle.id,
            record_type="cost",
            category="种子",
            amount=Decimal("200"),
            record_date=date(2026, 3, 1),
        )
    )
    patched_skill_sessions.add(
        FarmLog(
            farm_id=1,
            cycle_id=cycle.id,
            operation_type="浇水",
            operation_date=date(2026, 3, 2),
        )
    )
    patched_skill_sessions.commit()

    result = await DeleteCropCycleSkill().execute({"cycle_id": cycle.id}, ctx)

    assert result.status.value == "success"
    assert patched_skill_sessions.get(CropCycle, cycle.id) is None
    assert patched_skill_sessions.query(FarmLog).count() == 0
    assert patched_skill_sessions.query(CostRecord).count() == 0


@pytest.mark.asyncio
async def test_user_settings_skills_read_and_update(patched_skill_sessions, ctx):
    result = await ManageUserSettingsSkill().execute(
        {
            "display_name": "老李",
            "default_city": "杭州",
            "default_lat": 30.25,
            "assistant_role": "creative",
        },
        ctx,
    )
    assert result.status.value == "success"

    user = patched_skill_sessions.get(User, "test-user-001")
    setting = patched_skill_sessions.query(UserSetting).filter_by(user_id=user.id).one()
    assert user.nickname == "老李"
    assert setting.default_city == "杭州"
    assert setting.default_lat == 30.25
    assert setting.assistant_role == "creative"

    read = await GetUserSettingsSkill().execute({}, ctx)
    assert read.status.value == "success"
    assert "老李" in read.reply
    assert "杭州" in read.reply
    assert "灵感创意型" in read.reply
