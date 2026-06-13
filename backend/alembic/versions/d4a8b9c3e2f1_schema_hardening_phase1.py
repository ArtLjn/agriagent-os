"""schema hardening phase 1

Revision ID: d4a8b9c3e2f1
Revises: c6f4d9a2e8b1
Create Date: 2026-06-04 20:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "d4a8b9c3e2f1"
down_revision: Union[str, None] = "c6f4d9a2e8b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    _add_cost_category_columns(inspector)
    _backfill_cost_category(bind)
    _create_indexes(inspector)

    if dialect != "sqlite":
        _add_foreign_keys(inspector)
        _alter_mysql_types()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    if dialect != "sqlite":
        _drop_foreign_keys(inspector)
        _restore_mysql_types()

    _drop_indexes(inspector)
    _drop_cost_category_columns(inspector)


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_keys(inspector, table_name: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk["name"]}


def _matching_foreign_key_names(
    inspector,
    table_name: str,
    constrained_columns: list[str],
    referred_table: str,
) -> set[str]:
    result = set()
    for fk in inspector.get_foreign_keys(table_name):
        if (
            fk.get("referred_table") == referred_table
            and fk.get("constrained_columns") == constrained_columns
            and fk.get("name")
        ):
            result.add(fk["name"])
    return result


def _add_cost_category_columns(inspector) -> None:
    columns = _columns(inspector, "cost_records")
    if "category_id" not in columns:
        op.add_column(
            "cost_records", sa.Column("category_id", sa.Integer(), nullable=True)
        )
    if "category_name_snapshot" not in columns:
        op.add_column(
            "cost_records",
            sa.Column("category_name_snapshot", sa.String(length=50), nullable=True),
        )


def _drop_cost_category_columns(inspector) -> None:
    columns = _columns(inspector, "cost_records")
    if "category_name_snapshot" in columns:
        op.drop_column("cost_records", "category_name_snapshot")
    if "category_id" in columns:
        op.drop_column("cost_records", "category_id")


def _backfill_cost_category(bind) -> None:
    bind.execute(
        text(
            """
            UPDATE cost_records AS cr
            JOIN cost_categories AS cc
              ON cc.farm_id = cr.farm_id
             AND cc.name = cr.category
             AND cc.type = cr.record_type
            SET cr.category_id = cc.id,
                cr.category_name_snapshot = cc.name
            WHERE cr.deleted_at IS NULL
              AND cr.category_id IS NULL
            """
        )
        if bind.dialect.name == "mysql"
        else text(
            """
            UPDATE cost_records
            SET category_id = (
                    SELECT cc.id
                    FROM cost_categories AS cc
                    WHERE cc.farm_id = cost_records.farm_id
                      AND cc.name = cost_records.category
                      AND cc.type = cost_records.record_type
                    LIMIT 1
                ),
                category_name_snapshot = COALESCE(category_name_snapshot, category)
            WHERE deleted_at IS NULL
              AND category_id IS NULL
            """
        )
    )
    bind.execute(
        text(
            """
            UPDATE cost_records
            SET category_name_snapshot = category
            WHERE category_name_snapshot IS NULL
            """
        )
    )


def _create_indexes(inspector) -> None:
    index_specs = [
        (
            "cost_records",
            "ix_cost_records_farm_date_deleted",
            ["farm_id", "record_date", "deleted_at"],
        ),
        (
            "cost_records",
            "ix_cost_records_farm_type_date",
            ["farm_id", "record_type", "record_date"],
        ),
        (
            "crop_cycles",
            "ix_crop_cycles_farm_status_start",
            ["farm_id", "status", "start_date"],
        ),
        (
            "farm_logs",
            "ix_farm_logs_farm_operation_date",
            ["farm_id", "operation_date"],
        ),
        (
            "conversation_messages",
            "ix_conversation_messages_conversation_created",
            ["conversation_id", "created_at"],
        ),
        (
            "trace_records",
            "ix_trace_records_request_round_id",
            ["request_id", "round_index", "id"],
        ),
        ("agent_records", "ix_agent_records_farm_created", ["farm_id", "created_at"]),
    ]
    for table_name, index_name, columns in index_specs:
        if index_name not in _indexes(inspector, table_name):
            op.create_index(index_name, table_name, columns, unique=False)


def _drop_indexes(inspector) -> None:
    _ensure_fk_fallback_indexes(inspector)
    for table_name, index_name in [
        ("agent_records", "ix_agent_records_farm_created"),
        ("trace_records", "ix_trace_records_request_round_id"),
        ("conversation_messages", "ix_conversation_messages_conversation_created"),
        ("farm_logs", "ix_farm_logs_farm_operation_date"),
        ("crop_cycles", "ix_crop_cycles_farm_status_start"),
        ("cost_records", "ix_cost_records_farm_type_date"),
        ("cost_records", "ix_cost_records_farm_date_deleted"),
    ]:
        if index_name in _indexes(inspector, table_name):
            op.drop_index(index_name, table_name=table_name)


def _ensure_fk_fallback_indexes(inspector) -> None:
    fallback_specs = [
        ("agent_records", "ix_agent_records_farm_id", ["farm_id"]),
        (
            "conversation_messages",
            "ix_conversation_messages_conversation_id",
            ["conversation_id"],
        ),
        ("cost_records", "ix_cost_records_farm_id", ["farm_id"]),
        ("crop_cycles", "ix_crop_cycles_farm_id", ["farm_id"]),
        ("farm_logs", "ix_farm_logs_farm_id", ["farm_id"]),
    ]
    for table_name, index_name, columns in fallback_specs:
        if index_name not in _indexes(inspector, table_name):
            op.create_index(index_name, table_name, columns, unique=False)


def _add_foreign_keys(inspector) -> None:
    fk_specs = [
        (
            "cost_categories",
            "fk_cost_categories_farm_id",
            ["farm_id"],
            "farms",
            ["id"],
            "RESTRICT",
        ),
        (
            "cost_records",
            "fk_cost_records_category_id",
            ["category_id"],
            "cost_categories",
            ["id"],
            "RESTRICT",
        ),
        (
            "cost_records",
            "fk_cost_records_cycle_id",
            ["cycle_id"],
            "crop_cycles",
            ["id"],
            "SET NULL",
        ),
        (
            "feedback_records",
            "fk_feedback_records_user_id",
            ["user_id"],
            "users",
            ["id"],
            "RESTRICT",
        ),
        (
            "user_settings",
            "fk_user_settings_user_id",
            ["user_id"],
            "users",
            ["id"],
            "CASCADE",
        ),
        (
            "token_daily_stats",
            "fk_token_daily_stats_farm_id",
            ["farm_id"],
            "farms",
            ["id"],
            "RESTRICT",
        ),
        (
            "token_daily_stats",
            "fk_token_daily_stats_user_id",
            ["user_id"],
            "users",
            ["id"],
            "SET NULL",
        ),
        (
            "trace_records",
            "fk_trace_records_farm_id",
            ["farm_id"],
            "farms",
            ["id"],
            "RESTRICT",
        ),
        (
            "trace_records",
            "fk_trace_records_message_id",
            ["conversation_message_id"],
            "conversation_messages",
            ["id"],
            "SET NULL",
        ),
        (
            "simulation_runs",
            "fk_simulation_runs_farm_id",
            ["farm_id"],
            "farms",
            ["id"],
            "RESTRICT",
        ),
        (
            "simulation_results",
            "fk_simulation_results_farm_id",
            ["farm_id"],
            "farms",
            ["id"],
            "RESTRICT",
        ),
    ]
    for table_name, name, local_cols, remote_table, remote_cols, ondelete in fk_specs:
        if name not in _foreign_keys(inspector, table_name):
            op.create_foreign_key(
                name,
                table_name,
                remote_table,
                local_cols,
                remote_cols,
                ondelete=ondelete,
            )


def _drop_foreign_keys(inspector) -> None:
    for table_name, expected_name, columns, referred_table in [
        ("simulation_results", "fk_simulation_results_farm_id", ["farm_id"], "farms"),
        ("simulation_runs", "fk_simulation_runs_farm_id", ["farm_id"], "farms"),
        (
            "trace_records",
            "fk_trace_records_message_id",
            ["conversation_message_id"],
            "conversation_messages",
        ),
        ("trace_records", "fk_trace_records_farm_id", ["farm_id"], "farms"),
        ("token_daily_stats", "fk_token_daily_stats_user_id", ["user_id"], "users"),
        ("token_daily_stats", "fk_token_daily_stats_farm_id", ["farm_id"], "farms"),
        ("user_settings", "fk_user_settings_user_id", ["user_id"], "users"),
        ("feedback_records", "fk_feedback_records_user_id", ["user_id"], "users"),
        ("cost_records", "fk_cost_records_cycle_id", ["cycle_id"], "crop_cycles"),
        (
            "cost_records",
            "fk_cost_records_category_id",
            ["category_id"],
            "cost_categories",
        ),
        ("cost_categories", "fk_cost_categories_farm_id", ["farm_id"], "farms"),
    ]:
        names = {expected_name} & _foreign_keys(inspector, table_name)
        names |= _matching_foreign_key_names(
            inspector,
            table_name,
            columns,
            referred_table,
        )
        for name in names:
            op.drop_constraint(name, table_name, type_="foreignkey")


def _alter_mysql_types() -> None:
    op.alter_column(
        "trace_records", "input_data", type_=sa.JSON(), existing_nullable=True
    )
    op.alter_column(
        "trace_records", "output_data", type_=sa.JSON(), existing_nullable=True
    )
    op.alter_column(
        "trace_records", "token_usage", type_=sa.JSON(), existing_nullable=True
    )
    op.alter_column(
        "trace_records", "start_time", type_=sa.DateTime(), existing_nullable=True
    )
    op.alter_column(
        "trace_records", "end_time", type_=sa.DateTime(), existing_nullable=True
    )
    op.alter_column(
        "token_daily_stats", "date", type_=sa.Date(), existing_nullable=False
    )
    op.alter_column(
        "cycle_stages", "is_current", type_=sa.Boolean(), existing_nullable=True
    )
    for column in [
        "errors_json",
        "db_diff_json",
        "extracted_claims_json",
        "pending_action_json",
        "expected_db_changes_json",
    ]:
        op.alter_column(
            "simulation_results", column, type_=sa.JSON(), existing_nullable=True
        )


def _restore_mysql_types() -> None:
    op.alter_column(
        "trace_records", "input_data", type_=sa.Text(), existing_nullable=True
    )
    op.alter_column(
        "trace_records", "output_data", type_=sa.Text(), existing_nullable=True
    )
    op.alter_column(
        "trace_records", "token_usage", type_=sa.Text(), existing_nullable=True
    )
    op.alter_column(
        "trace_records",
        "start_time",
        type_=sa.String(length=32),
        existing_nullable=True,
    )
    op.alter_column(
        "trace_records", "end_time", type_=sa.String(length=32), existing_nullable=True
    )
    op.alter_column(
        "token_daily_stats", "date", type_=sa.String(length=10), existing_nullable=False
    )
    op.alter_column(
        "cycle_stages", "is_current", type_=sa.Integer(), existing_nullable=True
    )
    for column in [
        "errors_json",
        "db_diff_json",
        "extracted_claims_json",
        "pending_action_json",
        "expected_db_changes_json",
    ]:
        op.alter_column(
            "simulation_results", column, type_=sa.Text(), existing_nullable=True
        )
