"""manage_crop_cycle.update_stage 阶段更新能力测试。"""

import importlib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from skillify.core.context import SkillContext

from app.agent.skills import get_skill_manager

_main_mod = importlib.import_module("app.agent.skills.manage-crop-cycle.scripts.main")
_update_stage_mod = importlib.import_module(
    "app.agent.skills.manage-crop-cycle.scripts.update_stage"
)

ManageCropCycleSkill = _main_mod.ManageCropCycleSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def _make_stage(
    stage_id: int = 1,
    name: str = "育苗期",
    order_index: int = 0,
    is_current: int = 0,
    duration_days: int = 30,
) -> MagicMock:
    stage = MagicMock()
    stage.id = stage_id
    stage.name = name
    stage.order_index = order_index
    stage.is_current = is_current
    stage.duration_days = duration_days
    stage.start_date = date(2026, 5, 1)
    stage.end_date = date(2026, 5, 30)
    stage.key_tasks = "播种"
    return stage


def _make_cycle(
    cycle_id: int = 1,
    name: str = "春季西瓜",
    status: str = "active",
    stages: list | None = None,
) -> MagicMock:
    cycle = MagicMock()
    cycle.id = cycle_id
    cycle.name = name
    cycle.status = status
    if stages is None:
        stages = [
            _make_stage(1, "育苗期", 0, is_current=1),
            _make_stage(2, "伸蔓期", 1, is_current=0),
            _make_stage(3, "开花期", 2, is_current=0),
            _make_stage(4, "膨大期", 3, is_current=0),
            _make_stage(5, "采收期", 4, is_current=0),
        ]
    cycle.stages = stages
    return cycle


def test_update_crop_stage_not_exposed_as_standalone_llm_tool():
    manager = get_skill_manager()
    tool_names = {skill_def.name for skill_def in manager.list_skills()}

    assert "manage_crop_cycle" in tool_names
    assert "update_crop_stage" not in tool_names


def test_manage_crop_cycle_schema_accepts_update_stage_alias_param():
    schema = ManageCropCycleSkill().parameters_schema()

    assert "update_stage" in schema["properties"]["operation"]["enum"]
    assert "stage_name" in schema["properties"]


@pytest.mark.asyncio
@patch.object(_update_stage_mod, "SessionLocal")
async def test_update_stage_accepts_legacy_stage_name_param(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    cycle = _make_cycle()
    mock_db.query.return_value.filter.return_value.first.return_value = cycle

    result = await ManageCropCycleSkill().execute(
        {
            "operation": "update_stage",
            "cycle_id": 1,
            "stage_name": "膨大期",
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "膨大期" in result.reply
    assert "春季西瓜" in result.reply
    assert cycle.stages[0].is_current == 0
    assert cycle.stages[3].is_current == 1
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
@patch.object(_update_stage_mod, "SessionLocal")
async def test_update_stage_accepts_canonical_current_stage_param(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    cycle = _make_cycle()
    mock_db.query.return_value.filter.return_value.first.return_value = cycle

    result = await ManageCropCycleSkill().execute(
        {
            "operation": "update_stage",
            "cycle_id": 1,
            "current_stage": "开花期",
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "开花期" in result.reply
    assert cycle.stages[0].is_current == 0
    assert cycle.stages[2].is_current == 1


@pytest.mark.asyncio
@patch.object(_update_stage_mod, "SessionLocal")
async def test_update_stage_auto_matches_single_active_cycle(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    cycle = _make_cycle()
    mock_db.query.return_value.filter.return_value.all.return_value = [cycle]

    result = await ManageCropCycleSkill().execute(
        {"operation": "update_stage", "current_stage": "膨大期"},
        ctx,
    )

    assert result.status.value == "success"
    assert "膨大期" in result.reply


@pytest.mark.asyncio
@patch.object(_update_stage_mod, "SessionLocal")
async def test_update_stage_multiple_active_cycles_need_clarify(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    cycle1 = _make_cycle(cycle_id=1, name="春季西瓜")
    cycle2 = _make_cycle(cycle_id=2, name="春季辣椒")
    mock_db.query.return_value.filter.return_value.all.return_value = [cycle1, cycle2]

    result = await ManageCropCycleSkill().execute(
        {"operation": "update_stage", "current_stage": "膨大期"},
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "春季西瓜" in result.reply
    assert "春季辣椒" in result.reply
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_update_stage_missing_stage_name_fails(ctx):
    result = await ManageCropCycleSkill().execute({"operation": "update_stage"}, ctx)

    assert result.status.value == "failed"
    assert "阶段" in result.reply or "名称" in result.reply


@pytest.mark.asyncio
@patch.object(_update_stage_mod, "SessionLocal")
async def test_update_stage_missing_context_farm_id_fails_without_db_access(
    mock_session,
):
    result = await ManageCropCycleSkill().execute(
        {"operation": "update_stage", "cycle_id": 1, "current_stage": "膨大期"},
        SkillContext(),
    )

    assert result.status.value == "failed"
    assert "农场上下文" in result.reply
    mock_session.assert_not_called()


@pytest.mark.asyncio
@patch.object(_update_stage_mod, "SessionLocal")
async def test_update_stage_stage_not_found_reports_available_stages(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    cycle = _make_cycle()
    mock_db.query.return_value.filter.return_value.first.return_value = cycle

    result = await ManageCropCycleSkill().execute(
        {
            "operation": "update_stage",
            "cycle_id": 1,
            "current_stage": "成熟期",
        },
        ctx,
    )

    assert result.status.value == "failed"
    assert "成熟期" in result.reply
    assert "可用阶段" in result.reply
