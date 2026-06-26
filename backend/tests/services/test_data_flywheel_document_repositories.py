"""Data Flywheel 文档 Repository 行为测试。"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)


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
        self.updates: list[dict] = []

    async def replace_one(self, filter_doc, replacement, upsert=False):
        if self.fail_replace:
            raise RuntimeError("mongodb://user:secret@example/db failed")
        self.filters.append(dict(filter_doc))
        self.replacements.append(dict(replacement))
        return {"upserted": upsert}

    async def update_one(self, filter_doc, update_doc):
        self.filters.append(dict(filter_doc))
        self.updates.append(dict(update_doc))
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in filter_doc.items()):
                doc.update(update_doc.get("$set", {}))
        return {"matched_count": 1}

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
                else (
                    doc.get(key) != value["$ne"]
                    if isinstance(value, dict) and "$ne" in value
                    else doc.get(key) == value
                )
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
                if all(
                    doc.get(key) != value["$ne"]
                    if isinstance(value, dict) and "$ne" in value
                    else doc.get(key) == value
                    for key, value in filter_doc.items()
                )
            ]
        )


def _prelabel(**overrides) -> AgentDataFlywheelPrelabel:
    values = {
        "farm_id": 1,
        "sample_id": "turn:1:s1:1",
        "sample_type": "session_turn",
        "session_id": "s1",
        "turn_id": 1,
        "request_id": "req-1",
        "source": "llm_judge",
        "status": "pending",
        "labels": ["bad_reply"],
        "severity": "P1",
        "confidence": 0.8,
        "reason": "reason",
        "judge_model": "judge",
        "prompt_version": "v1",
    }
    values.update(overrides)
    return AgentDataFlywheelPrelabel(**values)


def _case_draft(**overrides) -> AgentCaseDraft:
    values = {
        "farm_id": 1,
        "draft_id": "draft-1",
        "source_sample_id": "turn:1:s1:1",
        "target_type": "simulation",
        "status": "draft",
        "case_json": {"case_id": "case-1"},
    }
    values.update(overrides)
    return AgentCaseDraft(**values)


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


def _chain(**overrides) -> AgentReviewIssueChain:
    values = {
        "farm_id": 1,
        "chain_id": "chain-1",
        "session_id": "s1",
        "trigger_turn_id": 1,
        "context_turn_ids": [],
        "result_turn_ids": [],
        "status": "accepted",
        "severity": "P1",
        "dominant_signal": "judge",
        "final_labels": ["bad_reply"],
        "source_label_ids": [],
    }
    values.update(overrides)
    return AgentReviewIssueChain(**values)


@pytest.mark.asyncio
async def test_data_flywheel_mongo_repositories_always_filter_by_farm_id():
    from app.modules.data_flywheel.document_repositories import (
        MongoCaseDraftRepository,
        MongoPrelabelRepository,
        MongoRepairPackRepository,
        MongoReviewIssueChainRepository,
    )

    collections = {
        "prelabels": FakeCollection(
            [{"mysqlId": 1, "farmId": 1, "sampleId": "s", "source": "llm_judge"}]
        ),
        "caseDrafts": FakeCollection(
            [{"mysqlId": 2, "farmId": 1, "draftId": "d", "sourceSampleId": "s"}]
        ),
        "repairPacks": FakeCollection(
            [
                {
                    "mysqlId": 3,
                    "farmId": 1,
                    "packId": "p",
                    "dedupKey": "k",
                    "status": "exported",
                }
            ]
        ),
        "reviewIssueChains": FakeCollection(
            [
                {
                    "mysqlId": 4,
                    "farmId": 1,
                    "chainId": "c",
                    "sessionId": "s",
                    "status": "accepted",
                }
            ]
        ),
    }

    await MongoPrelabelRepository(collections["prelabels"]).list_by_samples(
        farm_id=1, sample_ids=["s"]
    )
    await MongoCaseDraftRepository(collections["caseDrafts"]).get_by_draft_id(
        farm_id=1, draft_id="d"
    )
    await MongoRepairPackRepository(
        collections["repairPacks"]
    ).find_active_by_dedup_key(farm_id=1, dedup_key="k")
    await MongoReviewIssueChainRepository(
        collections["reviewIssueChains"]
    ).list_by_session(farm_id=1, session_id="s")

    for collection in collections.values():
        assert collection.filters
        assert all(filter_doc["farmId"] == 1 for filter_doc in collection.filters)

    with pytest.raises(ValueError, match="MONGO_FARM_ID_REQUIRED"):
        await MongoRepairPackRepository(collections["repairPacks"]).get_by_pack_id(
            farm_id=None, pack_id="p"
        )  # type: ignore[arg-type]


def test_data_flywheel_mysql_repositories_cover_core_crud(db_session):
    from app.modules.data_flywheel.document_repositories import (
        MySQLCaseDraftRepository,
        MySQLPrelabelRepository,
        MySQLRepairPackRepository,
        MySQLReviewIssueChainRepository,
    )

    prelabels = MySQLPrelabelRepository(db_session)
    prelabel = prelabels.create(_prelabel())
    prelabels.update_review_fields(
        farm_id=1,
        prelabel_id=prelabel.id,
        sample_id="turn:1:s1:1",
        status="accepted",
        reviewed_by="admin",
        reviewed_at=datetime(2026, 1, 1),
        accepted_label_ids=[9],
    )
    assert (
        prelabels.get_by_id_and_sample(
            farm_id=1, prelabel_id=prelabel.id, sample_id="turn:1:s1:1"
        ).status
        == "accepted"
    )

    drafts = MySQLCaseDraftRepository(db_session)
    draft = drafts.create(_case_draft())
    assert drafts.get_by_draft_id(farm_id=1, draft_id=draft.draft_id).id == draft.id
    assert (
        drafts.list_by_source_sample(farm_id=1, source_sample_id="turn:1:s1:1").total
        == 1
    )

    packs = MySQLRepairPackRepository(db_session)
    pack = packs.create(_repair_pack())
    assert packs.find_active_by_dedup_key(farm_id=1, dedup_key="dedup-1").id == pack.id
    packs.update_fields(
        farm_id=1, pack_id="pack-1", status="resolved", repair_note="done"
    )
    assert packs.get_by_pack_id(farm_id=1, pack_id="pack-1").status == "resolved"

    chains = MySQLReviewIssueChainRepository(db_session)
    chain = chains.save(_chain())
    chains.update_review_fields(
        farm_id=1, chain_id=chain.chain_id, reviewer_comment="ok"
    )
    assert (
        chains.get_by_chain_id(farm_id=1, chain_id="chain-1").reviewer_comment == "ok"
    )
    assert chains.list_by_session(farm_id=1, session_id="s1").total == 1


@pytest.mark.asyncio
async def test_data_flywheel_dual_write_order_and_mongo_failure_tolerance(db_session):
    from app.modules.data_flywheel.document_repositories import (
        DualWriteRepairPackRepository,
        MongoRepairPackRepository,
        MySQLRepairPackRepository,
    )

    events = []
    mysql_repo = MySQLRepairPackRepository(db_session)
    mongo_repo = MongoRepairPackRepository(FakeCollection(fail_replace=True))
    repo = DualWriteRepairPackRepository(
        mysql_repo,
        mongo_repo,
        on_secondary_failure=lambda payload: events.append(payload),
    )

    row = await repo.create(_repair_pack())

    assert row.id is not None
    assert db_session.query(AgentRepairPack).count() == 1
    assert events[0]["code"] == "mongo_secondary_write_failed"
    assert events[0]["object_type"] == "repair_pack"
    assert events[0]["business_id"] == "pack-1"
    assert "secret" not in events[0]["error"]


@pytest.mark.asyncio
async def test_data_flywheel_dual_write_can_record_compensation_task(db_session):
    from app.infra.mongo_compensation import (
        MongoCompensationRecorder,
        MongoCompensationTask,
    )
    from app.modules.data_flywheel.document_repositories import (
        DualWriteRepairPackRepository,
        MongoRepairPackRepository,
        MySQLRepairPackRepository,
    )

    recorder = MongoCompensationRecorder(db_session)
    repo = DualWriteRepairPackRepository(
        MySQLRepairPackRepository(db_session),
        MongoRepairPackRepository(FakeCollection(fail_replace=True)),
        on_secondary_failure=recorder.record_failure,
    )

    row = await repo.create(_repair_pack())

    task = db_session.query(MongoCompensationTask).one()
    assert task.object_type == "repair_pack"
    assert task.farm_id == 1
    assert task.business_id == row.pack_id
    assert task.mysql_id == row.id
    assert task.status == "pending"
    assert "secret" not in task.last_error


@pytest.mark.asyncio
async def test_data_flywheel_dual_write_ignores_compensation_recorder_failure(
    db_session,
):
    from app.modules.data_flywheel.document_repositories import (
        DualWriteRepairPackRepository,
        MongoRepairPackRepository,
        MySQLRepairPackRepository,
    )

    def broken_recorder(_payload):
        raise RuntimeError("mongodb://user:secret@example/db failed")

    repo = DualWriteRepairPackRepository(
        MySQLRepairPackRepository(db_session),
        MongoRepairPackRepository(FakeCollection(fail_replace=True)),
        on_secondary_failure=broken_recorder,
    )

    row = await repo.create(_repair_pack())

    assert row.id is not None
    assert db_session.query(AgentRepairPack).count() == 1


@pytest.mark.asyncio
async def test_data_flywheel_dual_write_updates_secondary_after_mysql(db_session):
    from app.modules.data_flywheel.document_repositories import (
        DualWriteRepairPackRepository,
        MongoRepairPackRepository,
        MySQLRepairPackRepository,
    )

    mysql_repo = MySQLRepairPackRepository(db_session)
    saved = mysql_repo.create(_repair_pack())
    collection = FakeCollection()
    repo = DualWriteRepairPackRepository(
        mysql_repo,
        MongoRepairPackRepository(collection),
    )

    updated = await repo.update_fields(
        farm_id=1,
        pack_id=saved.pack_id,
        status="resolved",
        repair_note="done",
    )

    assert updated.status == "resolved"
    assert collection.replacements[-1]["status"] == "resolved"
    assert collection.replacements[-1]["repairNote"] == "done"


@pytest.mark.asyncio
async def test_data_flywheel_selector_modes(db_session):
    from app.modules.data_flywheel.document_repositories import (
        DualWritePrelabelRepository,
        MongoReadPrelabelRepository,
        MongoPrelabelRepository,
        MySQLPrelabelRepository,
        build_data_flywheel_repository,
    )

    collection = FakeCollection()

    assert isinstance(
        build_data_flywheel_repository("prelabels", "mysql", db_session, collection),
        MySQLPrelabelRepository,
    )
    assert isinstance(
        build_data_flywheel_repository("prelabels", "dual", db_session, collection),
        DualWritePrelabelRepository,
    )
    assert isinstance(
        build_data_flywheel_repository(
            "prelabels", "mongo-read", db_session, collection
        ),
        MongoReadPrelabelRepository,
    )
    assert isinstance(
        build_data_flywheel_repository("prelabels", "mongo", db_session, collection),
        MongoPrelabelRepository,
    )


@pytest.mark.asyncio
async def test_data_flywheel_mongo_read_falls_back_to_mysql_on_miss(db_session, caplog):
    from app.modules.data_flywheel.document_repositories import (
        MongoPrelabelRepository,
        MongoReadPrelabelRepository,
        MySQLPrelabelRepository,
    )

    mysql_repo = MySQLPrelabelRepository(db_session)
    saved = mysql_repo.create(_prelabel())
    mongo_repo = MongoPrelabelRepository(FakeCollection())
    repo = MongoReadPrelabelRepository(mysql_repo, mongo_repo)

    with caplog.at_level("WARNING"):
        row = await repo.get_by_id_and_sample(
            farm_id=1,
            prelabel_id=saved.id,
            sample_id="turn:1:s1:1",
        )

    assert row.id == saved.id
    assert "code=mongo_read_fallback_to_mysql" in caplog.text
    assert "object_type=prelabel" in caplog.text
    assert "farm_id=1" in caplog.text
    assert f"business_id={saved.id}" in caplog.text
