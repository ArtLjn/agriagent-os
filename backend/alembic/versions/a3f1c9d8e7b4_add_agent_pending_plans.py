"""add agent pending plans

Revision ID: a3f1c9d8e7b4
Revises: f2c9a8e1d4b7
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "a3f1c9d8e7b4"
down_revision: Union[str, None] = "f2c9a8e1d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "agent_pending_plans" not in tables:
        op.create_table(
            "agent_pending_plans",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.String(length=64), nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("current_step_index", sa.Integer(), nullable=False),
            sa.Column("raw_user_input", sa.Text(), nullable=False),
            sa.Column("router_decision", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_agent_pending_plans_id", "agent_pending_plans", ["id"], unique=False
        )
        op.create_index(
            "ix_agent_pending_plans_plan_id",
            "agent_pending_plans",
            ["plan_id"],
            unique=True,
        )
        op.create_index(
            "ix_agent_pending_plans_farm_id",
            "agent_pending_plans",
            ["farm_id"],
            unique=False,
        )
        op.create_index(
            "ix_agent_pending_plans_session_id",
            "agent_pending_plans",
            ["session_id"],
            unique=False,
        )

    if "agent_pending_plan_steps" not in tables:
        op.create_table(
            "agent_pending_plan_steps",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.String(length=64), nullable=False),
            sa.Column("step_id", sa.String(length=64), nullable=False),
            sa.Column("step_index", sa.Integer(), nullable=False),
            sa.Column("tool_name", sa.String(length=100), nullable=False),
            sa.Column("params", sa.JSON(), nullable=False),
            sa.Column("depends_on", sa.JSON(), nullable=False),
            sa.Column("confirmation_state", sa.String(length=32), nullable=False),
            sa.Column("execution_status", sa.String(length=32), nullable=False),
            sa.Column("result_payload", sa.JSON(), nullable=True),
            sa.Column("error_payload", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["plan_id"], ["agent_pending_plans.plan_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_agent_pending_plan_steps_id",
            "agent_pending_plan_steps",
            ["id"],
            unique=False,
        )
        op.create_index(
            "ix_agent_pending_plan_steps_plan_id",
            "agent_pending_plan_steps",
            ["plan_id"],
            unique=False,
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "agent_pending_plan_steps" in tables:
        op.drop_index(
            "ix_agent_pending_plan_steps_plan_id",
            table_name="agent_pending_plan_steps",
        )
        op.drop_index(
            "ix_agent_pending_plan_steps_id",
            table_name="agent_pending_plan_steps",
        )
        op.drop_table("agent_pending_plan_steps")

    if "agent_pending_plans" in tables:
        op.drop_index(
            "ix_agent_pending_plans_session_id", table_name="agent_pending_plans"
        )
        op.drop_index(
            "ix_agent_pending_plans_farm_id", table_name="agent_pending_plans"
        )
        op.drop_index(
            "ix_agent_pending_plans_plan_id", table_name="agent_pending_plans"
        )
        op.drop_index("ix_agent_pending_plans_id", table_name="agent_pending_plans")
        op.drop_table("agent_pending_plans")
