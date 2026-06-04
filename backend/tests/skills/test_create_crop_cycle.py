"""建茬口 Skill (create_crop_cycle) 单元测试。"""

import importlib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from skillify.core.context import SkillContext

_create_cycle_mod = importlib.import_module(
    "app.agent.skills.create-crop-cycle.scripts.main"
)
CreateCropCycleSkill = _create_cycle_mod.CreateCropCycleSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def _make_template(template_id=1, name="辣椒", variety=None, stages=None) -> MagicMock:
    """构造模拟的 CropTemplate 对象。"""
    tmpl = MagicMock()
    tmpl.id = template_id
    tmpl.name = name
    tmpl.variety = variety
    tmpl.stages = stages or [
        MagicMock(name="育苗期", duration_days=30, order_index=0, key_tasks="播种"),
        MagicMock(name="生长期", duration_days=60, order_index=1, key_tasks="施肥"),
        MagicMock(name="采收期", duration_days=40, order_index=2, key_tasks="采摘"),
    ]
    return tmpl


def _make_cycle(cycle_id=1, name="秋季辣椒", start_date=None, stages=None) -> MagicMock:
    """构造模拟的 CropCycle 对象。"""
    cycle = MagicMock()
    cycle.id = cycle_id
    cycle.name = name
    cycle.start_date = start_date or date(2026, 5, 26)
    cycle.field_name = None
    cycle.stages = stages or [
        MagicMock(
            name="育苗期",
            start_date=date(2026, 5, 26),
            end_date=date(2026, 6, 24),
            duration_days=30,
            order_index=0,
        ),
        MagicMock(
            name="生长期",
            start_date=date(2026, 6, 25),
            end_date=date(2026, 8, 23),
            duration_days=60,
            order_index=1,
        ),
        MagicMock(
            name="采收期",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 10, 2),
            duration_days=40,
            order_index=2,
        ),
    ]
    return cycle


# ── 元信息测试 ──────────────────────────────────────────────────


class TestCreateCropCycleMeta:
    """Skill 元信息测试。"""

    def test_name(self):
        skill = CreateCropCycleSkill()
        assert skill.name() == "create_crop_cycle"

    def test_description_contains_trigger_words(self):
        skill = CreateCropCycleSkill()
        desc = skill.description()
        assert "创建" in desc
        assert "种植" in desc
        assert "茬口" in desc

    def test_parameters_schema_required_fields(self):
        skill = CreateCropCycleSkill()
        schema = skill.parameters_schema()
        assert "crop_name" in schema["properties"]
        assert "season" in schema["properties"]
        assert "start_date" in schema["properties"]
        assert "field_name" in schema["properties"]
        assert set(schema["required"]) == {"crop_name"}


# ── 正常场景 ──────────────────────────────────────────────────


class TestCreateCropCycleNormal:
    """正常建茬口场景。"""

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_basic_create_with_season(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """完整参数：帮我建个秋季辣椒茬口。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template(name="辣椒")
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle(name="秋季辣椒")
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "辣椒", "season": "秋季"},
            ctx,
        )

        assert result.status.value == "success"
        assert "秋季辣椒" in result.reply
        assert "育苗期" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_fuzzy_match_crop_name(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """模糊匹配：传入'朝天椒'匹配到'辣椒'模板。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template(name="辣椒")
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle(name="秋季辣椒")
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "朝天椒", "season": "秋季"},
            ctx,
        )

        assert result.status.value == "success"
        # 验证模糊搜索被调用
        mock_crop_svc.find_template_by_name.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_default_start_date_is_today(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """不传 start_date 时默认为今天。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle(start_date=date.today())
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        await skill.execute(
            {"crop_name": "辣椒", "season": "春季"},
            ctx,
        )

        call_args = mock_cycle_svc.create_crop_cycle.call_args
        cycle_create = call_args[0][1]
        assert cycle_create.start_date == date.today()

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_explicit_start_date(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """指定 start_date 时使用指定日期。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle(start_date=date(2026, 6, 1))
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        await skill.execute(
            {"crop_name": "辣椒", "season": "夏季", "start_date": "2026-06-01"},
            ctx,
        )

        call_args = mock_cycle_svc.create_crop_cycle.call_args
        cycle_create = call_args[0][1]
        assert cycle_create.start_date == date(2026, 6, 1)

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_uses_context_farm_id(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """使用 context 中的 farm_id。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle()
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        await skill.execute(
            {"crop_name": "辣椒", "season": "秋季"},
            ctx,
        )

        call_args = mock_cycle_svc.create_crop_cycle.call_args
        farm_id = call_args[1].get("farm_id") or call_args[0][2]
        assert farm_id == 1

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_cycle_name_format(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """茬口名称格式为 {season}{crop_name}。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle(name="春季西瓜")
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "西瓜", "season": "春季"},
            ctx,
        )

        assert result.status.value == "success"
        assert "春季西瓜" in result.reply

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_reply_contains_stage_list(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """成功回复中包含阶段列表。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle()
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "辣椒", "season": "秋季"},
            ctx,
        )

        assert "育苗期" in result.reply
        assert "生长期" in result.reply
        assert "采收期" in result.reply


# ── 无模板场景 ──────────────────────────────────────────────────


class TestCreateCropCycleNoTemplate:
    """无模板时的引导提示。"""

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_no_template_returns_need_clarify(
        self, mock_crop_svc, mock_session, ctx
    ):
        """无模板时返回 need_clarify，提示创建模板。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_crop_svc.find_template_by_name.return_value = None

        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "秋葵", "season": "秋季"},
            ctx,
        )

        assert result.status.value == "need_clarify"
        assert "秋葵" in result.reply
        assert "模板" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_no_template_does_not_call_create(
        self, mock_crop_svc, mock_session, ctx
    ):
        """无模板时不调用 cycle_service.create_crop_cycle。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_crop_svc.find_template_by_name.return_value = None

        # create_crop_cycle 不应该被调用，所以不 mock 它
        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "秋葵"},
            ctx,
        )

        assert result.status.value == "need_clarify"


# ── 异常与边界场景 ──────────────────────────────────────────────────


class TestCreateCropCycleError:
    """异常与边界场景。"""

    @pytest.mark.asyncio
    async def test_missing_crop_name(self, ctx):
        """缺少 crop_name 时返回错误。"""
        skill = CreateCropCycleSkill()
        result = await skill.execute({}, ctx)

        assert result.status.value == "failed"
        assert "作物" in result.reply

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_empty_crop_name(self, mock_crop_svc, mock_session, ctx):
        """crop_name 为空字符串时返回错误。"""
        skill = CreateCropCycleSkill()
        result = await skill.execute({"crop_name": ""}, ctx)

        assert result.status.value == "failed"
        assert "作物" in result.reply

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_invalid_date_falls_back_to_today(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """无效日期格式回退到今天。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle(start_date=date.today())
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        await skill.execute(
            {"crop_name": "辣椒", "start_date": "不是日期"},
            ctx,
        )

        call_args = mock_cycle_svc.create_crop_cycle.call_args
        cycle_create = call_args[0][1]
        assert cycle_create.start_date == date.today()

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_db_error_returns_failure(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """数据库异常时返回失败并关闭连接。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template
        mock_cycle_svc.create_crop_cycle.side_effect = Exception("DB error")

        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "辣椒", "season": "秋季"},
            ctx,
        )

        assert result.status.value == "failed"
        assert "失败" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_missing_context_farm_id_fails_without_db_access(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """context 无 farm_id 时必须失败，不能默认写到 1 号农场。"""
        empty_ctx = SkillContext()

        skill = CreateCropCycleSkill()
        result = await skill.execute(
            {"crop_name": "辣椒", "season": "秋季"},
            empty_ctx,
        )

        assert result.status.value == "failed"
        assert "农场上下文" in result.reply
        mock_session.assert_not_called()
        mock_crop_svc.find_template_by_name.assert_not_called()
        mock_cycle_svc.create_crop_cycle.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_create_cycle_mod, "SessionLocal")
    @patch.object(_create_cycle_mod, "cycle_service")
    @patch.object(_create_cycle_mod, "crop_service")
    async def test_default_season_when_not_provided(
        self, mock_crop_svc, mock_cycle_svc, mock_session, ctx
    ):
        """不传 season 时使用当前季节。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        template = _make_template()
        mock_crop_svc.find_template_by_name.return_value = template

        cycle = _make_cycle()
        mock_cycle_svc.create_crop_cycle.return_value = cycle

        skill = CreateCropCycleSkill()
        await skill.execute(
            {"crop_name": "辣椒"},
            ctx,
        )

        call_args = mock_cycle_svc.create_crop_cycle.call_args
        cycle_create = call_args[0][1]
        # 验证名称中包含某个季节
        assert any(s in cycle_create.name for s in ("春季", "夏季", "秋季", "冬季"))


# ── _format_reply 格式测试 ──────────────────────────────────────────────


class TestCropCycleFormatReply:
    """验证茬口创建回复使用 emoji + 有序列表格式。"""

    def test_reply_starts_with_success_emoji(self):
        """回复以 ✅ 开头。"""
        cycle = _make_cycle(name="春季西瓜")
        reply = _create_cycle_mod._format_reply(cycle)
        assert reply.startswith("✅")

    def test_reply_contains_cycle_name(self):
        """回复包含茬口名称。"""
        cycle = _make_cycle(name="春季西瓜")
        reply = _create_cycle_mod._format_reply(cycle)
        assert "春季西瓜" in reply

    def test_reply_contains_ordered_list(self):
        """阶段使用有序列表（1. 2. 3.）。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        assert "1." in reply
        assert "2." in reply
        assert "3." in reply

    def test_reply_date_format_m_d(self):
        """日期格式为 M/D。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        assert "5/26" in reply

    def test_reply_contains_duration_days(self):
        """每个阶段包含天数。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        assert "30天" in reply
        assert "60天" in reply

    def test_reply_contains_stage_emoji(self):
        """包含阶段规划标题 emoji。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        assert "📋" in reply
