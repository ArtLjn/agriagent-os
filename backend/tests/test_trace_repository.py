"""Trace Repository 存储后端行为测试。"""

from __future__ import annotations

import pytest

from app.models.trace import TraceRecord


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def sort(self, *_args):
        return self

    def skip(self, _offset: int):
        return self

    def limit(self, _limit: int):
        return self

    async def to_list(self, _length: int | None = None):
        return list(self._docs)


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None, fail_replace: bool = False):
        self.docs = docs or []
        self.fail_replace = fail_replace
        self.filters: list[dict] = []
        self.replacements: list[dict] = []

    async def replace_one(self, filter_doc, replacement, upsert=False):
        if self.fail_replace:
            raise RuntimeError("mongodb://user:secret@example/db failed")
        self.filters.append(dict(filter_doc))
        self.replacements.append(dict(replacement))
        return {"upserted": upsert}

    async def find_one(self, filter_doc):
        self.filters.append(dict(filter_doc))
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in filter_doc.items()):
                return doc
        return None

    def find(self, filter_doc):
        self.filters.append(dict(filter_doc))
        docs = [
            doc
            for doc in self.docs
            if all(
                doc.get(key) in value["$in"]
                if isinstance(value, dict) and "$in" in value
                else doc.get(key) == value
                for key, value in filter_doc.items()
            )
        ]
        return FakeCursor(docs)

    async def count_documents(self, filter_doc):
        self.filters.append(dict(filter_doc))
        return len(
            [
                doc
                for doc in self.docs
                if all(doc.get(key) == value for key, value in filter_doc.items())
            ]
        )


def _trace(**overrides) -> TraceRecord:
    values = {
        "farm_id": 1,
        "request_id": "req-1",
        "session_id": "session-1",
        "round_index": 0,
        "node_type": "llm_call",
        "node_name": "planner",
        "status": "success",
        "input_data": {"prompt": "hi"},
        "output_data": {"text": "ok"},
        "token_usage": {"total": 3},
    }
    values.update(overrides)
    return TraceRecord(**values)


def test_trace_mysql_repository_insert_list_get_and_node_summary(db_session):
    from app.infra.trace_repository import TraceMySQLRepository

    repo = TraceMySQLRepository(db_session)
    first = repo.insert(_trace(node_name="planner", duration_ms=10))
    repo.insert(_trace(node_name="executor", duration_ms=20))

    assert first.id is not None
    assert (
        repo.get_by_request_id(farm_id=1, request_id="req-1")[0].node_name == "planner"
    )

    page = repo.list_by_session(farm_id=1, session_id="session-1", limit=10)
    assert page.total == 2
    assert [item.node_name for item in page.items] == ["executor", "planner"]

    summary = repo.aggregate_by_node(farm_id=1, session_id="session-1")
    assert summary[0]["node_name"] == "executor"
    assert summary[0]["count"] == 1


@pytest.mark.asyncio
async def test_trace_mongo_repository_requires_farm_id_and_filters_by_farm():
    from app.infra.trace_repository import TraceMongoRepository

    collection = FakeCollection(
        [
            {
                "mysqlId": 10,
                "farmId": 1,
                "requestId": "req-1",
                "sessionId": "session-1",
                "roundIndex": 0,
                "nodeType": "llm_call",
                "nodeName": "planner",
                "status": "success",
            }
        ]
    )
    repo = TraceMongoRepository(collection)

    records = await repo.get_by_request_id(farm_id=1, request_id="req-1")
    page = await repo.list_by_session(farm_id=1, session_id="session-1")

    assert records[0].id == 10
    assert page.total == 1
    assert all(filter_doc["farmId"] == 1 for filter_doc in collection.filters)
    with pytest.raises(ValueError, match="MONGO_FARM_ID_REQUIRED"):
        await repo.get_by_request_id(farm_id=None, request_id="req-1")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_trace_dual_write_keeps_mysql_success_when_mongo_fails(db_session):
    from app.infra.trace_repository import (
        TraceDualWriteRepository,
        TraceMySQLRepository,
    )
    from app.infra.trace_repository import TraceMongoRepository

    events = []
    mysql_repo = TraceMySQLRepository(db_session)
    mongo_repo = TraceMongoRepository(FakeCollection(fail_replace=True))
    repo = TraceDualWriteRepository(
        mysql_repo,
        mongo_repo,
        on_secondary_failure=lambda payload: events.append(payload),
    )

    row = await repo.insert(_trace())

    assert row.id is not None
    assert db_session.query(TraceRecord).count() == 1
    assert events[0]["code"] == "mongo_secondary_write_failed"
    assert events[0]["object_type"] == "trace"
    assert "secret" not in events[0]["error"]


@pytest.mark.asyncio
async def test_trace_dual_write_can_record_compensation_task(db_session):
    from app.infra.mongo_compensation import (
        MongoCompensationRecorder,
        MongoCompensationTask,
    )
    from app.infra.trace_repository import (
        TraceDualWriteRepository,
        TraceMongoRepository,
        TraceMySQLRepository,
    )

    recorder = MongoCompensationRecorder(db_session)
    repo = TraceDualWriteRepository(
        TraceMySQLRepository(db_session),
        TraceMongoRepository(FakeCollection(fail_replace=True)),
        on_secondary_failure=recorder.record_failure,
    )

    row = await repo.insert(_trace())

    task = db_session.query(MongoCompensationTask).one()
    assert task.object_type == "trace"
    assert task.farm_id == 1
    assert task.business_id == "req-1"
    assert task.mysql_id == row.id
    assert task.status == "pending"
    assert "secret" not in task.last_error


@pytest.mark.asyncio
async def test_trace_dual_write_ignores_compensation_recorder_failure(db_session):
    from app.infra.trace_repository import (
        TraceDualWriteRepository,
        TraceMongoRepository,
        TraceMySQLRepository,
    )

    def broken_recorder(_payload):
        raise RuntimeError("mongodb://user:secret@example/db failed")

    repo = TraceDualWriteRepository(
        TraceMySQLRepository(db_session),
        TraceMongoRepository(FakeCollection(fail_replace=True)),
        on_secondary_failure=broken_recorder,
    )

    row = await repo.insert(_trace())

    assert row.id is not None
    assert db_session.query(TraceRecord).count() == 1


@pytest.mark.asyncio
async def test_trace_mongo_read_fallback_logs_structured_context(db_session, caplog):
    from app.infra.trace_repository import (
        MongoReadTraceRepository,
        TraceMongoRepository,
        TraceMySQLRepository,
    )

    mysql_repo = TraceMySQLRepository(db_session)
    saved = mysql_repo.insert(_trace())
    mongo_repo = TraceMongoRepository(FakeCollection())
    repo = MongoReadTraceRepository(mysql_repo, mongo_repo)

    with caplog.at_level("WARNING"):
        rows = await repo.get_by_request_id(farm_id=1, request_id="req-1")

    assert rows[0].id == saved.id
    assert "code=mongo_read_fallback_to_mysql" in caplog.text
    assert "object_type=trace" in caplog.text
    assert "farm_id=1" in caplog.text
    assert "business_id=req-1" in caplog.text


@pytest.mark.asyncio
async def test_trace_selector_modes_use_expected_repository(db_session):
    from app.infra.trace_repository import (
        MongoReadTraceRepository,
        TraceDualWriteRepository,
        TraceMongoRepository,
        TraceMySQLRepository,
        build_trace_repository,
    )

    collection = FakeCollection()

    assert isinstance(
        build_trace_repository("mysql", db_session, collection), TraceMySQLRepository
    )
    assert isinstance(
        build_trace_repository("dual", db_session, collection), TraceDualWriteRepository
    )
    assert isinstance(
        build_trace_repository("mongo-read", db_session, collection),
        MongoReadTraceRepository,
    )
    assert isinstance(
        build_trace_repository("mongo", db_session, collection), TraceMongoRepository
    )
