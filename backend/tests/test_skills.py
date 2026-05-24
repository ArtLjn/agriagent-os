"""Skill 单元测试 — 通过 mock 数据库查询隔离外部依赖。"""

import importlib
import pytest
from unittest.mock import MagicMock, patch

from skillify.core.context import SkillContext

# 目录名含连字符，无法直接 import，使用 importlib 动态加载
_cost_summary_mod = importlib.import_module("app.skills.cost-summary.scripts.main")
_cost_analytics_mod = importlib.import_module("app.skills.cost-analytics.scripts.main")
CostSummarySkill = _cost_summary_mod.CostSummarySkill
CostAnalyticsSkill = _cost_analytics_mod.CostAnalyticsSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


class MockRecord:
    """Mock CostRecord，用于替代真实 ORM 对象。"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestCostSummarySkill:
    @pytest.mark.asyncio
    @patch.object(_cost_summary_mod, "SessionLocal")
    async def test_empty_records(self, mock_session, ctx):
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = []

        mock_db = MagicMock()
        mock_db.query.return_value = chain
        mock_session.return_value = mock_db

        skill = CostSummarySkill()
        result = await skill.execute({"cycle_id": 99999}, ctx)

        assert "暂无成本或收入记录" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_cost_summary_mod, "SessionLocal")
    async def test_group_by_category(self, mock_session, ctx):
        records = [
            MockRecord(
                record_type="cost",
                category="化肥",
                amount=100,
                record_date="2025-03-01",
                note="",
                farm_id=1,
            ),
            MockRecord(
                record_type="cost",
                category="人工",
                amount=200,
                record_date="2025-03-02",
                note="",
                farm_id=1,
            ),
            MockRecord(
                record_type="income",
                category="销售",
                amount=500,
                record_date="2025-03-03",
                note="",
                farm_id=1,
            ),
        ]
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = records

        mock_db = MagicMock()
        mock_db.query.return_value = chain
        mock_session.return_value = mock_db

        skill = CostSummarySkill()
        result = await skill.execute(
            {
                "date_from": "2025-01-01",
                "date_to": "2025-12-31",
                "record_type": "all",
                "group_by": "category",
            },
            ctx,
        )

        assert "按分类汇总" in result.reply
        assert "化肥" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_cost_summary_mod, "SessionLocal")
    async def test_group_by_month(self, mock_session, ctx):
        records = [
            MockRecord(
                record_type="cost",
                category="化肥",
                amount=100,
                record_date="2025-03-01",
                note="",
                farm_id=1,
            ),
            MockRecord(
                record_type="cost",
                category="化肥",
                amount=200,
                record_date="2025-04-01",
                note="",
                farm_id=1,
            ),
        ]
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = records

        mock_db = MagicMock()
        mock_db.query.return_value = chain
        mock_session.return_value = mock_db

        skill = CostSummarySkill()
        result = await skill.execute(
            {
                "date_from": "2025-01-01",
                "date_to": "2025-12-31",
                "group_by": "month",
            },
            ctx,
        )

        assert "按月汇总" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_cost_summary_mod, "SessionLocal")
    async def test_simple_summary(self, mock_session, ctx):
        records = [
            MockRecord(
                record_type="cost",
                category="化肥",
                amount=100,
                record_date="2025-03-01",
                note="高钾肥",
                farm_id=1,
            ),
        ]
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = records

        mock_db = MagicMock()
        mock_db.query.return_value = chain
        mock_session.return_value = mock_db

        skill = CostSummarySkill()
        result = await skill.execute({"group_by": "none"}, ctx)

        assert "收支汇总" in result.reply
        assert "100.00" in result.reply
        mock_db.close.assert_called_once()


class TestCostAnalyticsSkill:
    @pytest.mark.asyncio
    @patch.object(_cost_analytics_mod, "SessionLocal")
    async def test_basic_analysis(self, mock_session, ctx):
        records = [
            MockRecord(
                record_type="cost",
                category="化肥",
                amount=100,
                record_date="2025-01-15",
                note="",
                farm_id=1,
            ),
            MockRecord(
                record_type="income",
                category="销售",
                amount=500,
                record_date="2025-01-20",
                note="",
                farm_id=1,
            ),
        ]
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.return_value = records

        mock_db = MagicMock()
        mock_db.query.return_value = chain
        mock_session.return_value = mock_db

        skill = CostAnalyticsSkill()
        result = await skill.execute(
            {
                "date_from": "2025-01-01",
                "date_to": "2025-01-31",
                "compare_period": "none",
            },
            ctx,
        )

        assert "收支分析" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_cost_analytics_mod, "SessionLocal")
    async def test_comparison(self, mock_session, ctx):
        records_current = [
            MockRecord(
                record_type="cost",
                category="化肥",
                amount=100,
                record_date="2025-02-15",
                note="",
                farm_id=1,
            ),
        ]
        records_previous = []

        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.side_effect = [records_current, records_previous]

        mock_db = MagicMock()
        mock_db.query.return_value = chain
        mock_session.return_value = mock_db

        skill = CostAnalyticsSkill()
        result = await skill.execute(
            {
                "date_from": "2025-02-01",
                "date_to": "2025-02-28",
                "compare_period": "last_month",
            },
            ctx,
        )

        assert "收支分析" in result.reply
        assert "对比期" in result.reply
        mock_db.close.assert_called_once()
