"""add dedup_key to agent repair packs

Revision ID: 20260620_agent_repair_packs_dedup_key
Revises: 20260619_seed_system_crop_templates
Create Date: 2026-06-20 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260620_agent_repair_packs_dedup_key"
down_revision: Union[str, None] = "20260619_seed_system_crop_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "agent_repair_packs"
COLUMN_NAME = "dedup_key"
INDEX_NAME = f"ix_{TABLE_NAME}_{COLUMN_NAME}"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME in columns:
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(TABLE_NAME) as batch_op:
            batch_op.add_column(sa.Column(COLUMN_NAME, sa.String(length=40), nullable=True))
    else:
        op.add_column(
            TABLE_NAME,
            sa.Column(COLUMN_NAME, sa.String(length=40), nullable=True),
        )

    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME not in indexes:
        op.create_index(INDEX_NAME, TABLE_NAME, [COLUMN_NAME])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME not in columns:
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(TABLE_NAME) as batch_op:
            batch_op.drop_column(COLUMN_NAME)
    else:
        op.drop_column(TABLE_NAME, COLUMN_NAME)
