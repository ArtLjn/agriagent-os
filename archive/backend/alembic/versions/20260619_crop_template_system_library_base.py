"""allow null farm id for system crop templates

Revision ID: 20260619_crop_template_system_library_base
Revises: 20260617_agent_repair_packs
Create Date: 2026-06-19 14:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "20260619_crop_template_system_library_base"
down_revision: Union[str, None] = "20260617_agent_repair_packs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "crop_templates"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        return

    columns = _columns(inspector)
    if bind.dialect.name == "sqlite":
        _upgrade_sqlite(columns)
    else:
        _upgrade_regular(columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        return
    _raise_if_system_templates_exist(bind)

    columns = _columns(inspector)
    if bind.dialect.name == "sqlite":
        _downgrade_sqlite(columns)
    else:
        _downgrade_regular(columns)


def _columns(inspector) -> dict[str, dict]:
    return {column["name"]: column for column in inspector.get_columns(TABLE_NAME)}


def _raise_if_system_templates_exist(bind) -> None:
    system_template_count = bind.execute(
        text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE farm_id IS NULL")
    ).scalar_one()
    if system_template_count:
        raise RuntimeError(
            "Cannot downgrade crop_templates.farm_id to NOT NULL while system "
            "templates exist. Remove or migrate farm_id IS NULL rows first."
        )


def _upgrade_sqlite(columns: dict[str, dict]) -> None:
    with op.batch_alter_table(TABLE_NAME, recreate="always") as batch_op:
        if "farm_id" in columns and not columns["farm_id"].get("nullable", True):
            batch_op.alter_column(
                "farm_id",
                existing_type=sa.Integer(),
                existing_nullable=False,
                nullable=True,
            )


def _upgrade_regular(columns: dict[str, dict]) -> None:
    if "farm_id" in columns and not columns["farm_id"].get("nullable", True):
        op.alter_column(
            TABLE_NAME,
            "farm_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
            nullable=True,
        )


def _downgrade_sqlite(columns: dict[str, dict]) -> None:
    with op.batch_alter_table(TABLE_NAME, recreate="always") as batch_op:
        if "farm_id" in columns and columns["farm_id"].get("nullable", True):
            batch_op.alter_column(
                "farm_id",
                existing_type=sa.Integer(),
                existing_nullable=True,
                nullable=False,
            )


def _downgrade_regular(columns: dict[str, dict]) -> None:
    if "farm_id" in columns and columns["farm_id"].get("nullable", True):
        op.alter_column(
            TABLE_NAME,
            "farm_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )
