"""add agent task states

Revision ID: 20260722_agent_task_states
Revises: 20260626_mongo_compensation_tasks
Create Date: 2026-07-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260722_agent_task_states"
down_revision: Union[str, None] = "20260626_mongo_compensation_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "agent_task_states" in set(inspector.get_table_names()):
        return

    op.create_table(
        "agent_task_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("entities_json", sa.JSON(), nullable=False),
        sa.Column("observations_json", sa.JSON(), nullable=False),
        sa.Column("missing_information_json", sa.JSON(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_agent_task_states_task_id"),
    )
    op.create_index("ix_agent_task_states_task_id", "agent_task_states", ["task_id"])
    op.create_index("ix_agent_task_states_farm_id", "agent_task_states", ["farm_id"])
    op.create_index("ix_agent_task_states_user_id", "agent_task_states", ["user_id"])
    op.create_index(
        "ix_agent_task_states_session_id", "agent_task_states", ["session_id"]
    )
    op.create_index(
        "ix_agent_task_states_task_type", "agent_task_states", ["task_type"]
    )
    op.create_index("ix_agent_task_states_status", "agent_task_states", ["status"])
    op.create_index(
        "ix_agent_task_states_expires_at", "agent_task_states", ["expires_at"]
    )
    op.create_index(
        "ix_agent_task_states_active_lookup",
        "agent_task_states",
        ["farm_id", "user_id", "session_id", "status", "updated_at"],
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "agent_task_states" not in set(inspector.get_table_names()):
        return

    op.drop_index("ix_agent_task_states_active_lookup", table_name="agent_task_states")
    op.drop_index("ix_agent_task_states_expires_at", table_name="agent_task_states")
    op.drop_index("ix_agent_task_states_status", table_name="agent_task_states")
    op.drop_index("ix_agent_task_states_task_type", table_name="agent_task_states")
    op.drop_index("ix_agent_task_states_session_id", table_name="agent_task_states")
    op.drop_index("ix_agent_task_states_user_id", table_name="agent_task_states")
    op.drop_index("ix_agent_task_states_farm_id", table_name="agent_task_states")
    op.drop_index("ix_agent_task_states_task_id", table_name="agent_task_states")
    op.drop_table("agent_task_states")
