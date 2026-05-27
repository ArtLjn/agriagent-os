"""更新阶段 Skill (update_crop_stage) 单元测试。"""

import importlib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from skillify.core.context import SkillContext

_update_mod = importlib.import_module("app.agent.skills.update-crop-stage.scripts.main")
UpdateCropStageSkill = _update_mod.UpdateCropStageSkill


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
    """构造模拟的 CycleStage 对象。"""
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
    """构造模拟的 CropCycle 对象。"""
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


# ── 元信息测试 ──────────────────────────────────────────────────


class TestUpdateCropStageMeta:
    """Skill 元信息测试。"""

    def test_name(self):
        skill = UpdateCropStageSkill()
        assert skill.name() == "update_crop_stage"

    def test_description_contains_trigger_words(self):
        skill = UpdateCropStageSkill()
        desc = skill.description()
        assert "阶段" in desc
        assert "进" in desc

    def test_parameters_schema_required_fields(self):
        skill = UpdateCropStageSkill()
        schema = skill.parameters_schema()
        assert "cycle_id" in schema["properties"]
        assert "stage_name" in schema["properties"]
        assert set(schema["required"]) == {"stage_name"}


# ── 正常场景：指定 cycle_id ───────────────────────────────────────


class TestUpdateCropStageWithCycleId:
    """通过 cycle_id 直接更新茬口阶段。"""

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_update_to_specific_stage(self, mock_session, ctx):
        """指定 cycle_id 和 stage_name，成功更新阶段。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle = _make_cycle()
        # 模拟查询返回 cycle
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 1, "stage_name": "膨大期"},
            ctx,
        )

        assert result.status.value == "success"
        assert "膨大期" in result.reply
        assert "春季西瓜" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_clears_old_current_before_setting_new(self, mock_session, ctx):
        """更新时清除旧的 is_current，设置新的 is_current。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        stages = [
            _make_stage(1, "育苗期", 0, is_current=1),
            _make_stage(2, "膨大期", 1, is_current=0),
        ]
        cycle = _make_cycle(stages=stages)
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        skill = UpdateCropStageSkill()
        await skill.execute(
            {"cycle_id": 1, "stage_name": "膨大期"},
            ctx,
        )

        # 旧的 is_current 应被清除
        assert stages[0].is_current == 0
        # 新的阶段 is_current 应被设置
        assert stages[1].is_current == 1
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_cycle_not_found_with_cycle_id(self, mock_session, ctx):
        """指定 cycle_id 但茬口不存在。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 999, "stage_name": "膨大期"},
            ctx,
        )

        assert result.status.value == "failed"
        assert "999" in result.reply
        mock_db.close.assert_called_once()


# ── 正常场景：无 cycle_id，自动匹配 ──────────────────────────────


class TestUpdateCropStageAutoMatch:
    """无 cycle_id 时自动匹配活跃茬口。"""

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_single_active_cycle_auto_match(self, mock_session, ctx):
        """只有一个活跃茬口时自动匹配。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle = _make_cycle()
        # 第一次 query 返回 cycle（for get_crop_cycle），第二次返回活跃列表
        # 使用 .all() 返回活跃茬口列表
        mock_db.query.return_value.filter.return_value.all.return_value = [cycle]
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"stage_name": "膨大期"},
            ctx,
        )

        assert result.status.value == "success"
        assert "膨大期" in result.reply

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_multiple_active_cycles_returns_need_clarify(self, mock_session, ctx):
        """多个活跃茬口时返回 NEED_CLARIFY。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle1 = _make_cycle(cycle_id=1, name="春季西瓜")
        cycle2 = _make_cycle(cycle_id=2, name="春季辣椒")
        mock_db.query.return_value.filter.return_value.all.return_value = [
            cycle1,
            cycle2,
        ]

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"stage_name": "膨大期"},
            ctx,
        )

        assert result.status.value == "need_clarify"
        assert "春季西瓜" in result.reply
        assert "春季辣椒" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_no_active_cycles_returns_failed(self, mock_session, ctx):
        """没有活跃茬口时返回失败。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"stage_name": "膨大期"},
            ctx,
        )

        assert result.status.value == "failed"
        assert "活跃" in result.reply or "茬口" in result.reply
        mock_db.close.assert_called_once()


# ── 阶段名称匹配 ──────────────────────────────────────────────────


class TestUpdateCropStageNameMatch:
    """阶段名称匹配逻辑。"""

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_exact_match(self, mock_session, ctx):
        """精确匹配阶段名称。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle = _make_cycle()
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 1, "stage_name": "开花期"},
            ctx,
        )

        assert result.status.value == "success"
        assert "开花期" in result.reply

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_fuzzy_match_with_suffix(self, mock_session, ctx):
        """模糊匹配：传入'膨大'匹配到'膨大期'。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle = _make_cycle()
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 1, "stage_name": "膨大"},
            ctx,
        )

        assert result.status.value == "success"
        assert "膨大期" in result.reply

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_stage_not_found_in_cycle(self, mock_session, ctx):
        """茬口中没有该阶段名称。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle = _make_cycle()
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 1, "stage_name": "成熟期"},
            ctx,
        )

        assert result.status.value == "failed"
        assert "成熟期" in result.reply
        assert "阶段" in result.reply


# ── 异常与边界场景 ──────────────────────────────────────────────────


class TestUpdateCropStageError:
    """异常与边界场景。"""

    @pytest.mark.asyncio
    async def test_missing_stage_name(self, ctx):
        """缺少 stage_name 时返回错误。"""
        skill = UpdateCropStageSkill()
        result = await skill.execute({}, ctx)

        assert result.status.value == "failed"
        assert "阶段" in result.reply or "名称" in result.reply

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_empty_stage_name(self, mock_session, ctx):
        """stage_name 为空字符串时返回错误。"""
        skill = UpdateCropStageSkill()
        result = await skill.execute({"stage_name": ""}, ctx)

        assert result.status.value == "failed"

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_db_error_returns_failure(self, mock_session, ctx):
        """数据库异常时返回失败并关闭连接。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.query.side_effect = Exception("DB connection lost")

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 1, "stage_name": "膨大期"},
            ctx,
        )

        assert result.status.value == "failed"
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_no_context_farm_id_defaults_to_1(self, mock_session, ctx):
        """context 无 farm_id 时默认为 1。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle = _make_cycle()
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        empty_ctx = SkillContext()

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 1, "stage_name": "膨大期"},
            empty_ctx,
        )

        assert result.status.value == "success"

    @pytest.mark.asyncio
    @patch.object(_update_mod, "SessionLocal")
    async def test_cycle_with_empty_stages(self, mock_session, ctx):
        """茬口没有阶段数据时返回失败。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        cycle = _make_cycle(stages=[])
        mock_db.query.return_value.filter.return_value.first.return_value = cycle

        skill = UpdateCropStageSkill()
        result = await skill.execute(
            {"cycle_id": 1, "stage_name": "膨大期"},
            ctx,
        )

        assert result.status.value == "failed"
        assert "阶段" in result.reply
