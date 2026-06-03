"""测试所有 service 层写操作的事务回滚保护。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cost_service import create_record
from app.services.crop_service import create_crop_template
from app.services.cycle_service import (
    create_crop_cycle,
    update_stage,
    _recalculate_stages,
)
from app.services.log_service import create_log
import asyncio
from app.services.agent_service import (
    chat_with_agent,
    get_daily_advice,
    generate_report,
)


def _make_report_data():
    from app.services.report_data_service import ReportData

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

        from app.schemas.cost import CostRecordCreate

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

        from app.schemas.crop import CropTemplateCreate, GrowthStageCreate

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

    @patch("app.services.cycle_service.CropTemplate")
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

        from app.schemas.cycle import CropCycleCreate

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

    def test_recalculate_stages_rollback_on_commit_failure(self) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_db = MagicMock()
        mock_cycle = MagicMock()
        mock_cycle.stages = []
        mock_cycle.start_date = date(2025, 3, 15)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cycle
        mock_db.commit.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            _recalculate_stages(mock_db, cycle_id=1)

        mock_db.rollback.assert_called_once()


class TestLogServiceRollback:
    """测试日志服务事务回滚。"""

    def test_create_log_rollback_on_commit_failure(self) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB error")

        from app.schemas.log import FarmLogCreate

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

    @patch("app.services.agent_service.invoke_advisor")
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

    @patch("app.services.agent_service.invoke_advisor")
    @patch("app.services.agent_service.get_composer")
    def test_get_daily_advice_rollback_on_commit_failure(
        self, mock_get_composer: MagicMock, mock_invoke: MagicMock
    ) -> None:
        """commit 失败时应调用 rollback 并重新抛出异常。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = "建议"
        mock_db = MagicMock()
        # 缓存查询返回 None，使 get_daily_advice 走生成新建议分支
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.commit.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            asyncio.run(get_daily_advice(mock_db, cycle_id=1, farm_id=1))

        mock_db.rollback.assert_called_once()

    @patch("app.services.agent_service.get_llm")
    @patch("app.services.report_data_service.get_weekly_report_data")
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
