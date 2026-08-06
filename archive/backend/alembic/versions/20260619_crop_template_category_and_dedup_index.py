"""add crop template category and dedup index

Revision ID: 20260619_crop_template_category_and_dedup_index
Revises: 20260619_crop_template_system_library_base
Create Date: 2026-06-19 15:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "20260619_crop_template_category_and_dedup_index"
down_revision: Union[str, None] = "20260619_crop_template_system_library_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "crop_templates"
INDEX_NAME = "ix_crop_templates_farm_name_variety"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        return

    columns = _columns(inspector)
    if "category" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("category", sa.String(length=50), nullable=True),
        )

    inspector = inspect(bind)
    if INDEX_NAME not in _indexes(inspector):
        op.create_index(
            INDEX_NAME,
            TABLE_NAME,
            ["farm_id", "name", "variety"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        return

    if INDEX_NAME in _indexes(inspector):
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)

    columns = _columns(inspector)
    if "category" in columns:
        _raise_if_category_data_exists(bind)
        op.drop_column(TABLE_NAME, "category")


def _columns(inspector) -> dict[str, dict]:
    return {column["name"]: column for column in inspector.get_columns(TABLE_NAME)}


def _indexes(inspector) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(TABLE_NAME)}


def _raise_if_category_data_exists(bind) -> None:
    category_count = bind.execute(
        text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE category IS NOT NULL")
    ).scalar_one()
    if category_count:
        raise RuntimeError(
            "Cannot drop crop_templates.category while category data exists. "
            "Clear or migrate category values first."
        )
