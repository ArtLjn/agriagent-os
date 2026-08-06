"""add review issue chain review fields

Revision ID: 20260624_review_issue_chain_review_fields
Revises: 20260623_agent_review_issue_chains
Create Date: 2026-06-24 16:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260624_review_issue_chain_review_fields"
down_revision: Union[str, None] = "20260623_agent_review_issue_chains"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "agent_review_issue_chains"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "fix_target" not in columns:
        op.add_column(TABLE_NAME, sa.Column("fix_target", sa.String(length=40), nullable=True))
    if "reviewer_comment" not in columns:
        op.add_column(TABLE_NAME, sa.Column("reviewer_comment", sa.Text(), nullable=True))
    if "ai_judge" not in columns:
        op.add_column(TABLE_NAME, sa.Column("ai_judge", sa.JSON(), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    index_name = f"ix_{TABLE_NAME}_fix_target"
    if index_name not in indexes:
        op.create_index(index_name, TABLE_NAME, ["fix_target"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    index_name = f"ix_{TABLE_NAME}_fix_target"
    if index_name in indexes:
        op.drop_index(index_name, table_name=TABLE_NAME)

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "reviewer_comment" in columns:
        op.drop_column(TABLE_NAME, "reviewer_comment")
    if "ai_judge" in columns:
        op.drop_column(TABLE_NAME, "ai_judge")
    if "fix_target" in columns:
        op.drop_column(TABLE_NAME, "fix_target")
