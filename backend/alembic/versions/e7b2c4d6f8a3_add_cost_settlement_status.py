"""add cost settlement status

Revision ID: e7b2c4d6f8a3
Revises: e7b2c4d6f8a2
Create Date: 2026-06-05 16:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "e7b2c4d6f8a3"
down_revision: Union[str, None] = "e7b2c4d6f8a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "cost_records" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("cost_records")}
    # SQLite 无法在非 batch add column 中安全添加 NOT NULL 且无默认值的列。
    # 这里的 server_default 仅用于兼容迁移；应用写入由 CostRecord 模型事件统一覆盖。
    if "settled_amount" not in columns:
        op.add_column(
            "cost_records",
            sa.Column(
                "settled_amount",
                sa.Numeric(10, 2),
                nullable=False,
                server_default="0",
            ),
        )
    if "settlement_status" not in columns:
        op.add_column(
            "cost_records",
            sa.Column(
                "settlement_status",
                sa.String(length=20),
                nullable=False,
                server_default="settled",
            ),
        )

    bind.execute(
        text(
            """
            UPDATE cost_records
            SET settled_amount = amount,
                settlement_status = 'settled'
            WHERE deleted_at IS NULL
              AND (
                  record_subtype IS NULL
                  OR record_subtype != '赊账'
                  OR settled_at IS NOT NULL
              )
            """
        )
    )
    bind.execute(
        text(
            """
            UPDATE cost_records
            SET settled_amount = 0,
                settlement_status = 'unsettled'
            WHERE deleted_at IS NULL
              AND record_subtype = '赊账'
              AND settled_at IS NULL
            """
        )
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "cost_records" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("cost_records")}
    if "settlement_status" in columns:
        op.drop_column("cost_records", "settlement_status")
    if "settled_amount" in columns:
        op.drop_column("cost_records", "settled_amount")
