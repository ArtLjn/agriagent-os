"""manage-crop-cycle 脚本真实入口测试。"""

import importlib

import pytest
from skillify.core.context import SkillContext
from skillify.models.schemas import ResultStatus, SkillResult

pytestmark = pytest.mark.no_db


def test_small_operations_resolve_from_main_module() -> None:
    main = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")

    assert main.create_cycle.__module__ == main.__name__
    assert main.delete_cycle.__module__ == main.__name__
    assert main.query_cycles.__module__ == main.__name__
    assert main.query_cycle_info.__module__ == main.__name__


def test_heavy_update_modules_keep_stable_real_modules() -> None:
    for module_name in ("update_cycle", "update_stage"):
        module = importlib.import_module(
            f"app.skills.manage-crop-cycle.scripts.{module_name}"
        )

        assert module.__name__ == f"app.skills.manage-crop-cycle.scripts.{module_name}"


def test_main_entry_exports_small_operations() -> None:
    main = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")

    assert set(main.__all__) >= {
        "ManageCropCycleSkill",
        "create_cycle",
        "delete_cycle",
        "query_cycle_info",
        "query_cycles",
        "update_cycle",
        "update_stage",
    }


@pytest.mark.asyncio
async def test_patch_on_main_small_operation_hits_dispatch(
    monkeypatch,
) -> None:
    main = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")

    async def fake_create_cycle(params: dict, context) -> SkillResult:
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=f"patched:{params['operation']}:{context.farm_id}",
        )

    monkeypatch.setattr(main, "create_cycle", fake_create_cycle)

    result = await main.ManageCropCycleSkill().execute(
        {"operation": "create_cycle"},
        SkillContext(farm_id=3),
    )

    assert result.status is ResultStatus.SUCCESS
    assert result.reply == "patched:create_cycle:3"
