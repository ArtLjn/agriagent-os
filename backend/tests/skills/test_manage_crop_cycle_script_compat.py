"""manage-crop-cycle 脚本归位兼容测试。"""

import importlib

import pytest
from skillify.core.context import SkillContext
from skillify.models.schemas import ResultStatus, SkillResult

pytestmark = pytest.mark.no_db


def test_small_operation_legacy_modules_alias_to_main_module() -> None:
    main = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")

    for module_name in (
        "create_cycle",
        "delete_cycle",
        "query_cycles",
        "query_cycle_info",
    ):
        legacy = importlib.import_module(
            f"app.skills.manage-crop-cycle.scripts.{module_name}"
        )

        assert legacy is main


def test_heavy_update_modules_keep_stable_real_modules() -> None:
    for module_name in ("update_cycle", "update_stage"):
        module = importlib.import_module(
            f"app.skills.manage-crop-cycle.scripts.{module_name}"
        )

        assert module.__name__ == f"app.skills.manage-crop-cycle.scripts.{module_name}"


def test_agent_legacy_small_operation_paths_share_main_module() -> None:
    main = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")
    legacy = importlib.import_module(
        "app.agent.skills.manage-crop-cycle.scripts.create_cycle"
    )

    assert legacy is main


@pytest.mark.asyncio
async def test_patch_on_legacy_small_operation_path_hits_main_dispatch(
    monkeypatch,
) -> None:
    main = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")
    legacy = importlib.import_module(
        "app.skills.manage-crop-cycle.scripts.create_cycle"
    )

    async def fake_create_cycle(params: dict, context) -> SkillResult:
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=f"patched:{params['operation']}:{context.farm_id}",
        )

    monkeypatch.setattr(legacy, "create_cycle", fake_create_cycle)

    result = await main.ManageCropCycleSkill().execute(
        {"operation": "create_cycle"},
        SkillContext(farm_id=3),
    )

    assert result.status is ResultStatus.SUCCESS
    assert result.reply == "patched:create_cycle:3"
