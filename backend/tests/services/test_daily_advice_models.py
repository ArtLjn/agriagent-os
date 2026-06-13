"""每日建议 v2 骨架构建测试。"""

from datetime import date

import pytest

from app.schemas.agent import (
    AdviceItem,
    DailyAdviceAction,
    DailyAdviceCompact,
    DailyAdviceDetailView,
    DailyAdviceOverview,
    DailyAdviceStep,
)
from app.services.daily_advice_models import (
    DAILY_ADVICE_CATEGORY_DEFAULTS,
    DailyAdviceCandidate,
    build_daily_advice_empty_response,
    build_daily_advice_item_skeletons,
    build_daily_advice_overview,
)


def _candidate(
    *,
    category: str = "weather",
    priority: int = 1,
    source_type: str = "weather_service",
    source_id: int | None = 12,
) -> DailyAdviceCandidate:
    return DailyAdviceCandidate(
        id=f"{category}-1",
        category=category,
        title_hint="高温错峰采收",
        detail_hint="今天最高温 36 度，建议避开中午高温时段安排采收。",
        priority=priority,
        due_date=date(2026, 6, 13),
        source_type=source_type,
        source_id=source_id,
        dedupe_key=f"{category}:1",
        reason="天气服务命中高温规则",
    )


def test_build_item_skeleton_maps_compact_detail_view_and_legacy_fields() -> None:
    skeleton = build_daily_advice_item_skeletons([_candidate()])[0]

    assert skeleton.id == "weather-1"
    assert skeleton.category == "weather"
    assert skeleton.source_type == "weather_service"
    assert skeleton.source_id == 12
    assert skeleton.compact.title == "高温错峰采收"
    assert skeleton.compact.subtitle == "今天最高温 36 度，建议避开中午高温时段安排采收。"
    assert skeleton.title == skeleton.compact.title
    assert skeleton.detail == skeleton.compact.subtitle
    assert skeleton.icon == skeleton.compact.icon
    assert skeleton.detail_view.title == "高温错峰采收"
    assert skeleton.detail_view.evidence[0].source_type == "weather_service"
    assert len(skeleton.detail_view.steps) >= 2
    assert any(action.type == "ask_agent" for action in skeleton.detail_view.actions)
    dumped = skeleton.model_dump()
    assert dumped["compact"]["title"] == skeleton.title
    assert dumped["detail"] == skeleton.compact.subtitle
    assert dumped["detail_view"]["title"] == skeleton.detail_view.title


def test_compact_input_overrides_legacy_fields() -> None:
    item = AdviceItem(
        title="旧标题",
        detail="旧详情字段会被覆盖",
        icon="OldIcon",
        priority=2,
        compact=DailyAdviceCompact(
            title="新标题",
            subtitle="这是 compact 提供的新详情字段内容",
            icon="NewIcon",
            icon_color="green",
        ),
    )

    assert item.title == "新标题"
    assert item.detail == "这是 compact 提供的新详情字段内容"
    assert item.icon == "NewIcon"


def test_short_candidate_builds_valid_skeleton() -> None:
    skeleton = build_daily_advice_item_skeletons(
        [
            DailyAdviceCandidate(
                id="short-1",
                category="record",
                title_hint="短建议",
                detail_hint="短",
                priority=3,
                due_date=None,
                source_type="record",
                source_id=None,
                dedupe_key="short",
                reason="短",
            )
        ]
    )[0]

    assert 15 <= len(skeleton.compact.subtitle) <= 50
    assert 20 <= len(skeleton.detail_view.description) <= 120


def test_empty_state_builder_returns_displayable_advice() -> None:
    response = build_daily_advice_empty_response(
        cycle_id=3,
        created_at=date(2026, 6, 13),
    )

    assert response.cycle_id == 3
    assert response.preview
    assert response.generation.mode == "empty"
    assert len(response.items) == 1
    item = response.items[0]
    assert item.id == "empty-today"
    assert item.compact.title == "今日暂无高优先级事项"
    assert item.detail == item.compact.subtitle
    assert item.detail_view.description
    assert len(item.detail_view.steps) >= 2


def test_overview_builder_generates_weather_work_order_and_pending_metrics() -> None:
    overview = build_daily_advice_overview(
        weather_summary="今日高温 36 度",
        work_order_count=13,
        pending_count=1,
    )

    assert 0 <= overview.score <= 100
    assert "今日高温 36 度" in overview.subtitle
    assert [metric.key for metric in overview.metrics] == [
        "weather",
        "work_order",
        "pending",
    ]
    assert overview.metrics[0].value == "今日高温 36 度"
    assert overview.metrics[1].value == "13项"
    assert overview.metrics[2].value == "1项"


def test_overview_builder_treats_negative_counts_as_zero() -> None:
    overview = build_daily_advice_overview(
        work_order_count=-3,
        pending_count=-1,
    )

    assert overview.subtitle == "天气平稳，今日有 0 项作业、0 项待处理"
    assert overview.metrics[1].value == "0项"
    assert overview.metrics[1].level == "normal"
    assert overview.metrics[2].value == "0项"
    assert overview.metrics[2].level == "normal"
    assert overview.score == build_daily_advice_overview().score


def test_default_overview_contains_required_metric_keys() -> None:
    overview = DailyAdviceOverview()

    assert [metric.key for metric in overview.metrics] == [
        "weather",
        "work_order",
        "pending",
    ]


def test_detail_view_actions_must_include_ask_agent() -> None:
    with pytest.raises(ValueError, match="ask_agent"):
        DailyAdviceDetailView(
            title="高温错峰采收",
            description="今天最高温较高，需要避开中午高温时段安排采收。",
            steps=[
                DailyAdviceStep(order=1, title="查看天气窗口"),
                DailyAdviceStep(order=2, title="调整作业时间"),
            ],
            actions=[DailyAdviceAction(type="create_work_order", label="生成作业单")],
        )


def test_detail_view_defaults_actions_to_ask_agent() -> None:
    detail_view = DailyAdviceDetailView(
        title="高温错峰采收",
        description="今天最高温较高，需要避开中午高温时段安排采收。",
        steps=[
            DailyAdviceStep(order=1, title="查看天气窗口"),
            DailyAdviceStep(order=2, title="调整作业时间"),
        ],
    )

    assert [action.type for action in detail_view.actions] == ["ask_agent"]
    assert detail_view.actions[0].label == "问问芽芽"


def test_category_defaults_cover_all_daily_advice_categories() -> None:
    expected_categories = {
        "weather",
        "operation",
        "crop_stage",
        "finance",
        "setup",
        "record",
    }

    assert set(DAILY_ADVICE_CATEGORY_DEFAULTS) == expected_categories
    for category in expected_categories:
        skeleton = build_daily_advice_item_skeletons(
            [_candidate(category=category, priority=2, source_type=category)]
        )[0]
        default = DAILY_ADVICE_CATEGORY_DEFAULTS[category]
        assert skeleton.compact.icon == default.icon
        assert skeleton.compact.icon_color == default.icon_color
        assert skeleton.level == default.level
        assert len(skeleton.detail_view.steps) >= 2
        assert any(action.type == "ask_agent" for action in skeleton.detail_view.actions)
