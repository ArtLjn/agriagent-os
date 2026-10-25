"""备忘录发布检查：重复运行、结构漂移、锁释放与初始化基线。"""

from unittest.mock import MagicMock, patch

import pytest
from farm_business.models import Memo
from farm_business.scripts import migrate_memos as migration
from sqlalchemy import create_engine, text


def test_schema_check_detects_missing_or_incomplete_table():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        with pytest.raises(RuntimeError, match="memo_schema_missing"):
            migration.check_schema(connection)
        connection.execute(text("CREATE TABLE memos (id INTEGER PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="memo_schema_mismatch"):
            migration.check_schema(connection)
    engine.dispose()


def test_schema_check_accepts_model_and_rejects_missing_list_index():
    engine = create_engine("sqlite://")
    Memo.__table__.create(engine)
    with engine.connect() as connection:
        migration.check_schema(connection)
        connection.execute(text("DROP INDEX idx_memo_list"))
        with pytest.raises(RuntimeError, match="memo_schema_mismatch"):
            migration.check_schema(connection)
    engine.dispose()


@pytest.mark.parametrize("exists", [False, True])
def test_apply_only_creates_missing_table_and_always_verifies(exists):
    engine = MagicMock()
    engine.dialect.name = "mysql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = 1
    with (
        patch.object(migration, "inspect") as inspector,
        patch.object(migration, "check_schema") as check,
    ):
        inspector.return_value.has_table.return_value = exists
        assert migration.migrate(engine, apply=True) == (
            "ready" if exists else "created"
        )
        check.assert_called_once_with(connection)
        if exists:
            connection.exec_driver_sql.assert_not_called()
        else:
            connection.exec_driver_sql.assert_called_once_with(
                migration.MIGRATION.read_text()
            )
        assert "RELEASE_LOCK" in str(connection.execute.call_args.args[0])


def test_read_only_check_never_acquires_lock_or_writes():
    engine = MagicMock()
    engine.dialect.name = "mysql"
    connection = engine.connect.return_value.__enter__.return_value
    with patch.object(migration, "check_schema") as check:
        assert migration.migrate(engine) == "ready"
        check.assert_called_once_with(connection)
        connection.scalar.assert_not_called()
        connection.exec_driver_sql.assert_not_called()


def test_lock_timeout_does_not_run_ddl():
    engine = MagicMock()
    engine.dialect.name = "mysql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = 0
    with pytest.raises(RuntimeError, match="memo_migration_busy"):
        migration.migrate(engine, apply=True)
    connection.exec_driver_sql.assert_not_called()


def test_schema_failure_releases_lock_without_modifying_existing_table():
    engine = MagicMock()
    engine.dialect.name = "mysql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = 1
    with (
        patch.object(migration, "inspect") as inspector,
        patch.object(migration, "check_schema", side_effect=RuntimeError("drift")),
    ):
        inspector.return_value.has_table.return_value = True
        with pytest.raises(RuntimeError, match="drift"):
            migration.migrate(engine, apply=True)
    connection.exec_driver_sql.assert_not_called()
    assert "RELEASE_LOCK" in str(connection.execute.call_args.args[0])


def test_new_environment_baseline_contains_exact_memo_ddl():
    root = migration.MIGRATION.parents[2]
    ddl = migration.MIGRATION.read_text().split("CREATE TABLE memos", 1)[1]
    assert "CREATE TABLE memos" + ddl in (root / "sql/farm_manager.sql").read_text()
