"""还赊账 Skill (settle_debt) 单元测试。"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from skillify.core.context import SkillContext

_settle_mod = importlib.import_module("app.agent.skills.settle-debt.scripts.main")
SettleDebtSkill = _settle_mod.SettleDebtSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def _mock_cost_record(amount, note, record_type="cost", category="化肥"):
    """构造模拟的赊账 CostRecord。"""
    return MagicMock(
        id=1,
        farm_id=1,
        record_type=record_type,
        category=category,
        amount=Decimal(str(amount)),
        record_date=date(2026, 5, 20),
        note=note,
    )


class TestSettleDebtSkillMeta:
    """Skill 元信息测试。"""

    def test_name(self):
        skill = SettleDebtSkill()
        assert skill.name() == "settle_debt"

    def test_description_contains_trigger_words(self):
        skill = SettleDebtSkill()
        desc = skill.description()
        for word in ("还钱", "还账", "还款", "清账"):
            assert word in desc

    def test_parameters_schema_required_fields(self):
        skill = SettleDebtSkill()
        schema = skill.parameters_schema()
        assert "counterparty" in schema["properties"]
        assert "amount" in schema["properties"]
        assert "note" in schema["properties"]
        assert set(schema["required"]) == {"counterparty"}

    def test_parameters_schema_counterparty_description(self):
        skill = SettleDebtSkill()
        schema = skill.parameters_schema()
        desc = schema["properties"]["counterparty"]["description"]
        assert "老王" in desc or "债权人" in desc


class TestSettleDebtPartial:
    """部分还款场景：指定金额还款。"""

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_partial_repayment(self, mock_create, mock_session, ctx):
        """还了老王1000块 — 部分还款。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_create.return_value = MagicMock(
            record_type="income",
            category="还款",
            amount=Decimal("1000"),
            record_date=date(2026, 5, 26),
            note="还老王",
        )

        skill = SettleDebtSkill()
        with patch.object(
            SettleDebtSkill,
            "_find_debt_records",
            return_value=[
                _mock_cost_record(3000, "赊账-农资店老王", category="大棚膜")
            ],
        ):
            result = await skill.execute(
                {"counterparty": "老王", "amount": 1000},
                ctx,
            )

        assert result.status.value == "success"
        assert "老王" in result.reply
        assert "1000" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_partial_repayment_with_note(self, mock_create, mock_session, ctx):
        """还款带备注。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_create.return_value = MagicMock(
            record_type="income",
            category="还款",
            amount=Decimal("500"),
            record_date=date(2026, 5, 26),
            note="还农资店",
        )

        skill = SettleDebtSkill()
        with patch.object(
            SettleDebtSkill,
            "_find_debt_records",
            return_value=[_mock_cost_record(2000, "赊账-农资店")],
        ):
            result = await skill.execute(
                {"counterparty": "农资店", "amount": 500, "note": "第一期还款"},
                ctx,
            )

        assert result.status.value == "success"
        mock_db.close.assert_called_once()


class TestSettleDebtFull:
    """全额还清场景：不传金额。"""

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_full_repayment_single_record(self, mock_create, mock_session, ctx):
        """老王的钱全还了 — 单笔赊账全额还清。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_create.return_value = MagicMock(
            record_type="income",
            category="还款",
            amount=Decimal("3000"),
            record_date=date(2026, 5, 26),
            note="还老王（全额）",
        )

        skill = SettleDebtSkill()
        with patch.object(
            SettleDebtSkill,
            "_find_debt_records",
            return_value=[_mock_cost_record(3000, "赊账-老王")],
        ):
            result = await skill.execute(
                {"counterparty": "老王"},
                ctx,
            )

        assert result.status.value == "success"
        assert "3000" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_full_repayment_multiple_records(
        self, mock_create, mock_session, ctx
    ):
        """多笔赊账合并还清。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_create.return_value = MagicMock(
            record_type="income",
            category="还款",
            amount=Decimal("3500"),
            record_date=date(2026, 5, 26),
            note="还老王（全额）",
        )

        skill = SettleDebtSkill()
        with patch.object(
            SettleDebtSkill,
            "_find_debt_records",
            return_value=[
                _mock_cost_record(2000, "赊账-老王", category="大棚膜"),
                _mock_cost_record(1500, "赊账-老王", category="化肥"),
            ],
        ):
            result = await skill.execute(
                {"counterparty": "老王"},
                ctx,
            )

        assert result.status.value == "success"
        assert "3500" in result.reply
        # 验证创建的还款记录金额等于总额
        call_args = mock_create.call_args
        record_create = call_args[0][1]
        assert record_create.amount == Decimal("3500")
        mock_db.close.assert_called_once()


class TestSettleDebtError:
    """异常与边界场景。"""

    @pytest.mark.asyncio
    async def test_missing_counterparty(self, ctx):
        """缺少 counterparty 时返回错误。"""
        skill = SettleDebtSkill()
        result = await skill.execute({}, ctx)

        assert result.status.value == "failed"
        assert "债权人" in result.reply

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    async def test_no_debt_records_found(self, mock_session, ctx):
        """找不到对应赊账记录时返回失败。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        skill = SettleDebtSkill()
        with patch.object(SettleDebtSkill, "_find_debt_records", return_value=[]):
            result = await skill.execute(
                {"counterparty": "老王"},
                ctx,
            )

        assert result.status.value == "failed"
        assert (
            "没找到" in result.reply
            or "未找到" in result.reply
            or "找不到" in result.reply
        )
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_db_error_returns_failure(self, mock_create, mock_session, ctx):
        """数据库异常时返回失败并关闭连接。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.side_effect = Exception("DB connection lost")

        skill = SettleDebtSkill()
        with patch.object(
            SettleDebtSkill,
            "_find_debt_records",
            return_value=[_mock_cost_record(1000, "赊账-老王")],
        ):
            result = await skill.execute(
                {"counterparty": "老王", "amount": 1000},
                ctx,
            )

        assert result.status.value == "failed"
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_zero_amount_repayment(self, mock_create, mock_session, ctx):
        """还款金额为0时返回错误。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王", "amount": 0},
            ctx,
        )

        assert result.status.value == "failed"
        assert "金额" in result.reply
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_negative_amount_repayment(self, mock_create, mock_session, ctx):
        """还款金额为负数时返回错误。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王", "amount": -500},
            ctx,
        )

        assert result.status.value == "failed"
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_missing_context_farm_id_fails_without_db_access(
        self, mock_create, mock_session
    ):
        """context 无 farm_id 时必须失败，不能默认写到 1 号农场。"""
        empty_ctx = SkillContext()

        skill = SettleDebtSkill()
        with patch.object(
            SettleDebtSkill,
            "_find_debt_records",
            return_value=[_mock_cost_record(1000, "赊账-老王")],
        ):
            result = await skill.execute(
                {"counterparty": "老王"},
                empty_ctx,
            )

        assert result.status.value == "failed"
        assert "农场上下文" in result.reply
        mock_session.assert_not_called()
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_empty_counterparty(self, mock_create, mock_session, ctx):
        """counterparty 为空字符串时返回错误。"""
        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": ""},
            ctx,
        )

        assert result.status.value == "failed"
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record")
    async def test_repayment_creates_income_record(
        self, mock_create, mock_session, ctx
    ):
        """验证还款记录是 income 类型、category 为还款。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_create.return_value = MagicMock(
            record_type="income",
            category="还款",
            amount=Decimal("2000"),
            record_date=date(2026, 5, 26),
            note="还农资店老王（全额）",
        )

        skill = SettleDebtSkill()
        with patch.object(
            SettleDebtSkill,
            "_find_debt_records",
            return_value=[_mock_cost_record(2000, "赊账-农资店老王")],
        ):
            await skill.execute(
                {"counterparty": "农资店老王"},
                ctx,
            )

        call_args = mock_create.call_args
        record_create = call_args[0][1]
        assert record_create.record_type == "income"
        assert record_create.category == "还款"
        assert "还农资店老王" in record_create.note
