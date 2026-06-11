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


def _create_agent_data_flywheel_labels(inspector) -> None:
    if "agent_data_flywheel_labels" in _tables(inspector):
        return
    op.create_table(
        "agent_data_flywheel_labels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
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
    op.create_index(
        "ix_agent_data_flywheel_labels_farm_id",
        "agent_data_flywheel_labels",
        ["farm_id"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_sample_id",
        "agent_data_flywheel_labels",
        ["sample_id"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_sample_type",
        "agent_data_flywheel_labels",
        ["sample_type"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_session_id",
        "agent_data_flywheel_labels",
        ["session_id"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_turn_id",
        "agent_data_flywheel_labels",
        ["turn_id"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_request_id",
        "agent_data_flywheel_labels",
        ["request_id"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_label",
        "agent_data_flywheel_labels",
        ["label"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_annotator_id",
        "agent_data_flywheel_labels",
        ["annotator_id"],
    )
    op.create_index(
        "ix_agent_data_flywheel_labels_created_at",
        "agent_data_flywheel_labels",
        ["created_at"],
    )


def _drop_agent_data_flywheel_labels(inspector) -> None:
    if "agent_data_flywheel_labels" in _tables(inspector):
        op.drop_table("agent_data_flywheel_labels")


def _create_agent_case_drafts(inspector) -> None:
    if "agent_case_drafts" in _tables(inspector):
        return
    op.create_table(
        "agent_case_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("draft_id", sa.String(length=64), nullable=False, unique=True),
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
    op.create_index("ix_agent_case_drafts_farm_id", "agent_case_drafts", ["farm_id"])
    op.create_index(
        "ix_agent_case_drafts_draft_id",
        "agent_case_drafts",
        ["draft_id"],
        unique=True,
    )
    op.create_index(
        "ix_agent_case_drafts_source_sample_id",
        "agent_case_drafts",
        ["source_sample_id"],
    )
    op.create_index(
        "ix_agent_case_drafts_target_type", "agent_case_drafts", ["target_type"]
    )
    op.create_index("ix_agent_case_drafts_status", "agent_case_drafts", ["status"])
    op.create_index(
        "ix_agent_case_drafts_created_by", "agent_case_drafts", ["created_by"]
    )
    op.create_index(
        "ix_agent_case_drafts_created_at", "agent_case_drafts", ["created_at"]
    )


def _drop_agent_case_drafts(inspector) -> None:
    if "agent_case_drafts" in _tables(inspector):
        op.drop_table("agent_case_drafts")
