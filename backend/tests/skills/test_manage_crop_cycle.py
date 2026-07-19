"""manage_crop_cycle 聚合 Skill 测试。"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from skillify.core.context import SkillContext

from app.skills import get_skill_manager
from app.skills.registry import load_skill_registry
from app.agent.router.tool_selector import select_tools
from app.domains.finance.cost_models import CostRecord
from app.domains.planting.crop_models import CropTemplate, GrowthStage
from app.domains.planting.cycle_models import CropCycle, CycleStage
from app.domains.planting.log_models import FarmLog

_manage_mod = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")
_create_mod = _manage_mod
_query_cycles_mod = _manage_mod
_query_info_mod = _manage_mod
_update_mod = importlib.import_module(
    "app.skills.manage-crop-cycle.scripts.update_cycle"
)
_update_stage_mod = importlib.import_module(
    "app.skills.manage-crop-cycle.scripts.update_stage"
)
_delete_mod = _manage_mod

ManageCropCycleSkill = _manage_mod.ManageCropCycleSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


@pytest.fixture
def skill_session(monkeypatch, db_session):
    for module in (
        _query_cycles_mod,
        _query_info_mod,
        _update_mod,
        _update_stage_mod,
        _delete_mod,
    ):
        monkeypatch.setattr(module, "SessionLocal", lambda: db_session)
    return db_session


def _make_tools(names: list[str]):
    tools = []
    for name in names:
        tool = MagicMock(spec=["name"])
        tool.name = name
        tools.append(tool)
    return tools


def _make_template(db, farm_id: int = 1, name: str = "玉米") -> CropTemplate:
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


def _make_cycle(
    db,
    *,
    farm_id: int = 1,
    name: str = "夏季玉米",
    crop_name: str = "玉米",
    start_date: date = date(2026, 6, 1),
    status: str = "active",
) -> CropCycle:
    template = _make_template(db, farm_id=farm_id, name=crop_name)
    cycle = CropCycle(
        farm_id=farm_id,
        name=name,
        crop_template_id=template.id,
        start_date=start_date,
        total_area_mu=Decimal("10"),
        season="夏季",
        batch_note="原备注",
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
                is_current=True,
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


def test_manage_crop_cycle_metadata_and_schema():
    skill = ManageCropCycleSkill()
    schema = skill.parameters_schema()

    assert skill.name() == "manage_crop_cycle"
    assert schema["required"] == ["operation"]
    assert set(schema["properties"]["operation"]["enum"]) >= {
        "create_cycle",
        "query_cycles",
        "query_cycle_info",
        "update_cycle",
        "update_stage",
        "delete_cycle",
    }
    assert skill.metadata()["capability"] == "manage_crop_cycle"


@pytest.mark.asyncio
@patch.object(_create_mod, "SessionLocal")
@patch.object(_create_mod, "cycle_service")
@patch.object(_create_mod, "crop_service")
async def test_create_cycle_operation(mock_crop_svc, mock_cycle_svc, mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    template = MagicMock(id=7)
    mock_crop_svc.find_template_by_name.return_value = template
    cycle = MagicMock(name="秋季辣椒")
    cycle.stages = [
        MagicMock(
            name="育苗期",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 10),
            duration_days=10,
            order_index=0,
        )
    ]
    mock_cycle_svc.create_crop_cycle.return_value = cycle

    result = await ManageCropCycleSkill().execute(
        {"operation": "create_cycle", "crop_name": "辣椒", "season": "秋季"},
        ctx,
    )

    assert result.status.value == "success"
    assert "秋季辣椒" in result.reply
    cycle_create = mock_cycle_svc.create_crop_cycle.call_args[0][1]
    assert cycle_create.name == "秋季辣椒"
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_query_cycles_operation(skill_session, ctx):
    _make_cycle(skill_session, name="夏季水稻", crop_name="水稻")
    _make_cycle(
        skill_session,
        name="春季大豆",
        crop_name="大豆",
        status="finished",
        start_date=date(2026, 3, 1),
    )

    result = await ManageCropCycleSkill().execute({"operation": "query_cycles"}, ctx)

    assert result.status.value == "success"
    assert "茬口列表" in result.reply
    assert "夏季水稻" in result.reply
    assert "春季大豆" in result.reply


@pytest.mark.asyncio
async def test_query_cycle_info_operation(skill_session, ctx):
    cycle = _make_cycle(skill_session)

    result = await ManageCropCycleSkill().execute(
        {"operation": "query_cycle_info", "cycle_id": cycle.id},
        ctx,
    )

    assert result.status.value == "success"
    assert "茬口：夏季玉米" in result.reply
    assert "播种期 [当前]" in result.reply


@pytest.mark.asyncio
async def test_update_cycle_operation_recalculates_stages(skill_session, ctx):
    cycle = _make_cycle(skill_session)

    result = await ManageCropCycleSkill().execute(
        {
            "operation": "update_cycle",
            "cycle_id": cycle.id,
            "start_date": "2026-09-01",
        },
        ctx,
    )

    assert result.status.value == "success"
    updated = skill_session.get(CropCycle, cycle.id)
    stages = sorted(updated.stages, key=lambda stage: stage.order_index)
    assert updated.start_date == date(2026, 9, 1)
    assert stages[0].start_date == date(2026, 9, 1)
    assert "阶段日期已同步重算" in result.reply


@pytest.mark.asyncio
async def test_update_stage_operation_uses_update_handler(skill_session, ctx):
    cycle = _make_cycle(skill_session)

    result = await ManageCropCycleSkill().execute(
        {
            "operation": "update_stage",
            "cycle_id": cycle.id,
            "current_stage": "生长期",
        },
        ctx,
    )

    assert result.status.value == "success"
    stages = {
        stage.name: stage.is_current
        for stage in skill_session.get(CropCycle, cycle.id).stages
    }
    assert stages["播种期"] is False
    assert stages["生长期"] is True


@pytest.mark.asyncio
async def test_delete_cycle_operation_removes_related_records(skill_session, ctx):
    cycle = _make_cycle(skill_session)
    skill_session.add_all(
        [
            CostRecord(
                farm_id=1,
                cycle_id=cycle.id,
                record_type="cost",
                category="种子",
                amount=Decimal("200"),
                record_date=date(2026, 3, 1),
            ),
            FarmLog(
                farm_id=1,
                cycle_id=cycle.id,
                operation_type="浇水",
                operation_date=date(2026, 3, 2),
            ),
        ]
    )
    skill_session.commit()

    result = await ManageCropCycleSkill().execute(
        {"operation": "delete_cycle", "cycle_id": cycle.id},
        ctx,
    )

    assert result.status.value == "success"
    assert skill_session.get(CropCycle, cycle.id) is None
    assert skill_session.query(FarmLog).count() == 0
    assert skill_session.query(CostRecord).count() == 0


def test_legacy_aliases_resolve_to_manage_crop_cycle_operations():
    registry = load_skill_registry()

    expected = {
        "create_crop_cycle": "create_cycle",
        "get_crop_cycles": "query_cycles",
        "get_crop_cycle_info": "query_cycle_info",
        "update_crop_cycle": "update_cycle",
        "delete_crop_cycle": "delete_cycle",
    }
    for legacy_name, operation in expected.items():
        alias = registry.resolve_alias(legacy_name)
        assert alias is not None
        assert alias.capability == "manage_crop_cycle"
        assert alias.operation == operation


def test_llm_tool_surface_hides_retired_crop_cycle_crud_tools():
    manager = get_skill_manager()
    tool_names = {skill_def.name for skill_def in manager.list_skills()}

    assert "manage_crop_cycle" in tool_names
    assert {
        "create_crop_cycle",
        "get_crop_cycles",
        "get_crop_cycle_info",
        "update_crop_cycle",
        "delete_crop_cycle",
    }.isdisjoint(tool_names)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("创建春茬种植西瓜", ["manage_crop_cycle"]),
        ("把玉米茬口改成9月1开始", ["manage_crop_cycle"]),
        ("删除茬口12", ["manage_crop_cycle"]),
        ("我的茬口", ["manage_crop_cycle"]),
    ],
)
def test_tool_selector_routes_crop_cycle_intents_to_canonical_skill(message, expected):
    tools = _make_tools(["manage_crop_cycle", "get_farm_status"])

    assert select_tools(message, tools) == expected
