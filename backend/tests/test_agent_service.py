import json
from datetime import datetime
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.agent import ChatRequest
from app.services.daily_advice_models import DailyAdviceCandidate
from app.services.agent_service import (
    chat_with_agent,
    get_daily_advice,
    generate_report,
)


def _make_mock_db() -> MagicMock:
    """创建带 refresh side_effect 的 mock 数据库会话。"""
    mock_db = MagicMock()

    def _refresh_side_effect(record):
        record.created_at = datetime(2024, 1, 1, 12, 0, 0)

    mock_db.refresh.side_effect = _refresh_side_effect
    # 让缓存查询链式调用返回 None，确保走 LLM 路径
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None
    return mock_db


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


class TestChatWithAgent:
    """测试 Agent 对话服务。"""

    @pytest.mark.asyncio
    async def test_chat_with_agent_delegates_to_application_use_case(self) -> None:
        """验证兼容入口委托 Application 聊天用例。"""
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.id = 1
        farm.user_id = "user-1"

        with (
            patch(
                "app.services.agent_service._load_farm_for_application",
                return_value=farm,
            ) as mock_load_farm,
            patch(
                "app.services.agent_service.application_chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = MagicMock(reply="应用层回复")
            result = await chat_with_agent(
                mock_db,
                "你好",
                farm_id=1,
                cycle_id=2,
                session_id="sess-1",
                user_id="user-1",
                request_id="req-1",
            )

        assert result.reply == "应用层回复"
        mock_load_farm.assert_called_once_with(mock_db, 1)
        mock_chat.assert_awaited_once()
        delegated_db, delegated_request, delegated_farm = mock_chat.call_args.args
        assert delegated_db == mock_db
        assert delegated_request == ChatRequest(
            message="你好", cycle_id=2, session_id="sess-1"
        )
        assert delegated_farm.id == farm.id
        assert delegated_farm.user_id == "user-1"
        assert mock_chat.call_args.kwargs == {"request_id": "req-1"}

    @pytest.mark.asyncio
    async def test_chat_with_agent_backfills_user_id_on_loaded_farm(self) -> None:
        """验证旧入口传入 user_id 时回填无用户农场。"""
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.id = 1
        farm.user_id = None

        with (
            patch(
                "app.services.agent_service._load_farm_for_application",
                return_value=farm,
            ),
            patch(
                "app.services.agent_service.application_chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = MagicMock(reply="回复内容")
            result = await chat_with_agent(
                mock_db,
                "你好",
                farm_id=1,
                session_id="sess-123",
                user_id="user-1",
            )

        assert result.reply == "回复内容"
        mock_chat.assert_awaited_once()
        delegated_farm = mock_chat.call_args.args[2]
        assert delegated_farm.id == farm.id
        assert delegated_farm.user_id == "user-1"
        assert farm.user_id is None

    @pytest.mark.asyncio
    async def test_chat_with_agent_explicit_user_id_overrides_farm_user_id(
        self,
    ) -> None:
        """验证显式 user_id 优先于农场原有 user_id。"""
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.id = 1
        farm.user_id = "farm-user"

        with (
            patch(
                "app.services.agent_service._load_farm_for_application",
                return_value=farm,
            ),
            patch(
                "app.services.agent_service.application_chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = MagicMock(reply="回复内容")
            await chat_with_agent(
                mock_db,
                "你好",
                farm_id=1,
                session_id="sess-123",
                user_id="explicit-user",
            )

        delegated_farm = mock_chat.call_args.args[2]
        assert delegated_farm.user_id == "explicit-user"
        assert farm.user_id == "farm-user"

    @pytest.mark.asyncio
    async def test_load_farm_for_application_raises_when_missing(self) -> None:
        """验证兼容入口加载不到农场时抛出明确错误。"""
        from app.services.agent_service import _load_farm_for_application

        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="未找到农场: 1"):
            _load_farm_for_application(mock_db, 1)

        mock_db.query.assert_called_once()


class TestStreamChatWithAgent:
    """测试流式对话服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.stream_advisor")
    @patch("app.services.agent_service.save_message")
    @patch("app.services.agent_service.get_or_create_conversation")
    async def test_stream_with_session_id_saves_messages(
        self,
        mock_get_conv: MagicMock,
        mock_save_msg: MagicMock,
        mock_stream: MagicMock,
    ) -> None:
        """验证流式对话也保存消息到会话。"""
        mock_conv = MagicMock()
        mock_conv.id = 55
        mock_get_conv.return_value = mock_conv

        async def _fake_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        mock_stream.side_effect = _fake_stream
        mock_db = _make_mock_db()

        from app.services.agent_service import stream_chat_with_agent

        chunks = []
        async for chunk in stream_chat_with_agent(
            "问题", farm_id=1, db=mock_db, session_id="sess-stream"
        ):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]
        # 验证保存 user 消息（assistant 由调用方 agent.py 保存）
        mock_save_msg.assert_any_call(mock_db, 55, "user", "问题")

    @pytest.mark.asyncio
    async def test_stream_cycle_confirm_missing_template_creates_template_pending(
        self,
    ) -> None:
        """流式确认创建茬口但缺模板时，也应先请求确认创建模板。"""
        from app.infra.pending_actions import get_pending, remove_pending, store_pending
        from app.services.agent_service import stream_chat_with_agent

        remove_pending(1)
        store_pending(
            1,
            "create_crop_cycle",
            {"crop_name": "小麦"},
            original_input="我想种小麦",
        )

        with patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = "系统还没有小麦模板，要帮你创建一个吗？"
            chunks = []
            async for chunk in stream_chat_with_agent("确认", farm_id=1):
                chunks.append(chunk)

        reply = "".join(chunks)
        pending = get_pending(1)
        assert pending is not None
        assert pending.skill_name == "create_crop_template"
        assert pending.params == {"crop_name": "小麦"}
        assert pending.follow_up_skill_name == "create_crop_cycle"
        assert pending.follow_up_params == {"crop_name": "小麦"}
        assert "系统还没有小麦作物模板" in reply
        assert "确认创建作物模板" in reply
        assert "已执行：系统还没有" not in reply
        assert "crop_name" not in reply

        remove_pending(1)


class TestGetDailyAdvice:
    """测试每日建议服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.collect_daily_advice_candidates")
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_uses_ranked_candidates_for_generation(
        self,
        mock_invoke: AsyncMock,
        mock_get_composer: MagicMock,
        mock_collect_candidates: AsyncMock,
    ) -> None:
        """每日建议生成应接入结构化候选并保存候选元数据。"""
        candidate = DailyAdviceCandidate(
            id="operation:work_order:7",
            category="operation",
            title_hint="今日完成追肥",
            detail_hint="玉米拔节期作业单今日到期。",
            priority=1,
            due_date=date(2026, 6, 12),
            source_type="operation_work_order",
            source_id=7,
            dedupe_key="operation_work_order:7",
            reason="作业单日期进入今日建议窗口",
        )
        mock_collect_candidates.return_value = [candidate]
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '{"preview":"今日追肥","items":['
            '{"title":"追肥","detail":"按作业单完成追肥","priority":1,"icon":"🌱"}'
            "]}"
        )
        mock_db = _make_mock_db()

        await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        mock_collect_candidates.assert_awaited_once_with(mock_db, farm_id=1)
        variables = mock_get_composer.return_value.compose.call_args.kwargs["variables"]
        assert "今日行动候选" in variables["farm_context"]
        assert "今日完成追肥" in variables["farm_context"]

        saved_record = mock_db.add.call_args.args[0]
        saved_meta = json.loads(saved_record.meta)
        assert saved_meta["selected_candidates"][0]["id"] == candidate.id
        assert saved_meta["candidate_fingerprint"]

    @pytest.mark.asyncio
    @patch("app.services.farm_context_service.build_summary")
    @patch("app.services.agent_service.collect_daily_advice_candidates")
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_does_not_fallback_to_debt_summary(
        self,
        mock_invoke: AsyncMock,
        mock_get_composer: MagicMock,
        mock_collect_candidates: AsyncMock,
        mock_build_summary: AsyncMock,
    ) -> None:
        """无候选时不能把旧摘要里的欠账/未结人工喂给今日建议。"""
        mock_collect_candidates.return_value = []
        mock_build_summary.return_value = (
            "【农场现状】\n欠账：诸葛四郎未付100元、李海未付100元、朱7未付100元"
        )
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '[{"title":"巡田","detail":"今日暂无明确高优先级行动，例行观察即可",'
            '"priority":3,"icon":"📋"}]'
        )
        mock_db = _make_mock_db()

        await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        mock_build_summary.assert_not_awaited()
        variables = mock_get_composer.return_value.compose.call_args.kwargs["variables"]
        assert variables["farm_context"] == "今日无明确高优先级行动候选。"
        assert "欠账" not in variables["farm_context"]
        assert "未付" not in variables["farm_context"]
        assert "诸葛四郎" not in variables["farm_context"]

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_returns_structured_items(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证每日建议生成结构化 items 并保存（旧数组格式）。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '[{"title":"施肥","detail":"生长期需追肥","priority":1,"icon":"🌱"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "施肥"
        assert result.preview == ""
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_passes_trusted_user_context(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """每日建议调用 Agent 时应携带可信 user_id，避免 quota 身份拦截。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '[{"title":"巡田","detail":"检查长势","priority":1,"icon":"📋"}]'
        )
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.user_id = "user-1"
        mock_db.query.return_value.filter.return_value.first.return_value = farm

        await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        mock_invoke.assert_awaited_once_with(
            "daily prompt",
            farm_id=1,
            db=mock_db,
            user_id="user-1",
            call_type="daily_advice",
        )

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_new_format_with_preview(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证新格式（含 preview + items）正确解析。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '{"preview":"今日需浇水","items":['
            '{"title":"浇水","detail":"土壤干燥需补水","priority":1,"icon":"💧"}'
            "]}"
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert result.preview == "今日需浇水"
        assert len(result.items) == 1
        assert result.items[0].title == "浇水"
        assert result.items[0].icon == "💧"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_old_format_backward_compatible(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证旧数组格式仍然兼容。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '[{"title":"除草","detail":"杂草影响生长","priority":2,"icon":"🌿"},'
            '{"title":"施肥","detail":"补充氮肥","priority":1,"icon":"🌱"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert result.preview == ""
        assert len(result.items) == 2
        # 按 priority 排序
        assert result.items[0].priority == 1
        assert result.items[0].title == "施肥"
        assert result.items[1].priority == 2
        assert result.items[1].title == "除草"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_fallback_on_plain_text(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证 LLM 返回纯文本时 fallback 为单条 item。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = "今日建议：施肥。"
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "今日农事建议"
        assert result.preview == ""
        # 向后兼容：advice property 返回拼接文本
        assert "今日建议：施肥。" in result.advice


class TestGenerateReport:
    """测试报告生成服务。"""

    @pytest.mark.asyncio
    @pytest.mark.no_db
    @patch("app.services.agent_service.get_llm")
    @patch("app.services.report_data_service.get_weekly_report_data")
    async def test_generate_report_returns_content(
        self, mock_report_data: AsyncMock, mock_get_llm: MagicMock
    ) -> None:
        """验证报告生成并保存。"""
        mock_report_data.return_value = _make_report_data()
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"summary":"报告内容...","advice_items":[]}'
            )
        )
        mock_get_llm.return_value = mock_llm
        mock_db = _make_mock_db()

        result = await generate_report(
            mock_db, farm_id=1, cycle_id=1, report_type="weekly"
        )

        assert "报告内容..." in result.content
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.no_db
    @patch("app.services.agent_service.get_llm")
    @patch("app.services.report_data_service.get_weekly_report_data")
    async def test_generate_report_ignores_llm_fact_overrides(
        self, mock_report_data: AsyncMock, mock_get_llm: MagicMock
    ) -> None:
        """LLM 只能补文案，不能覆盖后端确定性事实和信源。"""
        report_data = _make_report_data()
        report_data.period = {
            "start": "2026-06-01",
            "end": "2026-06-07",
            "label": "本周",
            "granularity": "week",
        }
        report_data.metrics = [{"label": "净收支", "value": "0", "unit": "元"}]
        report_data.sections = [
            {
                "type": "weekly_snapshot",
                "title": "本周快照",
                "data": {"net_profit": "0"},
                "source_ref_ids": ["cost_record:1"],
            }
        ]
        report_data.source_summary = [{"source_type": "cost_record", "count": 1}]
        report_data.source_refs = [
            {
                "id": "cost_record:1",
                "source_type": "cost_record",
                "source_id": 1,
                "label": "肥料支出 100 元",
                "occurred_on": "2026-06-02",
            }
        ]
        mock_report_data.return_value = report_data
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content=json.dumps(
                    {
                        "summary": {"text": "本周经营平稳"},
                        "highlights": [{"text": "完成一次成本复盘"}],
                        "metrics": [{"label": "净收支", "value": "9999"}],
                        "sections": [
                            {"type": "fake", "title": "模型伪造模块"}
                        ],
                        "source_refs": [
                            {
                                "id": "weather_service:fake",
                                "source_type": "weather_service",
                            }
                        ],
                        "recommendations": [
                            {
                                "title": "继续记录",
                                "detail": "保持农事和成本记录完整",
                                "priority": 2,
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        )
        mock_get_llm.return_value = mock_llm
        mock_db = _make_mock_db()

        result = await generate_report(mock_db, farm_id=1, report_type="weekly")

        assert result.structured_data is not None
        assert result.structured_data["metrics"][0]["label"] == "净收支"
        assert result.structured_data["metrics"][0]["value"] == "0"
        assert result.structured_data["sections"][0]["type"] == "weekly_snapshot"
        assert result.structured_data["sections"][0]["data"] == {"net_profit": "0"}
        assert result.structured_data["source_refs"][0]["id"] == "cost_record:1"
        assert result.structured_data["summary"]["text"] == "本周经营平稳"
        assert result.structured_data["summary"]["highlights"] == ["完成一次成本复盘"]
        assert result.structured_data["recommendations"][0]["title"] == "继续记录"

    @pytest.mark.asyncio
    @pytest.mark.no_db
    @patch("app.services.agent_service.get_llm")
    @patch("app.services.report_data_service.get_weekly_report_data")
    async def test_generate_report_rebuilds_facts_after_cycle_filter(
        self, mock_report_data: AsyncMock, mock_get_llm: MagicMock
    ) -> None:
        """带 cycle_id 的报告不会保留其他茬口的派生事实和信源。"""
        report_data = _make_report_data()
        report_data.period = {
            "start": "2026-06-01",
            "end": "2026-06-07",
            "label": "本周",
            "granularity": "week",
        }
        report_data.cycles = [
            {
                "cycle_id": 1,
                "name": "一号棚番茄",
                "field_name": "一号棚",
                "current_stage": "开花期",
                "progress_percent": 30,
                "period_log_count": 1,
                "total_stages": 2,
                "current_stage_index": 1,
                "days_elapsed": 10,
                "source_ref_ids": ["crop_cycle:1", "cycle_stage:10"],
            },
            {
                "cycle_id": 2,
                "name": "二号棚番茄",
                "field_name": "二号棚",
                "current_stage": "坐果期",
                "progress_percent": 50,
                "period_log_count": 1,
                "total_stages": 2,
                "current_stage_index": 2,
                "days_elapsed": 20,
                "source_ref_ids": ["crop_cycle:2", "cycle_stage:20"],
            },
        ]
        report_data.costs = [
            {
                "id": 1,
                "cycle_id": 1,
                "category": "农药",
                "amount": "80",
                "record_type": "cost",
                "record_date": date(2026, 6, 2),
            },
            {
                "id": 2,
                "cycle_id": 2,
                "category": "销售",
                "amount": "500",
                "record_type": "income",
                "record_date": date(2026, 6, 3),
            },
        ]
        report_data.logs = [
            {
                "id": 1,
                "cycle_id": 1,
                "operation_type": "打药",
                "operation_date": date(2026, 6, 2),
            },
            {
                "id": 2,
                "cycle_id": 2,
                "operation_type": "采收",
                "operation_date": date(2026, 6, 3),
            },
        ]
        report_data.operation_work_orders = [
            {
                "id": 1,
                "cycle_id": 1,
                "operation_type": "打药",
                "operation_date": date(2026, 6, 2),
                "scope_type": "cycle",
            },
            {
                "id": 2,
                "cycle_id": 2,
                "operation_type": "采收",
                "operation_date": date(2026, 6, 3),
                "scope_type": "cycle",
            },
        ]
        report_data.source_refs = [
            {"id": "crop_cycle:1", "source_type": "crop_cycle", "source_id": 1, "label": "一号棚番茄"},
            {"id": "cycle_stage:10", "source_type": "cycle_stage", "source_id": 10, "label": "开花期"},
            {"id": "cost_record:1", "source_type": "cost_record", "source_id": 1, "label": "农药 80元"},
            {"id": "farm_log:1", "source_type": "farm_log", "source_id": 1, "label": "打药"},
            {"id": "operation_work_order:1", "source_type": "operation_work_order", "source_id": 1, "label": "打药"},
            {"id": "crop_cycle:2", "source_type": "crop_cycle", "source_id": 2, "label": "二号棚番茄"},
            {"id": "cycle_stage:20", "source_type": "cycle_stage", "source_id": 20, "label": "坐果期"},
            {"id": "cost_record:2", "source_type": "cost_record", "source_id": 2, "label": "销售 500元"},
            {"id": "farm_log:2", "source_type": "farm_log", "source_id": 2, "label": "采收"},
            {"id": "operation_work_order:2", "source_type": "operation_work_order", "source_id": 2, "label": "采收"},
        ]
        mock_report_data.return_value = report_data
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content=json.dumps({"summary": "单茬口报告", "advice_items": []})
            )
        )
        mock_get_llm.return_value = mock_llm

        result = await generate_report(
            _make_mock_db(), farm_id=1, cycle_id=1, report_type="weekly"
        )

        source_ref_ids = {ref["id"] for ref in result.structured_data["source_refs"]}
        assert result.structured_data["overview"]["active_cycles"] == 1
        assert result.structured_data["overview"]["total_income"] == "0"
        assert result.structured_data["overview"]["total_cost"] == "80"
        assert "crop_cycle:1" in source_ref_ids
        assert "cost_record:1" in source_ref_ids
        assert "crop_cycle:2" not in source_ref_ids
        assert "cost_record:2" not in source_ref_ids

    @pytest.mark.asyncio
    @pytest.mark.no_db
    @patch("app.services.agent_service.get_llm")
    @patch("app.services.report_data_service.get_monthly_report_data")
    async def test_generate_monthly_cycle_report_does_not_mix_previous_period(
        self, mock_report_data: AsyncMock, mock_get_llm: MagicMock
    ) -> None:
        """带 cycle_id 的月报不会使用全农场上一周期对比。"""
        report_data = _make_report_data()
        report_data.report_type = "monthly"
        report_data.period = {
            "start": "2026-06-01",
            "end": "2026-06-30",
            "label": "本月",
            "granularity": "month",
        }
        report_data.cycles = [
            {
                "cycle_id": 1,
                "name": "一号棚番茄",
                "field_name": "一号棚",
                "current_stage": "开花期",
                "progress_percent": 30,
                "period_log_count": 0,
                "total_stages": 1,
                "current_stage_index": 1,
                "days_elapsed": 10,
                "source_ref_ids": ["crop_cycle:1"],
            }
        ]
        report_data.previous_period = {
            "period": {
                "granularity": "month",
                "start": date(2026, 5, 1),
                "end": date(2026, 5, 31),
            },
            "has_baseline": True,
            "metrics": {
                "total_cost": "999",
                "total_income": "888",
                "net_profit": "-111",
                "log_count": 99,
                "work_order_count": 99,
            },
            "changes": {"net_profit": "-111"},
        }
        report_data.source_refs = [
            {
                "id": "crop_cycle:1",
                "source_type": "crop_cycle",
                "source_id": 1,
                "label": "一号棚番茄",
            }
        ]
        mock_report_data.return_value = report_data
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content=json.dumps({"summary": "单茬口月报", "advice_items": []})
            )
        )
        mock_get_llm.return_value = mock_llm

        result = await generate_report(
            _make_mock_db(), farm_id=1, cycle_id=1, report_type="monthly"
        )

        comparison = next(
            section
            for section in result.structured_data["sections"]
            if section["type"] == "period_comparison"
        )
        assert comparison["data"]["has_baseline"] is False
        assert comparison["data"]["metrics"]["net_profit"] == "0"
        assert comparison["data"]["changes"] == {}
