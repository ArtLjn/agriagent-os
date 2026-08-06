"""add token daily stats user id

Revision ID: c6f4d9a2e8b1
Revises: b81d4f2a7c90
Create Date: 2026-06-04 15:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "c6f4d9a2e8b1"
down_revision: Union[str, None] = "b81d4f2a7c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("token_daily_stats")}

    if "user_id" not in columns:
        op.add_column(
            "token_daily_stats",
            sa.Column("user_id", sa.String(length=36), nullable=True),
        )

    indexes = {index["name"] for index in inspector.get_indexes("token_daily_stats")}
    if "ix_token_daily_stats_user_id" not in indexes:
        op.create_index(
            "ix_token_daily_stats_user_id",
            "token_daily_stats",
            ["user_id"],
            unique=False,
        )

    rows = bind.execute(
        sa.text(
            """
            SELECT stats.id AS stats_id, farms.user_id AS user_id
            FROM token_daily_stats AS stats
            JOIN farms ON farms.id = stats.farm_id
            WHERE stats.user_id IS NULL
              AND farms.user_id IS NOT NULL
            """
        )
    )
    for row in rows:
        bind.execute(
            sa.text("UPDATE token_daily_stats SET user_id = :user_id WHERE id = :id"),
            {"user_id": row.user_id, "id": row.stats_id},
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("token_daily_stats")}
    if "ix_token_daily_stats_user_id" in indexes:
        op.drop_index("ix_token_daily_stats_user_id", table_name="token_daily_stats")

    columns = {column["name"] for column in inspector.get_columns("token_daily_stats")}
    if "user_id" in columns:
        op.drop_column("token_daily_stats", "user_id")
