"""Schema hardening 迁移前审计命令。"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.shared.database import SessionLocal
from app.models.agent_record import AgentRecord
from app.models.conversation import Conversation, ConversationMessage
from app.models.cost import CostRecord
from app.models.cost_category import CostCategory
from app.models.cycle import CropCycle
from app.models.farm import Farm
from app.models.feedback import FeedbackRecord
from app.models.token_stats import TokenDailyStats
from app.models.trace import TraceRecord
from app.models.user import User
from app.models.user_setting import UserSetting


@dataclass
class AuditSection:
    """迁移审计分组结果。"""

    name: str
    issues: list[dict[str, Any]] = field(default_factory=list)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "issue_count": self.issue_count,
            "issues": self.issues,
        }


@dataclass
class CategoryMatchSection(AuditSection):
    """账务分类匹配审计结果。"""

    @property
    def unmatched_count(self) -> int:
        return self.issue_count

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["unmatched_count"] = self.unmatched_count
        return data


@dataclass
class PreflightAuditReport:
    """Schema hardening 迁移前审计报告。"""

    dangling_refs: AuditSection
    json_fields: AuditSection
    category_match: CategoryMatchSection

    @property
    def total_issue_count(self) -> int:
        return (
            self.dangling_refs.issue_count
            + self.json_fields.issue_count
            + self.category_match.issue_count
        )

    @property
    def ok(self) -> bool:
        return self.total_issue_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_issue_count": self.total_issue_count,
            "dangling_refs": self.dangling_refs.to_dict(),
            "json_fields": self.json_fields.to_dict(),
            "category_match": self.category_match.to_dict(),
        }


@dataclass
class PostMigrationAuditReport:
    """Schema hardening 迁移后审计报告。"""

    schema_objects: AuditSection

    @property
    def total_issue_count(self) -> int:
        return self.schema_objects.issue_count

    @property
    def ok(self) -> bool:
        return self.total_issue_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_issue_count": self.total_issue_count,
            "schema_objects": self.schema_objects.to_dict(),
        }


def run_preflight_audit(db: Session) -> PreflightAuditReport:
    """运行 schema hardening 迁移前审计。"""
    return PreflightAuditReport(
        dangling_refs=_audit_dangling_refs(db),
        json_fields=_audit_json_fields(db),
        category_match=_audit_category_matches(db),
    )


def run_post_migration_audit(db: Session) -> PostMigrationAuditReport:
    """运行 schema hardening 迁移后审计。"""
    return PostMigrationAuditReport(schema_objects=_audit_schema_objects(db))


def _audit_schema_objects(db: Session) -> AuditSection:
    section = AuditSection(name="schema_objects")
    bind = db.get_bind()
    inspector = inspect(bind)

    required_columns = {
        "cost_records": {"category_id", "category_name_snapshot"},
        "trace_records": {
            "input_data",
            "output_data",
            "token_usage",
            "start_time",
            "end_time",
        },
        "token_daily_stats": {"date", "user_id"},
        "cycle_stages": {"is_current"},
    }
    for table_name, columns in required_columns.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column in sorted(columns - existing):
            section.issues.append(
                {
                    "table": table_name,
                    "column": column,
                    "reason": "missing column",
                }
            )

    required_indexes = {
        "cost_records": {
            "ix_cost_records_farm_date_deleted",
            "ix_cost_records_farm_type_date",
        },
        "crop_cycles": {"ix_crop_cycles_farm_status_start"},
        "farm_logs": {"ix_farm_logs_farm_operation_date"},
        "conversation_messages": {"ix_conversation_messages_conversation_created"},
        "trace_records": {"ix_trace_records_request_round_id"},
        "agent_records": {"ix_agent_records_farm_created"},
    }
    for table_name, indexes in required_indexes.items():
        existing = {index["name"] for index in inspector.get_indexes(table_name)}
        for index_name in sorted(indexes - existing):
            section.issues.append(
                {
                    "table": table_name,
                    "index": index_name,
                    "reason": "missing index",
                }
            )

    if bind.dialect.name != "sqlite":
        required_fks = {
            "cost_records": {"fk_cost_records_category_id"},
            "token_daily_stats": {"fk_token_daily_stats_farm_id"},
            "trace_records": {"fk_trace_records_farm_id"},
        }
        for table_name, fks in required_fks.items():
            existing = {
                fk["name"]
                for fk in inspector.get_foreign_keys(table_name)
                if fk["name"]
            }
            for fk_name in sorted(fks - existing):
                section.issues.append(
                    {
                        "table": table_name,
                        "foreign_key": fk_name,
                        "reason": "missing foreign key",
                    }
                )

    return section


def _audit_dangling_refs(db: Session) -> AuditSection:
    section = AuditSection(name="dangling_refs")

    _collect_missing_ref(
        section,
        db,
        CostRecord,
        CostRecord.farm_id,
        Farm.id,
        "cost_records",
        "farm_id",
    )
    _collect_missing_ref(
        section,
        db,
        CostRecord,
        CostRecord.cycle_id,
        CropCycle.id,
        "cost_records",
        "cycle_id",
        nullable=True,
    )
    _collect_missing_ref(
        section,
        db,
        AgentRecord,
        AgentRecord.farm_id,
        Farm.id,
        "agent_records",
        "farm_id",
    )
    _collect_missing_ref(
        section,
        db,
        AgentRecord,
        AgentRecord.conversation_id,
        Conversation.id,
        "agent_records",
        "conversation_id",
        nullable=True,
    )
    _collect_missing_ref(
        section,
        db,
        Conversation,
        Conversation.farm_id,
        Farm.id,
        "conversations",
        "farm_id",
    )
    _collect_missing_ref(
        section,
        db,
        ConversationMessage,
        ConversationMessage.conversation_id,
        Conversation.id,
        "conversation_messages",
        "conversation_id",
    )
    _collect_missing_ref(
        section,
        db,
        FeedbackRecord,
        FeedbackRecord.user_id,
        User.id,
        "feedback_records",
        "user_id",
    )
    _collect_missing_ref(
        section,
        db,
        FeedbackRecord,
        FeedbackRecord.conversation_message_id,
        ConversationMessage.id,
        "feedback_records",
        "conversation_message_id",
        nullable=True,
    )
    _collect_missing_ref(
        section,
        db,
        UserSetting,
        UserSetting.user_id,
        User.id,
        "user_settings",
        "user_id",
    )
    _collect_missing_ref(
        section,
        db,
        TokenDailyStats,
        TokenDailyStats.farm_id,
        Farm.id,
        "token_daily_stats",
        "farm_id",
    )
    _collect_missing_ref(
        section,
        db,
        TokenDailyStats,
        TokenDailyStats.user_id,
        User.id,
        "token_daily_stats",
        "user_id",
        nullable=True,
    )
    _collect_missing_ref(
        section,
        db,
        TraceRecord,
        TraceRecord.farm_id,
        Farm.id,
        "trace_records",
        "farm_id",
    )
    return section


def _collect_missing_ref(
    section: AuditSection,
    db: Session,
    model,
    local_column,
    remote_column,
    table_name: str,
    column_name: str,
    nullable: bool = False,
) -> None:
    query = db.query(model.id, local_column).outerjoin(
        remote_column.class_, local_column == remote_column
    )
    if nullable:
        query = query.filter(local_column.isnot(None))
    query = query.filter(remote_column.is_(None))
    for row_id, ref_value in query.limit(100).all():
        section.issues.append(
            {
                "table": table_name,
                "id": row_id,
                "column": column_name,
                "value": ref_value,
                "reason": "missing referenced row",
            }
        )


def _audit_json_fields(db: Session) -> AuditSection:
    section = AuditSection(name="json_fields")
    checks = [
        ("trace_records", "input_data"),
        ("trace_records", "output_data"),
        ("trace_records", "token_usage"),
        ("agent_records", "meta"),
        ("conversation_messages", "meta"),
        ("simulation_results", "errors_json"),
        ("simulation_results", "db_diff_json"),
        ("simulation_results", "extracted_claims_json"),
        ("simulation_results", "pending_action_json"),
        ("simulation_results", "expected_db_changes_json"),
    ]
    for table_name, attr_name in checks:
        rows = db.execute(text(f"SELECT id, {attr_name} FROM {table_name}")).all()
        for row_id, raw_value in rows:
            if raw_value in (None, ""):
                continue
            try:
                if isinstance(raw_value, str):
                    json.loads(raw_value)
            except (TypeError, ValueError):
                section.issues.append(
                    {
                        "table": table_name,
                        "id": row_id,
                        "column": attr_name,
                        "reason": "invalid json",
                    }
                )
    return section


def _audit_category_matches(db: Session) -> CategoryMatchSection:
    section = CategoryMatchSection(name="category_match")
    records = (
        db.query(
            CostRecord.id,
            CostRecord.farm_id,
            CostRecord.record_type,
            CostRecord.category,
        )
        .filter(CostRecord.deleted_at.is_(None))
        .all()
    )
    for record_id, farm_id, record_type, category_name in records:
        matched = (
            db.query(CostCategory.id)
            .filter(
                CostCategory.farm_id == farm_id,
                CostCategory.type == record_type,
                CostCategory.name == category_name,
            )
            .first()
        )
        if matched is None:
            section.issues.append(
                {
                    "table": "cost_records",
                    "id": record_id,
                    "farm_id": farm_id,
                    "record_type": record_type,
                    "category": category_name,
                    "reason": "category not found",
                }
            )
    return section


def main() -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="运行 schema hardening 迁移前审计")
    parser.add_argument(
        "--phase",
        choices=("pre", "post"),
        default="pre",
        help="审计阶段：pre=迁移前，post=迁移后",
    )
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = (
            run_preflight_audit(db)
            if args.phase == "pre"
            else run_post_migration_audit(db)
        )
    finally:
        db.close()

    indent = 2 if args.pretty else None
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=indent))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
