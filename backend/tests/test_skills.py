"""Skill 单元测试 — 通过 mock 数据库查询隔离外部依赖。"""

import importlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from skillify.core.context import SkillContext

pytestmark = pytest.mark.no_db

# 目录名含连字符，无法直接 import，使用 importlib 动态加载
_manage_cost_mod = importlib.import_module("app.agent.skills.manage-cost.scripts.main")
_cost_summary_mod = importlib.import_module(
    "app.agent.skills.manage-cost.scripts.summary"
)
_cost_analytics_mod = importlib.import_module(
    "app.agent.skills.manage-cost.scripts.analytics"
)
_crop_cycle_mod = importlib.import_module(
    "app.agent.skills.manage-crop-cycle.scripts.main"
)
_crop_cycle_query_info_mod = importlib.import_module(
    "app.agent.skills.manage-crop-cycle.scripts.query_cycle_info"
)
ManageCostSkill = _manage_cost_mod.ManageCostSkill
ManageCropCycleSkill = _crop_cycle_mod.ManageCropCycleSkill


class TestManageCostSkillMeta:
    def test_name(self):
        skill = ManageCostSkill()
        assert skill.name() == "manage_cost"

    def test_description_contains_trigger_words(self):
        skill = ManageCostSkill()
        desc = skill.description()
        assert "记账" in desc
        assert "查账" in desc
        assert "趋势分析" in desc
        assert "欠款查询" in desc

    def test_parameters_schema(self):
        skill = ManageCostSkill()
        schema = skill.parameters_schema()
        assert schema["required"] == ["operation"]
        assert "query_summary" in schema["properties"]["operation"]["enum"]
        assert "analyze_cost" in schema["properties"]["operation"]["enum"]
        assert "cycle_id" in schema["properties"]
        assert "group_by" in schema["properties"]
        assert "compare_period" in schema["properties"]


class TestCropCycleSkillMeta:
    def test_cycle_id_is_optional_for_safe_fallback(self):
        skill = ManageCropCycleSkill()
        schema = skill.parameters_schema()
        assert "cycle_id" in schema["properties"]
        assert schema["required"] == ["operation"]
        assert "query_cycle_info" in schema["properties"]["operation"]["enum"]


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

        skill = ManageCostSkill()
        result = await skill.execute(
            {"operation": "query_summary", "cycle_id": 99999},
            ctx,
        )

        assert "暂无成本或收入记录" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_cost_summary_mod, "SessionLocal")
    async def test_does_not_cache_empty_balance_result(self, mock_session, ctx):
        empty_chain = MagicMock()
        empty_chain.filter.return_value = empty_chain
        empty_chain.order_by.return_value = empty_chain
        empty_chain.all.return_value = []

        fresh_chain = MagicMock()
        fresh_chain.filter.return_value = fresh_chain
        fresh_chain.order_by.return_value = fresh_chain
        fresh_chain.all.return_value = [
            MockRecord(
                record_type="income",
                category="销售",
                amount=100,
                record_date="2026-06-05",
                note="",
                farm_id=1,
            )
        ]

        empty_db = MagicMock()
        empty_db.query.return_value = empty_chain
        fresh_db = MagicMock()
        fresh_db.query.return_value = fresh_chain
        mock_session.side_effect = [empty_db, fresh_db]

        skill = ManageCostSkill()

        first = await skill.execute({"operation": "query_summary"}, ctx)
        second = await skill.execute({"operation": "query_summary"}, ctx)

        assert "暂无成本或收入记录" in first.reply
        assert "总收入：100.00 元" in second.reply

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

        skill = ManageCostSkill()
        result = await skill.execute(
            {
                "operation": "query_summary",
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

        skill = ManageCostSkill()
        result = await skill.execute(
            {
                "operation": "query_summary",
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

        skill = ManageCostSkill()
        result = await skill.execute(
            {"operation": "query_summary", "group_by": "none"},
            ctx,
        )

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

        skill = ManageCostSkill()
        result = await skill.execute(
            {
                "operation": "analyze_cost",
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

        skill = ManageCostSkill()
        result = await skill.execute(
            {
                "operation": "analyze_cost",
                "date_from": "2025-02-01",
                "date_to": "2025-02-28",
                "compare_period": "last_month",
            },
            ctx,
        )

        assert "收支分析" in result.reply
        assert "对比期" in result.reply
        mock_db.close.assert_called_once()


class TestCropCycleSkill:
    @pytest.mark.asyncio
    @patch.object(_crop_cycle_query_info_mod, "SessionLocal")
    async def test_missing_context_farm_id_fails_without_db_access(self, mock_session):
        skill = ManageCropCycleSkill()

        result = await skill.execute({"operation": "query_cycle_info"}, SkillContext())

        assert result.status.value == "failed"
        assert "缺少农场上下文" in result.reply
        mock_session.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_crop_cycle_query_info_mod, "SessionLocal")
    async def test_missing_context_farm_id_attr_fails_without_db_access(
        self, mock_session
    ):
        skill = ManageCropCycleSkill()

        result = await skill.execute({"operation": "query_cycle_info"}, MagicMock(spec=[]))

        assert result.status.value == "failed"
        assert "缺少农场上下文" in result.reply
        mock_session.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_crop_cycle_query_info_mod, "SessionLocal")
    @patch.object(_crop_cycle_query_info_mod, "farm_context_service")
    async def test_missing_cycle_id_returns_farm_status_fallback(
        self, mock_fcs, mock_session, ctx
    ):
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_fcs.build_summary = AsyncMock(
            return_value="【农场现状】\n茬口：夏季玉米(播种期)"
        )

        skill = ManageCropCycleSkill()
        result = await skill.execute({"operation": "query_cycle_info"}, ctx)

        assert "未指定茬口 ID" in result.reply
        assert "夏季玉米" in result.reply
        mock_fcs.build_summary.assert_called_once_with(mock_db, farm_id=1)
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_crop_cycle_query_info_mod, "SessionLocal")
    async def test_cycle_id_query_filters_by_context_farm_id(self, mock_session, ctx):
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = query
        mock_session.return_value = mock_db

        skill = ManageCropCycleSkill()
        result = await skill.execute({"operation": "query_cycle_info", "cycle_id": 9}, ctx)

        assert result.status.value == "success"
        assert "未找到 ID 为 9" in result.reply
        filter_args = query.filter.call_args.args
        assert len(filter_args) == 2
        assert "crop_cycles.farm_id" in str(filter_args[1])
        mock_db.close.assert_called_once()
