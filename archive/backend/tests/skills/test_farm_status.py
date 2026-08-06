"""get_farm_status Skill 单元测试。"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infra.skill_cache import clear_cache
from skillify.models.schemas import ResultStatus

pytestmark = pytest.mark.no_db

# kebab-case 目录名需要通过 importlib 导入
_mod = importlib.import_module("app.skills.farm-status.scripts.main")
FarmStatusSkill = _mod.FarmStatusSkill

SKILL_NAME = "get_farm_status"


@pytest.fixture(autouse=True)
def _clear_skill_cache():
    """每个测试前后清除 Skill 缓存，避免缓存命中干扰。"""
    clear_cache(SKILL_NAME)
    yield
    clear_cache(SKILL_NAME)


class TestFarmStatusMeta:
    """Skill 元信息测试。"""

    def test_name(self):
        skill = FarmStatusSkill()
        assert skill.name() == "get_farm_status"

    def test_description_contains_trigger_words(self):
        skill = FarmStatusSkill()
        desc = skill.description()
        assert "农场" in desc or "茬口" in desc

    def test_parameters_schema_no_required(self):
        skill = FarmStatusSkill()
        schema = skill.parameters_schema()
        assert schema["required"] == []


class TestFarmStatusExecution:
    """Skill 执行测试。"""

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "farm_context_service")
    async def test_returns_farm_summary(self, mock_fcs, mock_session_local):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_fcs.build_summary = AsyncMock(
            return_value="【农场现状】\n茬口：辣椒(开花期)\n本月花费：1250元"
        )

        skill = FarmStatusSkill()
        context = MagicMock(farm_id=1)
        result = await skill.execute({}, context)

        assert result.status == ResultStatus.SUCCESS
        assert "辣椒" in result.reply
        assert "1250" in result.reply
        mock_fcs.build_summary.assert_called_once_with(mock_db, farm_id=1)
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "farm_context_service")
    async def test_cache_is_isolated_by_farm_id(self, mock_fcs, mock_session_local):
        mock_session_local.side_effect = [MagicMock(), MagicMock()]
        mock_fcs.build_summary = AsyncMock(
            side_effect=["farm 1 summary", "farm 2 summary"]
        )

        skill = FarmStatusSkill()
        result1 = await skill.execute({}, MagicMock(farm_id=1))
        result2 = await skill.execute({}, MagicMock(farm_id=2))

        assert result1.reply == "farm 1 summary"
        assert result2.reply == "farm 2 summary"
        assert mock_fcs.build_summary.call_count == 2
        assert mock_fcs.build_summary.call_args_list[0].kwargs == {"farm_id": 1}
        assert mock_fcs.build_summary.call_args_list[1].kwargs == {"farm_id": 2}

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "farm_context_service")
    async def test_handles_db_error(self, mock_fcs, mock_session_local):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_fcs.build_summary = AsyncMock(side_effect=Exception("DB error"))

        skill = FarmStatusSkill()
        context = MagicMock(farm_id=1)
        result = await skill.execute({}, context)

        assert result.status == ResultStatus.FAILED
        assert "获取农场状态失败" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    async def test_missing_context_farm_id_fails_without_db_access(
        self, mock_session_local
    ):
        skill = FarmStatusSkill()
        context = MagicMock(farm_id=None)
        result = await skill.execute({}, context)

        assert result.status == ResultStatus.FAILED
        assert "缺少农场上下文" in result.reply
        mock_session_local.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    async def test_missing_context_farm_id_attr_fails_without_db_access(
        self, mock_session_local
    ):
        skill = FarmStatusSkill()
        context = MagicMock(spec=[])  # 无 farm_id 属性
        result = await skill.execute({}, context)

        assert result.status == ResultStatus.FAILED
        assert "缺少农场上下文" in result.reply
        mock_session_local.assert_not_called()
