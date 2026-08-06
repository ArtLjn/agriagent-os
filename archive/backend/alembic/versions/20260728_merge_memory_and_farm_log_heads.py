"""merge memory and farm log worker heads

Revision ID: 20260728_merge_memory_farm_logs
Revises: 20260722_explicit_memory_records, 20260728_farm_log_worker_links
Create Date: 2026-07-28 14:35:00.000000
"""

from typing import Sequence, Union


revision: str = "20260728_merge_memory_farm_logs"
down_revision: Union[str, tuple[str, str], None] = (
    "20260722_explicit_memory_records",
    "20260728_farm_log_worker_links",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
