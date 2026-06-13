"""结构化报告 schema 测试。"""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.structured_report import StructuredReportData


def test_structured_report_data_accepts_a2ui_contract():
    """结构化报告支持 A2UI 约定字段和信源引用。"""
    report = StructuredReportData(
        report_type="weekly",
        period={
            "granularity": "week",
            "start": "2026-06-08",
            "end": "2026-06-14",
            "label": "2026年第24周",
        },
        summary={"text": "本周农事执行平稳", "highlights": ["完成追肥"]},
        metrics=[
            {"label": "净收支", "value": "1200.00", "unit": "元"},
            {"label": "农事次数", "value": "3", "unit": "次"},
        ],
        sections=[
            {
                "type": "weekly_snapshot",
                "title": "本周快照",
                "subtitle": "自然周复盘",
                "items": [{"label": "农事次数", "value": 3}],
                "data": {"chart": [{"name": "施肥", "value": 1}]},
                "source_ref_ids": ["farm_log:7"],
            }
        ],
        recommendations=[
            {"title": "下周巡田", "detail": "重点查看叶片长势", "priority": 2}
        ],
        source_summary=[{"source_type": "farm_log", "count": 1}],
        source_refs=[
            {
                "id": "farm_log:7",
                "source_type": "farm_log",
                "source_id": "7",
                "label": "6月10日追肥记录",
                "occurred_on": "2026-06-10",
            }
        ],
    )

    dumped = report.model_dump(mode="json")

    assert dumped["period"]["granularity"] == "week"
    assert dumped["metrics"][0]["label"] == "净收支"
    assert dumped["sections"][0]["type"] == "weekly_snapshot"
    assert dumped["sections"][0]["source_ref_ids"] == ["farm_log:7"]
    assert dumped["source_refs"][0]["occurred_on"] == "2026-06-10"


def test_structured_report_data_keeps_legacy_fields_compatible():
    """旧报告生成链路仍可使用 overview/cycles/costs/logs/advice/summary。"""
    report = StructuredReportData(
        report_type="monthly",
        period={
            "granularity": "month",
            "start": "2026-06-01",
            "end": "2026-06-30",
        },
        summary="月报生成完成",
        metrics=[],
        sections=[],
        recommendations=[],
        source_summary=[],
        source_refs=[],
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        overview={
            "active_cycles": 1,
            "log_count": 2,
            "total_cost": "100.00",
            "total_income": "300.00",
            "net_profit": "200.00",
        },
        cycles=[],
        costs=[],
        logs=[],
        advice=[{"title": "继续记录", "detail": "保持农事记录完整", "priority": 2}],
    )

    assert report.period_start == date(2026, 6, 1)
    assert report.overview is not None
    assert report.advice[0].title == "继续记录"


def test_structured_report_data_requires_a2ui_contract_fields():
    """新结构化报告不能只带 report_type 通过校验。"""
    with pytest.raises(ValidationError):
        StructuredReportData(report_type="weekly")
