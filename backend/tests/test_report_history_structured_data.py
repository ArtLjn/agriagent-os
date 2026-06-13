"""报告历史结构化数据解析测试。"""

import json

from app.agent.application.history_use_case import parse_structured_data


def test_parse_structured_data_accepts_new_contract():
    """新结构包含 period/sections/source_refs 时可被历史接口返回。"""
    meta = json.dumps(
        {
            "report_type": "weekly",
            "period": {
                "granularity": "week",
                "start": "2026-06-08",
                "end": "2026-06-14",
            },
            "summary": {"text": "本周平稳"},
            "metrics": [{"label": "农事次数", "value": "1", "unit": "次"}],
            "sections": [
                {
                    "type": "weekly_snapshot",
                    "title": "本周快照",
                    "source_ref_ids": ["farm_log:1"],
                }
            ],
            "recommendations": [],
            "source_summary": [{"source_type": "farm_log", "count": 1}],
            "source_refs": [
                {
                    "id": "farm_log:1",
                    "source_type": "farm_log",
                    "source_id": "1",
                    "label": "追肥记录",
                }
            ],
        },
        ensure_ascii=False,
    )

    parsed = parse_structured_data(meta)

    assert parsed is not None
    assert parsed["period"]["granularity"] == "week"
    assert parsed["sections"][0]["source_ref_ids"] == ["farm_log:1"]


def test_parse_structured_data_accepts_legacy_overview_contract():
    """旧结构包含 overview 时仍作为结构化数据返回。"""
    meta = json.dumps({"report_type": "weekly", "overview": {"active_cycles": 1}})

    parsed = parse_structured_data(meta)

    assert parsed == {"report_type": "weekly", "overview": {"active_cycles": 1}}


def test_parse_structured_data_returns_none_for_null_or_invalid_meta():
    """空值、非法 JSON 和非报告结构均返回 None。"""
    assert parse_structured_data(None) is None
    assert parse_structured_data("") is None
    assert parse_structured_data("{bad json") is None
    assert parse_structured_data(json.dumps({"foo": "bar"})) is None
