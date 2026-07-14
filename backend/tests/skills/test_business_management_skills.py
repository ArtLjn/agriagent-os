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

_manage_cost_mod = importlib.import_module("app.agent.skills.manage-cost.scripts.main")
_manage_cost_records_mod = importlib.import_module(
    "app.agent.skills.manage-cost.scripts.records"
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
_manage_cycles_mod = importlib.import_module(
    "app.agent.skills.manage-crop-cycle.scripts.main"
)
_manage_cycles_query_mod = importlib.import_module(
    "app.agent.skills.manage-crop-cycle.scripts.query_cycles"
)
_manage_templates_mod = importlib.import_module(
    "app.agent.skills.manage-crop-templates.scripts.main"
)
_manage_logs_mod = importlib.import_module(
    "app.agent.skills.manage-farm-logs.scripts.main"
)
_manage_cycles_delete_mod = importlib.import_module(
    "app.agent.skills.manage-crop-cycle.scripts.delete_cycle"
)
_get_settings_mod = importlib.import_module(
    "app.agent.skills.get-user-settings.scripts.main"
)
_manage_settings_mod = importlib.import_module(
    "app.agent.skills.manage-user-settings.scripts.main"
)

ManageCostSkill = _manage_cost_mod.ManageCostSkill
GetCostCategoriesSkill = _get_categories_mod.GetCostCategoriesSkill
ManageCostCategoriesSkill = _manage_categories_mod.ManageCostCategoriesSkill
GetPlantingUnitsSkill = _get_units_mod.GetPlantingUnitsSkill
ManagePlantingUnitsSkill = _manage_units_mod.ManagePlantingUnitsSkill
ManageCropCycleSkill = _manage_cycles_mod.ManageCropCycleSkill
ManageCropTemplatesSkill = _manage_templates_mod.ManageCropTemplatesSkill
ManageFarmLogsSkill = _manage_logs_mod.ManageFarmLogsSkill
GetUserSettingsSkill = _get_settings_mod.GetUserSettingsSkill
ManageUserSettingsSkill = _manage_settings_mod.ManageUserSettingsSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1, user_id="test-user-001")


@pytest.fixture
def patched_skill_sessions(monkeypatch, db_session):
    for module in (
        _manage_cost_records_mod,
        _get_categories_mod,
        _manage_categories_mod,
        _get_units_mod,
        _manage_units_mod,
        _manage_cycles_query_mod,
        _manage_templates_mod,
        _manage_logs_mod,
        _manage_cycles_delete_mod,
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


def _create_named_cycle(
    db,
    template: CropTemplate,
    *,
    name: str,
    status: str,
    start_date: date,
) -> CropCycle:
    cycle = CropCycle(
        farm_id=1,
        name=name,
        crop_template_id=template.id,
        start_date=start_date,
        status=status,
    )
    db.add(cycle)
    db.flush()
    db.add(
        CycleStage(
            cycle_id=cycle.id,
            name="播种期",
            start_date=start_date,
            end_date=start_date,
            duration_days=1,
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

    result = await ManageCostSkill().execute(
        {"operation": "delete_record", "record_id": record.id},
        ctx,
    )

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

    listed = await ManageCropTemplatesSkill().execute(
        {"operation": "query_templates"}, ctx
    )
    assert listed.status.value == "success"
    assert "西瓜" in listed.reply

    updated = await ManageCropTemplatesSkill().execute(
        {
            "operation": "manage_template",
            "action": "update",
            "template_id": template.id,
            "name": "麒麟西瓜",
        },
        ctx,
    )
    assert updated.status.value == "success"
    assert patched_skill_sessions.get(CropTemplate, template.id).name == "麒麟西瓜"

    deleted = await ManageCropTemplatesSkill().execute(
        {
            "operation": "manage_template",
            "action": "delete",
            "template_id": template.id,
        },
        ctx,
    )
    assert deleted.status.value == "success"
    assert patched_skill_sessions.get(CropTemplate, template.id) is None


@pytest.mark.asyncio
async def test_get_crop_cycles_lists_all_cycles(patched_skill_sessions, ctx):
    template = _create_template(patched_skill_sessions)
    _create_named_cycle(
        patched_skill_sessions,
        template,
        name="夏季水稻",
        status="active",
        start_date=date(2026, 6, 1),
    )
    _create_named_cycle(
        patched_skill_sessions,
        template,
        name="春季大豆",
        status="finished",
        start_date=date(2026, 3, 1),
    )

    listed = await ManageCropCycleSkill().execute({"operation": "query_cycles"}, ctx)

    assert listed.status.value == "success"
    assert "茬口列表" in listed.reply
    assert "夏季水稻" in listed.reply
    assert "春季大豆" in listed.reply
    assert "农场现状" not in listed.reply


@pytest.mark.asyncio
async def test_manage_farm_logs_updates_and_deletes_log(patched_skill_sessions, ctx):
    cycle = _create_cycle(patched_skill_sessions)
    cycle_id = cycle.id
    created = await ManageFarmLogsSkill().execute(
        {
            "operation": "create_log",
            "cycle_id": cycle_id,
            "operation_type": "除草",
            "operation_date": "2026-03-02",
            "note": "棚头",
        },
        ctx,
    )
    assert created.status.value == "success"
    assert (
        patched_skill_sessions.query(FarmLog)
        .filter_by(cycle_id=cycle_id, operation_type="除草")
        .one()
        .note
        == "棚头"
    )

    listed = await ManageFarmLogsSkill().execute(
        {"operation": "query_logs", "cycle_id": cycle_id, "days": 180},
        ctx,
    )
    assert listed.status.value == "success"
    assert "除草" in listed.reply

    log = FarmLog(
        farm_id=1,
        cycle_id=cycle_id,
        operation_type="浇水",
        operation_date=date(2026, 3, 3),
        note="上午",
    )
    patched_skill_sessions.add(log)
    patched_skill_sessions.commit()

    updated = await ManageFarmLogsSkill().execute(
        {
            "operation": "manage_log",
            "action": "update",
            "log_id": log.id,
            "operation_type": "施肥",
        },
        ctx,
    )
    assert updated.status.value == "success"
    assert patched_skill_sessions.get(FarmLog, log.id).operation_type == "施肥"

    deleted = await ManageFarmLogsSkill().execute(
        {"operation": "manage_log", "action": "delete", "log_id": log.id},
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

    result = await ManageCropCycleSkill().execute(
        {"operation": "delete_cycle", "cycle_id": cycle.id},
        ctx,
    )

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
