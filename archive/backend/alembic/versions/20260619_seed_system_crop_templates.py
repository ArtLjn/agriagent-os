"""seed system crop templates

Revision ID: 20260619_seed_system_crop_templates
Revises: 20260619_crop_template_category_and_dedup_index
Create Date: 2026-06-19 16:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.ops.system_crop_templates import (
    iter_system_template_keys,
    seed_system_crop_templates,
)


revision: str = "20260619_seed_system_crop_templates"
down_revision: Union[str, None] = "20260619_crop_template_category_and_dedup_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        seed_system_crop_templates(session)
    finally:
        session.close()


def downgrade() -> None:
    bind = op.get_bind()
    for name, variety in iter_system_template_keys():
        template_ids = _system_template_ids(bind, name=name, variety=variety)
        if not template_ids:
            continue
        bind.execute(
            text(
                "DELETE FROM growth_stages WHERE crop_template_id IN :template_ids"
            ).bindparams(bindparam("template_ids", expanding=True)),
            {"template_ids": tuple(template_ids)},
        )
        bind.execute(
            text("DELETE FROM crop_templates WHERE id IN :template_ids").bindparams(
                bindparam("template_ids", expanding=True)
            ),
            {"template_ids": tuple(template_ids)},
        )


def _system_template_ids(bind, name: str, variety: str | None) -> list[int]:
    query = (
        "SELECT id FROM crop_templates "
        "WHERE farm_id IS NULL AND name = :name AND "
        + ("variety IS NULL" if variety is None else "variety = :variety")
    )
    params = {"name": name}
    if variety is not None:
        params["variety"] = variety
    return list(bind.execute(text(query), params).scalars())
