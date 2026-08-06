"""pending plan concurrency safety

Revision ID: 20260731_pending_plan_concurrency_safety
Revises: 20260728_merge_memory_farm_logs
Create Date: 2026-07-31 16:35:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260731_pending_plan_concurrency_safety"
down_revision: Union[str, None] = "20260728_merge_memory_farm_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PENDING_INDEX_NAME = "uq_agent_pending_plan_steps_pending"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agent_pending_plans")}
    if "version" not in columns:
        op.add_column(
            "agent_pending_plans",
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        )

    _cleanup_duplicate_step_rows(bind.dialect.name)
    _create_pending_step_unique_index(bind.dialect.name)


def downgrade() -> None:
    bind = op.get_bind()
    _drop_pending_step_unique_index(bind.dialect.name)
    columns = {column["name"] for column in inspect(bind).get_columns("agent_pending_plans")}
    if "version" in columns:
        op.drop_column("agent_pending_plans", "version")


def _cleanup_duplicate_step_rows(dialect_name: str) -> None:
    if dialect_name == "mysql":
        op.execute(
            """
            UPDATE agent_pending_plan_steps target
            JOIN agent_pending_plan_steps keep_row
              ON keep_row.plan_id = target.plan_id
             AND keep_row.step_index = target.step_index
             AND keep_row.status = target.status
             AND keep_row.id < target.id
            SET target.status = 'failed',
                target.execution_status = 'failed',
                target.error_message = '迁移前清理重复 step 状态'
            WHERE target.status IN ('pending', 'executed')
            """
        )
        return
    op.execute(
        """
        UPDATE agent_pending_plan_steps
           SET status = 'failed',
               execution_status = 'failed',
               error_message = '迁移前清理重复 step 状态'
         WHERE status IN ('pending', 'executed')
           AND id NOT IN (
             SELECT MIN(id)
               FROM agent_pending_plan_steps
              WHERE status IN ('pending', 'executed')
              GROUP BY plan_id, step_index, status
           )
        """
    )


def _create_pending_step_unique_index(dialect_name: str) -> None:
    if dialect_name == "mysql":
        op.execute(
            f"""
            CREATE UNIQUE INDEX {_PENDING_INDEX_NAME}
            ON agent_pending_plan_steps (
              plan_id,
              step_index,
              ((CASE WHEN status = 'pending' THEN status ELSE NULL END))
            )
            """
        )
        return
    op.create_index(
        _PENDING_INDEX_NAME,
        "agent_pending_plan_steps",
        ["plan_id", "step_index", "status"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )


def _drop_pending_step_unique_index(dialect_name: str) -> None:
    if dialect_name == "mysql":
        op.execute(f"DROP INDEX {_PENDING_INDEX_NAME} ON agent_pending_plan_steps")
        return
    op.drop_index(_PENDING_INDEX_NAME, table_name="agent_pending_plan_steps")
