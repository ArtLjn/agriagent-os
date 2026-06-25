"""fix missing review issue chain ai judge column

Revision ID: 20260625_fix_review_issue_chain_ai_judge_column
Revises: 20260624_review_issue_chain_review_fields
Create Date: 2026-06-25 14:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260625_fix_review_issue_chain_ai_judge_column"
down_revision: Union[str, None] = "20260624_review_issue_chain_review_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "agent_review_issue_chains"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "ai_judge" not in columns:
        op.add_column(TABLE_NAME, sa.Column("ai_judge", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "ai_judge" in columns:
        op.drop_column(TABLE_NAME, "ai_judge")
