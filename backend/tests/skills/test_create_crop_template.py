"""创建作物模板 Skill 测试。"""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from skillify.core.context import SkillContext

_mod = importlib.import_module("app.agent.skills.create-crop-template.scripts.main")
CreateCropTemplateSkill = _mod.CreateCropTemplateSkill

pytestmark = pytest.mark.no_db


@pytest.fixture
def ctx() -> SkillContext:
    return SkillContext(farm_id=7)


def _stage(
    name: str,
    duration_days: int = 10,
    order_index: int = 0,
    key_tasks: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        duration_days=duration_days,
        order_index=order_index,
        key_tasks=key_tasks,
    )


def _template(template_id: int, stages: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(id=template_id, stages=stages)


def _llm_client_with_stages() -> MagicMock:
    message = SimpleNamespace(
        content=(
            '[{"name":"播种期","duration_days":7,"order_index":0,'
            '"key_tasks":"催芽播种"}]'
        )
    )
    choice = SimpleNamespace(message=message)
    response = SimpleNamespace(choices=[choice])
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.crop_service, "create_crop_template")
@patch.object(_mod.crop_service, "find_system_template_match")
@patch.object(_mod.crop_service, "find_exact_duplicate")
async def test_exact_duplicate_returns_existing_id_after_stage_generation(
    mock_find_duplicate,
    mock_find_system_match,
    mock_create,
    mock_session,
    ctx,
) -> None:
    """生成阶段后精确查重命中时返回已有模板 ID，不新建。"""
    db = MagicMock()
    mock_session.return_value = db
    existing = _template(
        42,
        [
            _stage("播种期", order_index=0),
            _stage("苗期", order_index=1),
        ],
    )
    mock_find_system_match.return_value = None
    mock_find_duplicate.return_value = existing
    ctx.llm_model = "test-model"
    ctx.llm_client = _llm_client_with_stages()

    result = await CreateCropTemplateSkill().execute(
        {"crop_name": "西瓜", "variety": "8424"},
        ctx,
    )

    assert result.status.value == "success"
    assert "已有完全相同的模版 #42" in result.reply
    assert "播种期→苗期" in result.reply
    mock_find_system_match.assert_called_once_with(db, "西瓜", "8424")
    mock_find_duplicate.assert_called_once()
    duplicate_call = mock_find_duplicate.call_args
    assert duplicate_call.kwargs["farm_id"] == 7
    assert duplicate_call.kwargs["name"] == "西瓜"
    assert duplicate_call.kwargs["variety"] == "8424"
    mock_create.assert_not_called()
    db.close.assert_called_once()


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.crop_service, "create_crop_template")
@patch.object(_mod.crop_service, "find_system_template_match")
@patch.object(_mod.crop_service, "find_exact_duplicate")
async def test_system_template_match_returns_need_clarify_without_llm_or_write(
    mock_find_duplicate,
    mock_find_system_match,
    mock_create,
    mock_session,
    ctx,
) -> None:
    """系统库精确命中时推荐导入，不调用 LLM 且不写库。"""
    db = MagicMock()
    mock_session.return_value = db
    system_template = _template(
        100,
        [
            _stage("播种期", order_index=0),
            _stage("拔节期", order_index=1),
        ],
    )
    mock_find_system_match.return_value = system_template
    ctx.llm_model = "test-model"
    ctx.llm_client = _llm_client_with_stages()

    result = await CreateCropTemplateSkill().execute({"crop_name": "玉米"}, ctx)

    assert result.status.value == "need_clarify"
    assert "系统库已有 玉米 的成熟模版" in result.reply
    assert "播种期→拔节期" in result.reply
    assert "要导入吗" in result.reply
    mock_find_system_match.assert_called_once_with(db, "玉米", None)
    ctx.llm_client.chat.completions.create.assert_not_called()
    mock_find_duplicate.assert_not_called()
    mock_create.assert_not_called()
    db.close.assert_called_once()


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.crop_service, "create_crop_template")
@patch.object(_mod.crop_service, "find_system_template_match")
@patch.object(_mod.crop_service, "find_exact_duplicate")
async def test_no_match_uses_llm_and_creates_template(
    mock_find_duplicate,
    mock_find_system_match,
    mock_create,
    mock_session,
    ctx,
) -> None:
    """无系统模板且无精确重复时使用 LLM 阶段并创建用户模板。"""
    db = MagicMock()
    mock_session.return_value = db
    mock_find_system_match.return_value = None
    mock_find_duplicate.return_value = None
    created = _template(88, [_stage("播种期", 7, 0, "催芽播种")])
    mock_create.return_value = created
    ctx.llm_model = "test-model"
    ctx.llm_client = _llm_client_with_stages()

    result = await CreateCropTemplateSkill().execute({"crop_name": "藜麦"}, ctx)

    assert result.status.value == "success"
    assert "藜麦模板已创建" in result.reply
    assert "播种期" in result.reply
    ctx.llm_client.chat.completions.create.assert_awaited_once()
    mock_find_duplicate.assert_called_once()
    mock_create.assert_called_once()
    create_call = mock_create.call_args
    assert create_call.kwargs["farm_id"] == 7
    template_create = create_call.args[1]
    assert template_create.name == "藜麦"
    assert template_create.stages[0].key_tasks == "催芽播种"
    db.close.assert_called_once()


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.crop_service, "find_system_template_match")
async def test_missing_context_rejects_before_opening_db(
    mock_find_system_match,
    mock_session,
) -> None:
    """缺少 farm_id 时拒绝执行，不打开 DB。"""
    result = await CreateCropTemplateSkill().execute(
        {"crop_name": "西瓜"},
        SkillContext(),
    )

    assert result.status.value == "failed"
    assert "缺少农场上下文" in result.reply
    mock_session.assert_not_called()
    mock_find_system_match.assert_not_called()
