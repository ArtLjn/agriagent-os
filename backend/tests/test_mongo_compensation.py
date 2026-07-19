"""Mongo 双写补偿任务测试。"""

from __future__ import annotations

import logging

import pytest

from app.platforms.data_flywheel.models import AgentRepairPack


def _repair_pack(**overrides) -> AgentRepairPack:
    values = {
        "farm_id": 1,
        "pack_id": "pack-1",
        "fix_target": "skill",
        "labels": ["bad_reply"],
        "source_sample_ids": ["turn:1:s1:1"],
        "source_label_ids": [],
        "dedup_key": "dedup-1",
        "status": "exported",
    }
    values.update(overrides)
    return AgentRepairPack(**values)


class FakeMongoRepo:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.rows = []

    async def create(self, row):
        if self.fail:
            raise RuntimeError("mongodb://app:secret@mongo.example/db failed")
        self.rows.append(row)
        return row


class FakeMySQLRepairPackRepo:
    def __init__(self, row: AgentRepairPack) -> None:
        self._row = row

    def get_by_pack_id(self, *, farm_id: int, pack_id: str):
        if self._row.farm_id == farm_id and self._row.pack_id == pack_id:
            return self._row
        return None


@pytest.mark.asyncio
async def test_compensation_recorder_persists_sanitized_task(db_session):
    from app.infra.mongo_compensation import (
        MongoCompensationRecorder,
        MongoCompensationTask,
    )

    recorder = MongoCompensationRecorder(db_session)

    task = recorder.record_failure(
        {
            "object_type": "repair_pack",
            "farm_id": 1,
            "business_id": "pack-1",
            "mysql_id": 12,
            "operation": "create",
            "error": "mongodb://app:secret@mongo.example/db failed",
        }
    )

    saved = db_session.query(MongoCompensationTask).one()
    assert task.id == saved.id
    assert saved.object_type == "repair_pack"
    assert saved.farm_id == 1
    assert saved.business_id == "pack-1"
    assert saved.mysql_id == 12
    assert saved.operation == "create"
    assert saved.status == "pending"
    assert saved.attempts == 0
    assert "secret" not in saved.last_error
    assert "***" in saved.last_error


@pytest.mark.asyncio
async def test_compensation_replay_marks_completed_and_logs_context(db_session, caplog):
    from app.infra.mongo_compensation import (
        MongoCompensationRecorder,
        MongoCompensationReplayService,
        MongoCompensationTask,
    )
    row = _repair_pack(id=12)
    mysql_repo = FakeMySQLRepairPackRepo(row)
    recorder = MongoCompensationRecorder(db_session)
    task = recorder.record_failure(
        {
            "object_type": "repair_pack",
            "farm_id": row.farm_id,
            "business_id": row.pack_id,
            "mysql_id": row.id,
            "operation": "create",
            "error": "timeout",
        }
    )
    mongo_repo = FakeMongoRepo()
    service = MongoCompensationReplayService(
        db_session,
        mysql_repositories={"repair_pack": mysql_repo},
        mongo_repositories={"repair_pack": mongo_repo},
    )

    with caplog.at_level(logging.INFO):
        result = await service.replay_once(task.id)

    saved = db_session.get(MongoCompensationTask, task.id)
    assert result is True
    assert saved.status == "completed"
    assert saved.completed_at is not None
    assert mongo_repo.rows[-1].id == row.id
    assert "code=mongo_compensation_replay_succeeded" in caplog.text
    assert "object_type=repair_pack" in caplog.text
    assert "farm_id=1" in caplog.text
    assert "business_id=pack-1" in caplog.text
    assert f"mysql_id={row.id}" in caplog.text


@pytest.mark.asyncio
async def test_compensation_replay_marks_failed_without_leaking_uri(db_session, caplog):
    from app.infra.mongo_compensation import (
        MongoCompensationRecorder,
        MongoCompensationReplayService,
        MongoCompensationTask,
    )
    row = _repair_pack(id=12)
    mysql_repo = FakeMySQLRepairPackRepo(row)
    task = MongoCompensationRecorder(db_session).record_failure(
        {
            "object_type": "repair_pack",
            "farm_id": row.farm_id,
            "business_id": row.pack_id,
            "mysql_id": row.id,
            "operation": "create",
            "error": "timeout",
        }
    )
    service = MongoCompensationReplayService(
        db_session,
        mysql_repositories={"repair_pack": mysql_repo},
        mongo_repositories={"repair_pack": FakeMongoRepo(fail=True)},
        max_attempts=1,
    )

    with caplog.at_level(logging.WARNING):
        result = await service.replay_once(task.id)

    saved = db_session.get(MongoCompensationTask, task.id)
    assert result is False
    assert saved.status == "failed"
    assert saved.attempts == 1
    assert "secret" not in saved.last_error
    assert "secret" not in caplog.text
    assert "code=mongo_compensation_replay_failed" in caplog.text
    assert "object_type=repair_pack" in caplog.text
    assert f"mysql_id={row.id}" in caplog.text


def test_compensation_recorder_does_not_list_terminal_failed_tasks(db_session):
    from app.infra.mongo_compensation import MongoCompensationRecorder

    recorder = MongoCompensationRecorder(db_session)
    task = recorder.record_failure(
        {
            "object_type": "repair_pack",
            "farm_id": 1,
            "business_id": "pack-1",
            "mysql_id": 12,
            "operation": "create",
            "error": "timeout",
        }
    )
    task.status = "failed"
    task.attempts = 3
    db_session.commit()

    assert recorder.list_pending() == []
