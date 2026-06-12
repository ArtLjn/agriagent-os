"""add status to data flywheel labels

Revision ID: 20260612_agent_data_flywheel_label_status
Revises: 20260611_agent_data_flywheel
Create Date: 2026-06-12 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260612_agent_data_flywheel_label_status"
down_revision: Union[str, None] = "20260611_agent_data_flywheel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_name = "agent_data_flywheel_labels"
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "status" not in columns:
        op.add_column(
            table_name,
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="open",
            ),
        )

    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if "ix_agent_data_flywheel_labels_status" not in indexes:
        op.create_index(
            "ix_agent_data_flywheel_labels_status",
            table_name,
            ["status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_name = "agent_data_flywheel_labels"
    if table_name not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if "ix_agent_data_flywheel_labels_status" in indexes:
        op.drop_index("ix_agent_data_flywheel_labels_status", table_name=table_name)

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "status" in columns:
        op.drop_column(table_name, "status")
