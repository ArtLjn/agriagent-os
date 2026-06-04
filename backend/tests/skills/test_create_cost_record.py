"""记账 Skill (create_cost_record) 单元测试。"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from skillify.core.context import SkillContext

_create_cost_mod = importlib.import_module(
    "app.agent.skills.create-cost-record.scripts.main"
)
CreateCostRecordSkill = _create_cost_mod.CreateCostRecordSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


class TestCreateCostRecordSkillMeta:
    """Skill 元信息测试。"""

    def test_name(self):
        skill = CreateCostRecordSkill()
        assert skill.name() == "create_cost_record"

    def test_description_contains_trigger_words(self):
        skill = CreateCostRecordSkill()
        desc = skill.description()
        assert "记账" in desc
        assert "花了" in desc
        assert "买了" in desc

    def test_parameters_schema_required_fields(self):
        skill = CreateCostRecordSkill()
        schema = skill.parameters_schema()
        assert "amount" in schema["properties"]
        assert "category" in schema["properties"]
        assert set(schema["required"]) == {"amount", "category"}


class TestCreateCostRecordNormal:
    """正常记账场景。"""

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_basic_cost_record(self, mock_create, mock_session, ctx):
        """基本支出记账：昨天买了200块化肥。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note=None,
        )

        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {
                "amount": 200,
                "category": "化肥",
                "record_date": "2026-05-25",
            },
            ctx,
        )

        assert result.status.value == "success"
        assert "化肥" in result.reply
        assert "200" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_income_record(self, mock_create, mock_session, ctx):
        """收入记账：卖了番茄赚了5000。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(
            record_type="income",
            category="番茄销售",
            amount=Decimal("5000"),
            record_date=date(2026, 5, 26),
            note=None,
        )

        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {
                "amount": 5000,
                "category": "番茄销售",
                "record_type": "income",
            },
            ctx,
        )

        assert result.status.value == "success"
        assert "收入" in result.reply
        assert "5000" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_debt_record_with_counterparty(self, mock_create, mock_session, ctx):
        """赊账记账：在农资店老王那赊了3000块大棚膜。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(
            record_type="cost",
            category="大棚膜",
            amount=Decimal("3000"),
            record_date=date(2026, 5, 26),
            note="赊账-农资店老王",
        )

        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {
                "amount": 3000,
                "category": "大棚膜",
                "note": "赊账-农资店老王",
            },
            ctx,
        )

        assert result.status.value == "success"
        assert "大棚膜" in result.reply
        assert "3000" in result.reply
        assert "赊账" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_default_record_type_is_cost(self, mock_create, mock_session, ctx):
        """不传 record_type 时默认为 cost。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            record_date=date(2026, 5, 26),
            note=None,
        )

        skill = CreateCostRecordSkill()
        await skill.execute(
            {"amount": 100, "category": "化肥"},
            ctx,
        )

        call_args = mock_create.call_args
        record_create = call_args[0][1]
        assert record_create.record_type == "cost"

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_default_date_is_today(self, mock_create, mock_session, ctx):
        """不传 record_date 时默认为今天。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            record_date=date.today(),
            note=None,
        )

        skill = CreateCostRecordSkill()
        await skill.execute(
            {"amount": 100, "category": "化肥"},
            ctx,
        )

        call_args = mock_create.call_args
        record_create = call_args[0][1]
        assert record_create.record_date == date.today()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_uses_context_farm_id(self, mock_create, mock_session, ctx):
        """使用 context 中的 farm_id。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            record_date=date.today(),
            note=None,
        )

        skill = CreateCostRecordSkill()
        await skill.execute(
            {"amount": 100, "category": "化肥"},
            ctx,
        )

        call_args = mock_create.call_args
        assert call_args[1].get("farm_id") == 1 or call_args[0][2] == 1


class TestCreateCostRecordError:
    """异常与边界场景。"""

    @pytest.mark.asyncio
    async def test_missing_amount(self, ctx):
        """缺少 amount 时返回错误。"""
        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {"category": "化肥"},
            ctx,
        )

        assert result.status.value == "failed"
        assert "金额" in result.reply

    @pytest.mark.asyncio
    async def test_missing_category(self, ctx):
        """缺少 category 时返回错误。"""
        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {"amount": 100},
            ctx,
        )

        assert result.status.value == "failed"
        assert "分类" in result.reply

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_zero_amount(self, mock_create, mock_session, ctx):
        """金额为 0 时返回错误。"""
        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {"amount": 0, "category": "化肥"},
            ctx,
        )

        assert result.status.value == "failed"
        assert "金额" in result.reply
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_negative_amount(self, mock_create, mock_session, ctx):
        """金额为负数时返回错误。"""
        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {"amount": -50, "category": "化肥"},
            ctx,
        )

        assert result.status.value == "failed"
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_invalid_date_format(self, mock_create, mock_session, ctx):
        """无效日期格式回退到今天。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            record_date=date.today(),
            note=None,
        )

        skill = CreateCostRecordSkill()
        await skill.execute(
            {"amount": 100, "category": "化肥", "record_date": "不是日期"},
            ctx,
        )

        call_args = mock_create.call_args
        record_create = call_args[0][1]
        assert record_create.record_date == date.today()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_db_error_returns_failure(self, mock_create, mock_session, ctx):
        """数据库异常时返回失败并关闭连接。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.side_effect = Exception("DB connection lost")

        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {"amount": 100, "category": "化肥"},
            ctx,
        )

        assert result.status.value == "failed"
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_missing_context_farm_id_fails_without_db_access(
        self, mock_create, mock_session, ctx
    ):
        """context 无 farm_id 时必须失败，不能默认写到 1 号农场。"""
        empty_ctx = SkillContext()

        skill = CreateCostRecordSkill()
        result = await skill.execute(
            {"amount": 100, "category": "化肥"},
            empty_ctx,
        )

        assert result.status.value == "failed"
        assert "农场上下文" in result.reply
        mock_session.assert_not_called()
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_create_cost_mod, "SessionLocal")
    @patch.object(_create_cost_mod, "create_record")
    async def test_empty_params(self, mock_create, mock_session, ctx):
        """空参数时返回错误。"""
        skill = CreateCostRecordSkill()
        result = await skill.execute({}, ctx)

        assert result.status.value == "failed"
        mock_create.assert_not_called()


class TestCostRecordFormatReply:
    """验证记账回复使用 emoji + Markdown 格式。"""

    def test_reply_starts_with_money_emoji(self):
        """回复以 💰 开头。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert reply.startswith("💰")

    def test_reply_contains_bold_category(self):
        """回复包含加粗分类。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "**化肥**" in reply

    def test_reply_contains_amount(self):
        """回复包含金额。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "200元" in reply

    def test_income_reply_shows_income_label(self):
        """收入记录显示「收入」标签。"""
        record = MagicMock(
            record_type="income",
            category="番茄销售",
            amount=Decimal("5000"),
            record_date=date(2026, 5, 26),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "收入" in reply

    def test_debt_reply_shows_debt_label(self):
        """赊账记录显示「赊账」标签。"""
        record = MagicMock(
            record_type="cost",
            category="大棚膜",
            amount=Decimal("3000"),
            record_date=date(2026, 5, 26),
            note="赊账-农资店老王",
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "赊账" in reply

    def test_reply_contains_note_when_present(self):
        """有备注时显示备注。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note="赊账-农资店老王",
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "农资店老王" in reply
