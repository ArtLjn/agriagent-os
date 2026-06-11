"""agent data flywheel storage

Revision ID: 20260611_agent_data_flywheel
Revises: 20260611_agent_session_flywheel
Create Date: 2026-06-11 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260611_agent_data_flywheel"
down_revision: Union[str, None] = "20260611_agent_session_flywheel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _create_agent_data_flywheel_labels(inspector)
    _create_agent_case_drafts(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _drop_agent_case_drafts(inspector)
    _drop_agent_data_flywheel_labels(inspector)


def _tables(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _indexes(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(
    inspector,
    table_name: str,
    index_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    if index_name not in _indexes(inspector, table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _create_agent_data_flywheel_labels(inspector) -> None:
    table_name = "agent_data_flywheel_labels"
    if table_name not in _tables(inspector):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False
            ),
            sa.Column("sample_id", sa.String(length=160), nullable=False),
            sa.Column("sample_type", sa.String(length=40), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("turn_id", sa.Integer(), nullable=True),
            sa.Column("request_id", sa.String(length=32), nullable=True),
            sa.Column("label", sa.String(length=64), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("annotator_id", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_farm_id",
        ["farm_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_sample_id",
        ["sample_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_sample_type",
        ["sample_type"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_session_id",
        ["session_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_turn_id",
        ["turn_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_request_id",
        ["request_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_label",
        ["label"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_annotator_id",
        ["annotator_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_data_flywheel_labels_created_at",
        ["created_at"],
    )


def _drop_agent_data_flywheel_labels(inspector) -> None:
    if "agent_data_flywheel_labels" in _tables(inspector):
        op.drop_table("agent_data_flywheel_labels")


def _create_agent_case_drafts(inspector) -> None:
    table_name = "agent_case_drafts"
    if table_name not in _tables(inspector):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False
            ),
            sa.Column("draft_id", sa.String(length=64), nullable=False),
            sa.Column("source_sample_id", sa.String(length=160), nullable=False),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column(
                "status", sa.String(length=20), nullable=False, server_default="draft"
            ),
            sa.Column("case_json", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_case_drafts_farm_id",
        ["farm_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_case_drafts_draft_id",
        ["draft_id"],
        unique=True,
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_case_drafts_source_sample_id",
        ["source_sample_id"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_case_drafts_target_type",
        ["target_type"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_case_drafts_status",
        ["status"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_case_drafts_created_by",
        ["created_by"],
    )
    _create_index_if_missing(
        inspector,
        table_name,
        "ix_agent_case_drafts_created_at",
        ["created_at"],
    )


def _drop_agent_case_drafts(inspector) -> None:
    if "agent_case_drafts" in _tables(inspector):
        op.drop_table("agent_case_drafts")
