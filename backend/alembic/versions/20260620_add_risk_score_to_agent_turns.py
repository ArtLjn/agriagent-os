"""add risk score to agent turns

Revision ID: 20260620_add_risk_score_to_agent_turns
Revises: 20260619_seed_system_crop_templates
Create Date: 2026-06-20 14:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260620_add_risk_score_to_agent_turns"
down_revision: Union[str, None] = "20260619_seed_system_crop_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_turns",
        sa.Column("rule_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_turns",
        sa.Column("rule_hits", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "agent_turns",
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_turns", sa.Column("risk_dominant_signal", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "agent_turns", sa.Column("risk_severity", sa.String(length=10), nullable=True)
    )
    op.add_column(
        "agent_turns", sa.Column("judge_bad_prob", sa.Float(), nullable=True)
    )
    op.add_column(
        "agent_turns", sa.Column("judge_issue_type", sa.String(length=80), nullable=True)
    )
    op.add_column(
        "agent_turns",
        sa.Column("judge_suggested_label", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_agent_turns_risk_score", "agent_turns", ["risk_score"])
    op.create_index(
        "ix_agent_turns_risk_dominant_signal",
        "agent_turns",
        ["risk_dominant_signal"],
    )
    op.create_index("ix_agent_turns_risk_severity", "agent_turns", ["risk_severity"])
    op.create_index(
        "ix_agent_turns_judge_issue_type", "agent_turns", ["judge_issue_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_turns_judge_issue_type", table_name="agent_turns")
    op.drop_index("ix_agent_turns_risk_severity", table_name="agent_turns")
    op.drop_index("ix_agent_turns_risk_dominant_signal", table_name="agent_turns")
    op.drop_index("ix_agent_turns_risk_score", table_name="agent_turns")
    op.drop_column("agent_turns", "judge_suggested_label")
    op.drop_column("agent_turns", "judge_issue_type")
    op.drop_column("agent_turns", "judge_bad_prob")
    op.drop_column("agent_turns", "risk_severity")
    op.drop_column("agent_turns", "risk_dominant_signal")
    op.drop_column("agent_turns", "risk_score")
    op.drop_column("agent_turns", "rule_hits")
    op.drop_column("agent_turns", "rule_score")
