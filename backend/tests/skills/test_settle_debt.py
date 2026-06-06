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


def _mock_cost_record(
    amount,
    note,
    record_type="cost",
    category="化肥",
    settled_amount=None,
    settlement_status="settled",
):
    """构造模拟的赊账 CostRecord。"""
    total_amount = Decimal(str(amount))
    settled = Decimal(str(settled_amount if settled_amount is not None else amount))
    return MagicMock(
        id=1,
        farm_id=1,
        record_type=record_type,
        category=category,
        amount=total_amount,
        record_date=date(2026, 5, 20),
        note=note,
        settled_amount=settled,
        unsettled_amount=total_amount - settled,
        settlement_status=settlement_status,
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
    @patch.object(_settle_mod, "create_record", create=True)
    @patch("app.services.debt_service.settle_debt")
    async def test_partial_repayment(self, mock_settle, mock_create, mock_session, ctx):
        """还了老王1000块 — 部分还款。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_settle.return_value = _mock_cost_record(
            amount=Decimal("1000"),
            note=None,
            category="大棚膜",
        )

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王", "amount": 1000},
            ctx,
        )

        assert result.status.value == "success"
        assert "老王" in result.reply
        assert "1000" in result.reply
        mock_settle.assert_called_once_with(
            mock_db, farm_id=1, counterparty="老王", amount=Decimal("1000"), note=None
        )
        mock_create.assert_not_called()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record", create=True)
    @patch("app.services.debt_service.settle_debt")
    async def test_partial_repayment_with_note(
        self, mock_settle, mock_create, mock_session, ctx
    ):
        """还款带备注。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_settle.return_value = _mock_cost_record(
            amount=Decimal("500"),
            note=None,
        )

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "农资店", "amount": 500, "note": "第一期还款"},
            ctx,
        )

        assert result.status.value == "success"
        assert "第一期还款" not in result.reply
        mock_settle.assert_called_once_with(
            mock_db,
            farm_id=1,
            counterparty="农资店",
            amount=Decimal("500"),
            note="第一期还款",
        )
        mock_create.assert_not_called()
        mock_db.close.assert_called_once()


class TestSettleDebtFull:
    """全额还清场景：不传金额。"""

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record", create=True)
    @patch("app.services.debt_service.settle_debt")
    async def test_full_repayment_single_record(
        self, mock_settle, mock_create, mock_session, ctx
    ):
        """老王的钱全还了 — 单笔赊账全额还清。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_settle.return_value = _mock_cost_record(
            amount=Decimal("3000"),
            note=None,
        )

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王"},
            ctx,
        )

        assert result.status.value == "success"
        assert "3000" in result.reply
        mock_settle.assert_called_once_with(
            mock_db, farm_id=1, counterparty="老王", amount=None, note=None
        )
        mock_create.assert_not_called()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record", create=True)
    @patch("app.services.debt_service.settle_debt")
    async def test_full_repayment_multiple_records(
        self, mock_settle, mock_create, mock_session, ctx
    ):
        """全额还清时复用 service 返回的原始账单。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_settle.return_value = _mock_cost_record(
            amount=Decimal("2000"),
            note=None,
            category="大棚膜",
        )

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王"},
            ctx,
        )

        assert result.status.value == "success"
        assert "2000" in result.reply
        assert "大棚膜" in result.reply
        mock_settle.assert_called_once_with(
            mock_db, farm_id=1, counterparty="老王", amount=None, note=None
        )
        mock_create.assert_not_called()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch("app.services.debt_service.settle_debt")
    async def test_full_repayment_reply_does_not_label_cumulative_settled_as_current_amount(
        self, mock_settle, mock_session, ctx
    ):
        """全额结清部分已结账单时，不把累计已结金额说成本次还款金额。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_settle.return_value = _mock_cost_record(
            amount=Decimal("300"),
            note=None,
            settled_amount=Decimal("300"),
            settlement_status="settled",
        )

        skill = SettleDebtSkill()
        result = await skill.execute({"counterparty": "老王"}, ctx)

        assert result.status.value == "success"
        assert "本次还款" not in result.reply
        assert "已结" in result.reply
        assert "剩余" in result.reply
        assert "settled" in result.reply

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch("app.services.debt_service.settle_debt")
    async def test_overpayment_reply_does_not_show_original_amount_as_current_payment(
        self, mock_settle, mock_session, ctx
    ):
        """传入金额超过剩余金额时，不把原始超额金额展示成本次还款。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_settle.return_value = _mock_cost_record(
            amount=Decimal("500"),
            note=None,
            settled_amount=Decimal("500"),
            settlement_status="settled",
        )

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王", "amount": 999},
            ctx,
        )

        assert result.status.value == "success"
        assert "本次还款" not in result.reply
        assert "999" not in result.reply
        assert "已结" in result.reply
        assert "剩余" in result.reply


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
    @patch("app.services.debt_service.settle_debt")
    async def test_no_debt_records_found(self, mock_settle, mock_session, ctx):
        """找不到对应赊账记录时返回失败。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_settle.side_effect = ValueError("未找到 老王 的未结清账单")

        skill = SettleDebtSkill()
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
    @patch("app.services.debt_service.settle_debt")
    async def test_db_error_returns_failure(self, mock_settle, mock_session, ctx):
        """数据库异常时返回失败并关闭连接。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_settle.side_effect = Exception("DB connection lost")

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王", "amount": 1000},
            ctx,
        )

        assert result.status.value == "failed"
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record", create=True)
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
    @patch.object(_settle_mod, "create_record", create=True)
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
    @pytest.mark.parametrize("amount", [float("nan"), float("inf")])
    @patch.object(_settle_mod, "SessionLocal")
    @patch("app.services.debt_service.settle_debt")
    async def test_non_finite_amount_fails_without_db_access(
        self, mock_settle, mock_session, amount, ctx
    ):
        """非有限金额返回参数错误，不访问数据库和 service。"""
        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王", "amount": amount},
            ctx,
        )

        assert result.status.value == "failed"
        assert result.reply == "还款失败：金额无效，请提供大于0的金额。"
        mock_session.assert_not_called()
        mock_settle.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_settle_mod, "SessionLocal")
    @patch.object(_settle_mod, "create_record", create=True)
    async def test_missing_context_farm_id_fails_without_db_access(
        self, mock_create, mock_session
    ):
        """context 无 farm_id 时必须失败，不能默认写到 1 号农场。"""
        empty_ctx = SkillContext()

        skill = SettleDebtSkill()
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
    @patch.object(_settle_mod, "create_record", create=True)
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
    @patch.object(_settle_mod, "create_record", create=True)
    @patch("app.services.debt_service.settle_debt")
    async def test_repayment_updates_original_record_without_creating_income_record(
        self, mock_settle, mock_create, mock_session, ctx
    ):
        """还款更新原始账单，不创建 income/还款 记录。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        original_record = _mock_cost_record(
            amount=Decimal("2000"),
            note=None,
            category="化肥",
        )
        mock_settle.return_value = original_record

        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "农资店老王"},
            ctx,
        )

        assert result.status.value == "success"
        assert "农资店老王" in result.reply
        assert "2000" in result.reply
        mock_settle.assert_called_once_with(
            mock_db, farm_id=1, counterparty="农资店老王", amount=None, note=None
        )
        mock_create.assert_not_called()
