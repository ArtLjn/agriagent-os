"""initial schema

Revision ID: 706a5f7f11b9
Revises:
Create Date: 2026-06-03 11:07:16.265507
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

from app.shared.database import Base
from app.models import *  # noqa: F401,F403


revision: str = "706a5f7f11b9"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    managed_tables = set(Base.metadata.tables)
    if existing_tables & managed_tables:
        return
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
