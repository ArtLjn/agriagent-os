"""add user token quota limits

Revision ID: b81d4f2a7c90
Revises: 9c2a1d7b4e6f
Create Date: 2026-06-04 10:48:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "b81d4f2a7c90"
down_revision: Union[str, None] = "9c2a1d7b4e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "token_monthly_limit" not in columns:
        op.add_column(
            "users", sa.Column("token_monthly_limit", sa.Integer(), nullable=True)
        )
    if "token_weekly_limit" not in columns:
        op.add_column(
            "users", sa.Column("token_weekly_limit", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "token_weekly_limit" in columns:
        op.drop_column("users", "token_weekly_limit")
    if "token_monthly_limit" in columns:
        op.drop_column("users", "token_monthly_limit")
