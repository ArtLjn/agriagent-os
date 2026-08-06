"""add risk score to agent turns

Revision ID: 20260620_add_risk_score_to_agent_turns
Revises: 20260619_seed_system_crop_templates
Create Date: 2026-06-20 14:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260620_add_risk_score_to_agent_turns"
down_revision: Union[str, None] = "20260619_seed_system_crop_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "agent_turns"

COLUMNS = (
    ("rule_score", sa.Float(), False, "0"),
    ("rule_hits", sa.JSON(), True, None),
    ("risk_score", sa.Float(), False, "0"),
    ("risk_dominant_signal", sa.String(length=20), True, None),
    ("risk_severity", sa.String(length=10), True, None),
    ("judge_bad_prob", sa.Float(), True, None),
    ("judge_issue_type", sa.String(length=80), True, None),
    ("judge_suggested_label", sa.String(length=80), True, None),
)

INDEXES = (
    ("ix_agent_turns_risk_score", ("risk_score",)),
    ("ix_agent_turns_risk_dominant_signal", ("risk_dominant_signal",)),
    ("ix_agent_turns_risk_severity", ("risk_severity",)),
    ("ix_agent_turns_judge_issue_type", ("judge_issue_type",)),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns(TABLE)}
    existing_idx = {i["name"] for i in inspector.get_indexes(TABLE)}
    for name, type_, nullable, default in COLUMNS:
        if name in existing_cols:
            continue
        op.add_column(
            TABLE,
            sa.Column(
                name,
                type_,
                nullable=nullable,
                server_default=default if default is not None else None,
            ),
        )
    for name, cols in INDEXES:
        if name in existing_idx:
            continue
        op.create_index(name, TABLE, list(cols))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    existing_idx = {i["name"] for i in inspector.get_indexes(TABLE)}
    existing_cols = {c["name"] for c in inspector.get_columns(TABLE)}
    for name, _ in INDEXES:
        if name in existing_idx:
            op.drop_index(name, table_name=TABLE)
    for name, _, _, _ in reversed(COLUMNS):
        if name in existing_cols:
            op.drop_column(TABLE, name)
