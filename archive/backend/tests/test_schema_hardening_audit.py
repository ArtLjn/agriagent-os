"""Schema hardening 迁移前审计测试。"""

from datetime import date

from sqlalchemy import text

from app.domains.finance.cost_models import CostRecord
from app.domains.finance.cost_category_models import CostCategory
from app.domains.finance.cost_schemas import CostRecordCreate
from app.domains.finance.debt_service import create_debt_record
from app.domains.finance.cost_service import create_record
from app.ops.schema_hardening_audit import (
    run_post_migration_audit,
    run_preflight_audit,
)


def test_preflight_audit_reports_clean_database(db_session):
    """干净数据库应返回通过结果。"""
    category = CostCategory(
        farm_id=1,
        name="人工",
        type="cost",
        icon="worker",
    )
    db_session.add(category)
    db_session.add(
        CostRecord(
            farm_id=1,
            record_type="cost",
            category="人工",
            amount=200,
            record_date=date(2026, 6, 4),
        )
    )
    db_session.commit()

    report = run_preflight_audit(db_session)

    assert report.ok is True
    assert report.total_issue_count == 0
    assert report.category_match.unmatched_count == 0


def test_preflight_audit_reports_dangling_refs_invalid_json_and_category_miss(
    db_session,
):
    """迁移前审计应报告悬挂引用、非法 JSON 和无法匹配的分类。"""
    db_session.add(
        CostRecord(
            farm_id=1,
            record_type="cost",
            category="不存在分类",
            amount=300,
            record_date=date(2026, 6, 4),
        )
    )
    db_session.commit()
    db_session.execute(text("PRAGMA foreign_keys=OFF"))
    db_session.execute(
        text(
            """
            INSERT INTO trace_records (
                request_id, farm_id, node_type, node_name, input_data, token_usage
            ) VALUES (
                'req', 999, 'llm_call', 'test', '{bad json', '{"total": 10}'
            )
            """
        )
    )
    db_session.execute(
        text(
            """
            INSERT INTO token_daily_stats (
                user_id, farm_id, date, model, call_type
            ) VALUES (
                'missing-user', 999, '2026-06-04', 'qwen', 'chat'
            )
            """
        )
    )
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    db_session.commit()

    report = run_preflight_audit(db_session)

    assert report.ok is False
    assert report.dangling_refs.issue_count >= 2
    assert report.json_fields.issue_count == 1
    assert report.category_match.unmatched_count == 1
    assert report.total_issue_count >= 4


def test_preflight_audit_serializes_report_for_cli(db_session):
    """审计报告应能序列化为 CLI 友好的字典。"""
    report = run_preflight_audit(db_session)

    data = report.to_dict()

    assert data["ok"] is True
    assert data["total_issue_count"] == 0
    assert "dangling_refs" in data
    assert "json_fields" in data
    assert "category_match" in data


def test_cost_record_supports_category_fk_and_snapshot_columns():
    """CostRecord 模型应支持分类外键和历史分类快照。"""
    assert hasattr(CostRecord, "category_id")
    assert hasattr(CostRecord, "category_name_snapshot")


def test_create_record_writes_category_id_and_snapshot(db_session):
    """创建账务记录时应写入分类外键和历史快照。"""
    category = CostCategory(
        farm_id=1,
        name="人工",
        type="cost",
        icon="worker",
    )
    db_session.add(category)
    db_session.commit()

    record = create_record(
        db_session,
        CostRecordCreate(
            record_type="cost",
            category="人工",
            amount=200,
            record_date=date(2026, 6, 4),
        ),
        farm_id=1,
    )

    assert record.category_id == category.id
    assert record.category_name_snapshot == "人工"
    assert record.category == "人工"


def test_create_debt_record_writes_category_id_and_snapshot(db_session):
    """创建赊账记录时也应写入分类外键和历史快照。"""
    category = CostCategory(
        farm_id=1,
        name="化肥",
        type="cost",
        icon="flask",
    )
    db_session.add(category)
    db_session.commit()

    record = create_debt_record(
        db_session,
        CostRecordCreate(
            record_type="cost",
            category="化肥",
            amount=300,
            record_date=date(2026, 6, 4),
            counterparty="老王农资",
        ),
        farm_id=1,
    )

    assert record.category_id == category.id
    assert record.category_name_snapshot == "化肥"


def test_post_migration_audit_checks_columns_and_indexes(db_session):
    """迁移后校验应检查关键列和索引。"""
    report = run_post_migration_audit(db_session)

    data = report.to_dict()

    assert "schema_objects" in data
    assert all(
        issue["reason"] != "missing column" for issue in report.schema_objects.issues
    )
