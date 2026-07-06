"""MongoDB 三期 MySQL 文档清库工具测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.conversation import Conversation, ConversationMessage
from app.models.guardrails_log import GuardrailsLog
from app.models.mongo_compensation import MongoCompensationTask


class FakeCollection:
    def __init__(self, count: int) -> None:
        self.count = count

    async def count_documents(self, _filter_doc):
        return self.count


class FakeDatabase:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts

    def __getitem__(self, name: str) -> FakeCollection:
        return FakeCollection(self.counts.get(name, 0))


def _add_guardrails(db_session, count: int = 2) -> list[GuardrailsLog]:
    rows = [
        GuardrailsLog(
            farm_id=1,
            trigger_type="input",
            trigger_detail=f"detail-{index}",
            source_text=f"source-{index}",
        )
        for index in range(count)
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def _add_conversation_message(db_session) -> ConversationMessage:
    conversation = Conversation(farm_id=1, session_id="cleanup-session")
    db_session.add(conversation)
    db_session.flush()
    message = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="需要转移到 Mongo 的正文",
        meta='{"source": "test"}',
        meta_json={"source": "test"},
        turn_id=7,
        content_hash="hash-1",
    )
    db_session.add(message)
    db_session.commit()
    return message


@pytest.mark.asyncio
async def test_plan_marks_blocked_and_ready_states(db_session):
    from app.infra.mysql_document_cleanup import build_plan

    _add_guardrails(db_session, count=1)
    db_session.add(
        MongoCompensationTask(
            object_type="guardrails_log",
            farm_id=1,
            business_id="blocked",
            mysql_id=1,
            status="pending",
        )
    )
    db_session.commit()

    rows = await build_plan(
        db_session,
        FakeDatabase({"guardrailsLogs": 1}),
        tables=["guardrails_logs"],
        backend_overrides={"guardrails_logs": "mongo"},
        verify_reports={"guardrails_logs": {"table": "guardrails_logs", "ok": True}},
    )

    payload = rows[0].to_dict()
    assert payload["mysql_count"] == 1
    assert payload["mongo_count"] == 1
    assert payload["status"] == "blocked"
    assert payload["blocked_reasons"][0]["code"] == "MYSQL_CLEANUP_COMPENSATION_BACKLOG"


def test_denied_table_returns_structured_error(db_session):
    from app.infra.mysql_document_cleanup import cleanup_table
    from app.infra.mysql_document_cleanup_types import CleanupError

    with pytest.raises(CleanupError) as exc:
        cleanup_table(db_session, table="conversations", strategy="delete")

    assert exc.value.code == "MYSQL_CLEANUP_TABLE_NOT_ALLOWED"


def test_backup_writes_jsonl_metadata_and_tokens(db_session, tmp_path):
    from app.infra.mysql_document_cleanup import create_backup

    rows = _add_guardrails(db_session, count=2)
    output_dir = tmp_path / "backend" / "var" / "mongodb-cleanup" / "backups"
    result = create_backup(db_session, table="guardrails_logs", output_dir=output_dir)

    backup = Path(result.backup_file)
    metadata = json.loads(Path(result.metadata_file).read_text(encoding="utf-8"))
    lines = backup.read_text(encoding="utf-8").splitlines()
    assert result.row_count == len(rows)
    assert metadata["sha256"] == result.sha256
    assert result.cleanup_confirm_token.startswith("CLEANUP:guardrails_logs:")
    assert "backend/var/mongodb-cleanup" in result.backup_file
    assert len(lines) == 2


def test_cleanup_dry_run_does_not_delete(db_session):
    from app.infra.mysql_document_cleanup import cleanup_table

    _add_guardrails(db_session, count=2)
    result = cleanup_table(
        db_session,
        table="guardrails_logs",
        strategy="delete",
        batch_size=1,
    )

    assert result.mode == "dry-run"
    assert result.planned_count == 2
    assert db_session.query(GuardrailsLog).count() == 2


def test_execute_requires_backup_token_backend_and_verify(db_session, tmp_path):
    from app.infra.mysql_document_cleanup import cleanup_table, create_backup
    from app.infra.mysql_document_cleanup_types import CleanupError

    _add_guardrails(db_session, count=1)
    backup = create_backup(db_session, table="guardrails_logs", output_dir=tmp_path)

    with pytest.raises(CleanupError) as exc:
        cleanup_table(
            db_session,
            table="guardrails_logs",
            strategy="delete",
            execute=True,
            backup_file=Path(backup.backup_file),
            confirm_token=backup.cleanup_confirm_token,
            verify_report={"table": "guardrails_logs", "ok": True},
            backend_overrides={"guardrails_logs": "dual"},
        )
    assert exc.value.code == "MYSQL_CLEANUP_BACKEND_NOT_MONGO"

    with pytest.raises(CleanupError) as exc:
        cleanup_table(
            db_session,
            table="guardrails_logs",
            strategy="delete",
            execute=True,
            backup_file=Path(backup.backup_file),
            confirm_token="wrong",
            verify_report={"table": "guardrails_logs", "ok": True},
            backend_overrides={"guardrails_logs": "mongo"},
        )
    assert exc.value.code == "MYSQL_CLEANUP_CONFIRMATION_REQUIRED"


def test_execute_deletes_in_batches(db_session, tmp_path):
    from app.infra.mysql_document_cleanup import cleanup_table, create_backup

    _add_guardrails(db_session, count=3)
    backup = create_backup(db_session, table="guardrails_logs", output_dir=tmp_path)

    result = cleanup_table(
        db_session,
        table="guardrails_logs",
        strategy="delete",
        execute=True,
        backup_file=Path(backup.backup_file),
        confirm_token=backup.cleanup_confirm_token,
        verify_report={"table": "guardrails_logs", "ok": True},
        backend_overrides={"guardrails_logs": "mongo"},
        batch_size=2,
    )

    assert result.affected_count == 3
    assert result.batches == 2
    assert db_session.query(GuardrailsLog).count() == 0


def test_conversation_messages_only_allow_slim_and_keep_identity(db_session, tmp_path):
    from app.infra.mysql_document_cleanup import cleanup_table, create_backup
    from app.infra.mysql_document_cleanup_types import CleanupError

    message = _add_conversation_message(db_session)
    backup = create_backup(
        db_session, table="conversation_messages", output_dir=tmp_path
    )

    with pytest.raises(CleanupError) as exc:
        cleanup_table(db_session, table="conversation_messages", strategy="delete")
    assert exc.value.code == "MYSQL_CLEANUP_STRATEGY_NOT_ALLOWED"

    result = cleanup_table(
        db_session,
        table="conversation_messages",
        strategy="slim",
        execute=True,
        backup_file=Path(backup.backup_file),
        confirm_token=backup.cleanup_confirm_token,
        verify_report={"table": "conversation_messages", "ok": True},
        backend_overrides={"conversation_messages": "mongo"},
    )
    db_session.refresh(message)
    assert result.affected_count == 1
    assert message.content == ""
    assert message.meta is None
    assert message.meta_json is None
    assert message.turn_id == 7
    assert message.content_hash == "hash-1"


@pytest.mark.asyncio
async def test_post_verify_checks_mysql_strategy_and_mongo_count(db_session):
    from app.infra.mysql_document_cleanup import post_verify

    _add_guardrails(db_session, count=1)
    failed = await post_verify(
        db_session,
        FakeDatabase({"guardrailsLogs": 1}),
        table="guardrails_logs",
        strategy="delete",
        expected_mongo_count=1,
    )
    assert failed["ok"] is False

    db_session.query(GuardrailsLog).delete()
    db_session.commit()
    passed = await post_verify(
        db_session,
        FakeDatabase({"guardrailsLogs": 1}),
        table="guardrails_logs",
        strategy="delete",
        expected_mongo_count=1,
    )
    assert passed["ok"] is True


def test_rollback_import_restores_and_skips_duplicates(db_session, tmp_path):
    from app.infra.mysql_document_cleanup import (
        cleanup_table,
        create_backup,
        rollback_import,
    )

    _add_guardrails(db_session, count=1)
    backup = create_backup(db_session, table="guardrails_logs", output_dir=tmp_path)
    cleanup_table(
        db_session,
        table="guardrails_logs",
        strategy="delete",
        execute=True,
        backup_file=Path(backup.backup_file),
        confirm_token=backup.cleanup_confirm_token,
        verify_report={"table": "guardrails_logs", "ok": True},
        backend_overrides={"guardrails_logs": "mongo"},
    )

    restored = rollback_import(
        db_session,
        table="guardrails_logs",
        backup_file=Path(backup.backup_file),
        execute=True,
        confirm_token=backup.rollback_confirm_token,
    )
    duplicate = rollback_import(
        db_session,
        table="guardrails_logs",
        backup_file=Path(backup.backup_file),
        execute=True,
        confirm_token=backup.rollback_confirm_token,
    )

    assert restored.inserted == 1
    assert duplicate.skipped_existing == 1
    assert db_session.query(GuardrailsLog).count() == 1
