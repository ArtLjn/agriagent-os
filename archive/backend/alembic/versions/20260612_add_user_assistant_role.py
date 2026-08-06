"""add assistant role to user settings

Revision ID: 20260612_add_user_assistant_role
Revises: 20260612_agent_data_flywheel_label_status
Create Date: 2026-06-12 15:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260612_add_user_assistant_role"
down_revision: Union[str, None] = "20260612_agent_data_flywheel_label_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_name = "user_settings"
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "assistant_role" not in columns:
        op.add_column(
            table_name,
            sa.Column(
                "assistant_role",
                sa.String(length=20),
                nullable=False,
                server_default="warm",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_name = "user_settings"
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "assistant_role" in columns:
        op.drop_column(table_name, "assistant_role")
