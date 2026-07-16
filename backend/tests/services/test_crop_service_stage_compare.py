from types import SimpleNamespace

import pytest

from app.services import crop_service
from app.services.crop_service import _normalize_stages_for_compare


pytestmark = pytest.mark.no_db


def _stage(
    name: str,
    duration_days: int,
    key_tasks: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        duration_days=duration_days,
        key_tasks=key_tasks,
    )


def test_normalize_stages_for_compare_ignores_stage_order():
    left = [
        _stage("育苗期", 30, "控温"),
        _stage("定植期", 1, "浇定根水"),
    ]
    right = [
        _stage("定植期", 1, "浇定根水"),
        _stage("育苗期", 30, "控温"),
    ]

    assert _normalize_stages_for_compare(left) == _normalize_stages_for_compare(right)


def test_normalize_stages_for_compare_preserves_duplicate_stage_counts():
    repeated = [
        _stage("育苗期", 30, "控温"),
        _stage("育苗期", 30, "控温"),
    ]
    single = [_stage("育苗期", 30, "控温")]

    assert _normalize_stages_for_compare(repeated) != _normalize_stages_for_compare(
        single
    )
    assert _normalize_stages_for_compare(repeated) == (
        ("育苗期", 30, "控温"),
        ("育苗期", 30, "控温"),
    )


def test_normalize_stages_for_compare_normalizes_key_tasks_whitespace():
    left = [_stage("育苗期", 30, "  控温\t保湿\n遮阴  ")]
    right = [_stage("育苗期", 30, "控温 保湿 遮阴")]

    assert _normalize_stages_for_compare(left) == _normalize_stages_for_compare(right)


def test_stage_compare_does_not_depend_on_private_protocol():
    source = crop_service.__loader__.get_source(crop_service.__name__)

    assert source is not None
    assert "_ComparableStage" not in source
    assert "Protocol" not in source
