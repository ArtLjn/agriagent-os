"""add farm uid

Revision ID: 9c2a1d7b4e6f
Revises: 706a5f7f11b9
Create Date: 2026-06-04 00:00:00.000000
"""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "9c2a1d7b4e6f"
down_revision: Union[str, None] = "706a5f7f11b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("farms")}
    if "uid" not in columns:
        op.add_column("farms", sa.Column("uid", sa.String(length=36), nullable=True))

    farms = bind.execute(sa.text("SELECT id FROM farms WHERE uid IS NULL OR uid = ''"))
    for row in farms:
        bind.execute(
            sa.text("UPDATE farms SET uid = :uid WHERE id = :id"),
            {"uid": str(uuid4()), "id": row.id},
        )

    indexes = {index["name"] for index in inspector.get_indexes("farms")}
    if "ix_farms_uid" not in indexes:
        op.create_index("ix_farms_uid", "farms", ["uid"], unique=True)

    if bind.dialect.name != "sqlite":
        op.alter_column(
            "farms", "uid", existing_type=sa.String(length=36), nullable=False
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("farms")}
    if "ix_farms_uid" in indexes:
        op.drop_index("ix_farms_uid", table_name="farms")

    columns = {column["name"] for column in inspector.get_columns("farms")}
    if "uid" in columns:
        op.drop_column("farms", "uid")
