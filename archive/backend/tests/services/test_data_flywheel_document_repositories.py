"""Data Flywheel Mongo 文档 Repository 行为测试。"""

from __future__ import annotations

import importlib

import pytest

from app.platforms.data_flywheel.models import (
    AgentCaseDraft,
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
    def __init__(self, docs: list[dict] | None = None):
        self.docs = docs or []
        self.filters: list[dict] = []
        self.replacements: list[dict] = []
        self.updates: list[dict] = []

    async def replace_one(self, filter_doc, replacement, upsert=False):
        self.filters.append(dict(filter_doc))
        self.replacements.append(dict(replacement))
        return {"upserted": upsert}

    async def update_one(self, filter_doc, update_doc):
        self.filters.append(dict(filter_doc))
        self.updates.append(dict(update_doc))
        for doc in self.docs:
            if _matches(doc, filter_doc):
                doc.update(update_doc.get("$set", {}))
        return {"matched_count": 1}

    async def find_one(self, filter_doc):
        self.filters.append(dict(filter_doc))
        for doc in self.docs:
            if _matches(doc, filter_doc):
                return doc
        return None

    def find(self, filter_doc):
        self.filters.append(dict(filter_doc))
        return FakeCursor([doc for doc in self.docs if _matches(doc, filter_doc)])

    async def count_documents(self, filter_doc):
        self.filters.append(dict(filter_doc))
        return len([doc for doc in self.docs if _matches(doc, filter_doc)])


def _matches(doc: dict, filter_doc: dict) -> bool:
    for key, value in filter_doc.items():
        actual = doc.get(key)
        if isinstance(value, dict) and "$in" in value:
            if actual not in value["$in"]:
                return False
            continue
        if isinstance(value, dict) and "$ne" in value:
            if actual == value["$ne"]:
                return False
            continue
        if actual != value:
            return False
    return True


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


def test_data_flywheel_aggregate_uses_shared_repository_selector() -> None:
    shared = importlib.import_module("app.platforms.shared.repository_selector")
    aggregate = importlib.import_module("app.platforms.data_flywheel.document_repositories")

    assert (
        aggregate.build_data_flywheel_repository
        is shared.build_data_flywheel_repository
    )


@pytest.mark.asyncio
async def test_data_flywheel_mongo_repositories_always_filter_by_farm_id():
    from app.platforms.data_flywheel.document_repositories import (
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


@pytest.mark.asyncio
async def test_data_flywheel_mongo_repository_assigns_id_without_mysql_row():
    from app.platforms.data_flywheel.document_repositories import MongoCaseDraftRepository

    collection = FakeCollection()
    repo = MongoCaseDraftRepository(collection)
    row = _case_draft()

    saved = await repo.create(row)

    assert saved.id is not None
    assert collection.filters == [{"mysqlId": saved.id}]
    assert collection.replacements[0]["mysqlId"] == saved.id


@pytest.mark.asyncio
async def test_data_flywheel_selector_rejects_removed_gray_backends(db_session):
    from app.platforms.data_flywheel.document_repositories import (
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
        build_data_flywheel_repository("prelabels", "mongo", db_session, collection),
        MongoPrelabelRepository,
    )

    with pytest.raises(ValueError) as exc:
        build_data_flywheel_repository("prelabels", "dual", db_session, collection)
    assert exc.value.args[0]["code"] == "INVALID_STORAGE_BACKEND"
    assert exc.value.args[0]["backend"] == "dual"


@pytest.mark.asyncio
async def test_data_flywheel_review_issue_chain_mongo_list_uses_expected_order():
    from app.platforms.data_flywheel.document_repositories import (
        MongoReviewIssueChainRepository,
    )

    collection = FakeCollection(
        [
            {
                "mysqlId": 1,
                "farmId": 1,
                "chainId": "chain-1",
                "sessionId": "s1",
                "status": "accepted",
                "severity": "P1",
            },
            {
                "mysqlId": 2,
                "farmId": 1,
                "chainId": "chain-2",
                "sessionId": "s1",
                "status": "accepted",
                "severity": "P0",
            },
        ]
    )

    page = await MongoReviewIssueChainRepository(collection).list_by_session(
        farm_id=1,
        session_id="s1",
    )

    assert page.total == 2
    assert [row.chain_id for row in page.items] == ["chain-1", "chain-2"]


@pytest.mark.asyncio
async def test_data_flywheel_mongo_repository_updates_mapped_fields():
    from app.platforms.data_flywheel.document_repositories import (
        MongoReviewIssueChainRepository,
    )

    collection = FakeCollection(
        [
            {
                "mysqlId": 4,
                "farmId": 1,
                "chainId": "chain-1",
                "sessionId": "s1",
                "status": "accepted",
            }
        ]
    )

    row = await MongoReviewIssueChainRepository(collection).update_review_fields(
        farm_id=1,
        chain_id="chain-1",
        reviewer_comment="ok",
    )

    assert row is not None
    assert row.reviewer_comment == "ok"
    assert collection.updates[-1] == {"$set": {"reviewerComment": "ok"}}
