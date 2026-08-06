"""add mongo compensation tasks

Revision ID: 20260626_mongo_compensation_tasks
Revises: 20260625_fix_review_issue_chain_ai_judge_column
Create Date: 2026-06-26 12:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260626_mongo_compensation_tasks"
down_revision: Union[str, None] = "20260625_fix_review_issue_chain_ai_judge_column"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "mongo_compensation_tasks"
INDEXES = {
    "ix_mongo_compensation_tasks_status_next_retry": ["status", "next_retry_at"],
    "ix_mongo_compensation_tasks_object_business": [
        "object_type",
        "farm_id",
        "business_id",
    ],
    "ix_mongo_compensation_tasks_mysql_id": ["mysql_id"],
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("object_type", sa.String(length=64), nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.String(length=160), nullable=True),
            sa.Column("mysql_id", sa.Integer(), nullable=True),
            sa.Column("operation", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    for index_name, columns in INDEXES.items():
        if index_name not in indexes:
            op.create_index(index_name, TABLE_NAME, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    op.drop_table(TABLE_NAME)
