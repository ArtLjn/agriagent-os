from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import Base
from app.models import *  # noqa: F401,F403

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    run_migrations_online()


def run_migrations_online() -> None:
    from app.core.database import engine

    with engine.connect() as connection:
        if _ensure_version_num_capacity(connection, min_length=128):
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


def _ensure_version_num_capacity(connection, min_length: int) -> bool:
    """确保 alembic_version.version_num 能容纳较长 revision id。"""
    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        return False

    version_column = next(
        (
            column
            for column in inspector.get_columns("alembic_version")
            if column["name"] == "version_num"
        ),
        None,
    )
    if version_column is None:
        return False

    column_type = version_column["type"]
    current_length = getattr(column_type, "length", None)
    if current_length is not None and current_length >= min_length:
        return False

    connection.execute(
        text(f"ALTER TABLE alembic_version MODIFY version_num VARCHAR({min_length})")
    )
    return True


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
