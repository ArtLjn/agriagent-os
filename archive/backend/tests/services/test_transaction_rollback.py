"""测试所有 service 层写操作的事务回滚保护。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.finance.cost_service import create_record
from app.domains.planting.crop_service import create_crop_template
from app.domains.planting.cycle_service import (
    advance_stage,
    create_crop_cycle,
    update_stage,
    _recalculate_stages,
)
from app.domains.planting.log_service import create_log
import asyncio
from app.domains.conversation.agent_service import (
    chat_with_agent,
    get_daily_advice,
    generate_report,
)
from app.domains.conversation.daily_advice_models import DailyAdviceCandidate


def _make_report_data():
    from app.domains.farm.report_data_service import ReportData

    return ReportData(
        report_type="weekly",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        overview={
            "active_cycles": 1,
            "log_count": 0,
            "total_cost": "0",
            "total_income": "0",
            "net_profit": "0",
        },
        cycles=[],
        costs=[],
        logs=[],
    )


class TestCostServiceRollback:
    """测试成本服务事务回滚。"""

    def test_create_record_rollback_on_commit_failure(self) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB error")

        from app.domains.finance.cost_schemas import CostRecordCreate

        record = CostRecordCreate(
            cycle_id=1,
            record_type="cost",
            category="肥料",
            amount=Decimal("100.00"),
            record_date=date(2025, 3, 10),
        )

        with pytest.raises(RuntimeError, match="DB error"):
            create_record(mock_db, record, farm_id=1)

        mock_db.rollback.assert_called_once()


class TestCropServiceRollback:
    """测试作物服务事务回滚。"""

    def test_create_crop_template_rollback_on_commit_failure(self) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB error")

        from app.domains.planting.crop_schemas import CropTemplateCreate, GrowthStageCreate

        template = CropTemplateCreate(
            name="西瓜",
            variety="8424",
            stages=[
                GrowthStageCreate(
                    name="育苗期",
                    duration_days=30,
                    order_index=0,
                    key_tasks="温湿度管理",
                )
            ],
        )

        with pytest.raises(RuntimeError, match="DB error"):
            create_crop_template(mock_db, template, farm_id=1)

        mock_db.rollback.assert_called_once()


class TestCycleServiceRollback:
    """测试周期服务事务回滚。"""

    @patch("app.domains.planting.cycle_service.CropTemplate")
    def test_create_crop_cycle_rollback_on_commit_failure(
        self, mock_template_cls: MagicMock
    ) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB error")

        mock_template = MagicMock()
        mock_template.stages = []
        mock_template_cls.return_value = mock_template
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_template

        from app.domains.planting.cycle_schemas import CropCycleCreate

        cycle = CropCycleCreate(
            name="1号棚西瓜",
            crop_template_id=1,
            start_date=date(2025, 3, 15),
        )

        with pytest.raises(RuntimeError, match="DB error"):
            create_crop_cycle(mock_db, cycle, farm_id=1)

        mock_db.rollback.assert_called_once()

    def test_update_stage_rollback_on_commit_failure(self) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_db = MagicMock()
        mock_stage = MagicMock()
        mock_stage.cycle_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_stage
        mock_db.commit.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            update_stage(mock_db, stage_id=1, name="新名称")

        mock_db.rollback.assert_called_once()

    def test_recalculate_stages_does_not_commit_or_rollback(self) -> None:
        """阶段重算只更新内存对象，事务由外层写操作统一管理。"""
        mock_db = MagicMock()
        mock_cycle = MagicMock()
        mock_cycle.stages = []
        mock_cycle.start_date = date(2025, 3, 15)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cycle

        _recalculate_stages(mock_db, cycle_id=1)

        mock_db.commit.assert_not_called()
        mock_db.rollback.assert_not_called()

    @patch("app.domains.planting.cycle_service.invalidate_farm_context")
    def test_advance_stage_invalidates_context_after_commit(
        self, mock_invalidate: MagicMock
    ) -> None:
        """推进阶段成功提交后应清理上下文缓存。"""
        mock_db = MagicMock()
        current_stage = MagicMock()
        current_stage.order_index = 0
        current_stage.is_current = 1
        next_stage = MagicMock()
        next_stage.order_index = 1
        next_stage.is_current = 0
        mock_cycle = MagicMock()
        mock_cycle.stages = [current_stage, next_stage]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cycle

        advance_stage(mock_db, cycle_id=1, farm_id=9)

        mock_db.commit.assert_called_once()
        mock_invalidate.assert_called_once_with(9)
        mock_db.refresh.assert_called_once_with(mock_cycle)


class TestLogServiceRollback:
    """测试日志服务事务回滚。"""

    def test_create_log_rollback_on_commit_failure(self) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB error")

        from app.domains.planting.log_schemas import FarmLogCreate

        log = FarmLogCreate(
            cycle_id=1,
            operation_type="浇水",
            operation_date=date(2025, 3, 10),
        )

        with pytest.raises(RuntimeError, match="DB error"):
            create_log(mock_db, log, farm_id=1)

        mock_db.rollback.assert_called_once()


class TestAgentServiceRollback:
    """测试 Agent 服务事务回滚。"""

    @patch("app.domains.conversation.agent_service.invoke_advisor")
    def test_chat_with_agent_rollback_on_commit_failure(
        self, mock_invoke: MagicMock
    ) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_invoke.return_value = "建议"
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            asyncio.run(chat_with_agent(mock_db, "今天做什么？", farm_id=1))

        mock_db.rollback.assert_called_once()

    @patch("app.domains.conversation.agent_service.invoke_advisor")
    @patch("app.domains.conversation.agent_service.get_composer")
    @patch("app.domains.conversation.daily_advice_generation.collect_daily_advice_candidates")
    def test_get_daily_advice_rollback_on_commit_failure(
        self,
        mock_collect_candidates: AsyncMock,
        mock_get_composer: MagicMock,
        mock_invoke: AsyncMock,
    ) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_collect_candidates.return_value = [
            DailyAdviceCandidate(
                id="candidate-1",
                category="record",
                title_hint="补录今日农事",
                detail_hint="记录今日完成事项",
                priority=2,
                due_date=date.today(),
                source_type="test",
                source_id=None,
                dedupe_key="test-record",
                reason="rollback test",
            )
        ]
        mock_invoke.return_value = """
        {
          "cycle_id": null,
          "preview": "今日建议",
          "overview": {"metrics": []},
          "items": [
            {
              "id": "candidate-1",
              "category": "record",
              "level": "normal",
              "title": "补录今日农事",
              "summary": "记录今日完成事项",
              "steps": [],
              "actions": [],
              "evidence": []
            }
          ],
          "generation": {}
        }
        """
        mock_db = MagicMock()
        # 缓存查询返回 None，使 get_daily_advice 走生成新建议分支
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.commit.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            asyncio.run(get_daily_advice(mock_db, cycle_id=1, farm_id=1))

        mock_db.rollback.assert_called_once()

    @patch("app.domains.conversation.agent_service.get_llm")
    @patch("app.domains.farm.report_data_service.get_weekly_report_data")
    def test_generate_report_rollback_on_commit_failure(
        self, mock_report_data: AsyncMock, mock_get_llm: MagicMock
    ) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_report_data.return_value = _make_report_data()
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content='{"summary":"报告内容","advice_items":[]}')
        )
        mock_get_llm.return_value = mock_llm
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            asyncio.run(
                generate_report(mock_db, cycle_id=1, report_type="weekly", farm_id=1)
            )

        mock_db.rollback.assert_called_once()
