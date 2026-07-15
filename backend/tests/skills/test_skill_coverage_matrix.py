"""Skill 覆盖矩阵测试。"""

import pytest

from app.agent.skill_coverage import (
    CoveragePriority,
    CoverageStatus,
    high_priority_unclassified_entries,
    list_skill_coverage_entries,
    summarize_skill_coverage,
)

pytestmark = pytest.mark.no_db


def test_coverage_matrix_has_required_fields_for_every_entry():
    entries = list_skill_coverage_entries()

    assert entries
    for entry in entries:
        assert entry.domain
        assert entry.operation
        assert entry.source
        assert entry.rationale


def test_high_priority_entries_are_classified():
    assert high_priority_unclassified_entries() == []


def test_worker_crud_is_covered_by_dedicated_skills():
    entries = list_skill_coverage_entries()
    worker_entry = next(
        entry
        for entry in entries
        if entry.domain == "worker" and entry.operation == "query_crud"
    )

    assert worker_entry.status == CoverageStatus.COVERED_BY_SKILL
    assert worker_entry.priority == CoveragePriority.HIGH
    assert worker_entry.skill_name == "get_workers|manage_workers"


def test_wage_save_update_is_covered_by_manage_wages():
    entries = list_skill_coverage_entries()
    wage_entry = next(
        entry
        for entry in entries
        if entry.domain == "labor" and entry.operation == "wage_save_update"
    )

    assert wage_entry.status == CoverageStatus.COVERED_BY_SKILL
    assert wage_entry.skill_name == "manage_wages"


def test_ordinary_high_priority_business_has_no_needs_skill_gap():
    gaps = [
        entry
        for entry in list_skill_coverage_entries()
        if entry.priority == CoveragePriority.HIGH
        and entry.status == CoverageStatus.NEEDS_SKILL
    ]

    assert gaps == []


@pytest.mark.parametrize(
    ("domain", "operation", "skill_name"),
    [
        ("cost", "delete_record", "manage_cost"),
        (
            "cost_category",
            "list_create_delete",
            "manage_cost_categories",
        ),
        (
            "planting_unit",
            "crud",
            "manage_planting_units",
        ),
        (
            "farm_log",
            "create_query_update_delete",
            "manage_farm_logs",
        ),
        (
            "user_settings",
            "get_update_settings",
            "manage_user_settings",
        ),
    ],
)
def test_new_business_gaps_are_covered(domain, operation, skill_name):
    entry = next(
        item
        for item in list_skill_coverage_entries()
        if item.domain == domain and item.operation == operation
    )

    assert entry.status == CoverageStatus.COVERED_BY_SKILL
    assert entry.skill_name == skill_name


def test_summary_reports_classified_statuses():
    summary = summarize_skill_coverage()

    assert summary[CoverageStatus.COVERED_BY_SKILL.value] >= 1
    assert summary[CoverageStatus.ADMIN_SKILL.value] >= 1


def test_coverage_matrix_exposes_capability_operations():
    entries = list_skill_coverage_entries()
    worker_entry = next(
        entry
        for entry in entries
        if entry.domain == "worker" and entry.operation == "query_crud"
    )

    assert worker_entry.legacy_skill_names == ["get_workers", "manage_workers"]
    assert worker_entry.capability_name == "manage_workers"
    assert worker_entry.capability_operations == [
        "manage_workers.query_workers",
        "manage_workers.manage_worker",
    ]
