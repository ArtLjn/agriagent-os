"""MySQL 到 MongoDB 迁移工具测试。"""

from __future__ import annotations

import pytest

from app.models.data_flywheel import AgentRepairPack


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def sort(self, *_args):
        return self

    def limit(self, limit: int):
        self._docs = self._docs[:limit]
        return self

    async def to_list(self, _length=None):
        return list(self._docs)


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None, fail: bool = False) -> None:
        self.docs = docs or []
        self.fail = fail
        self.replacements: list[tuple[dict, dict, bool]] = []

    async def replace_one(self, filter_doc, doc, upsert=False):
        if self.fail:
            raise RuntimeError("write failed")
        self.replacements.append((dict(filter_doc), dict(doc), upsert))
        existing = next(
            (item for item in self.docs if item.get("mysqlId") == doc.get("mysqlId")),
            None,
        )
        if existing is None:
            self.docs.append(dict(doc))
        else:
            existing.update(doc)

    def find(self, filter_doc):
        if "mysqlId" in filter_doc and "$in" in filter_doc["mysqlId"]:
            allowed = set(filter_doc["mysqlId"]["$in"])
            docs = [doc for doc in self.docs if doc.get("mysqlId") in allowed]
        else:
            docs = list(self.docs)
        return FakeCursor(docs)

    async def count_documents(self, _filter_doc):
        return len(self.docs)


class FakeDatabase:
    def __init__(self, collections: dict[str, FakeCollection]) -> None:
        self.collections = collections

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


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


@pytest.mark.asyncio
async def test_backfill_table_dry_run_scans_without_writing(db_session):
    from scripts.migrate_mysql_to_mongo import backfill_table

    db_session.add(_repair_pack())
    db_session.commit()
    database = FakeDatabase({"repairPacks": FakeCollection()})

    stats = await backfill_table(
        db_session,
        database,
        table="agent_repair_packs",
        dry_run=True,
    )

    assert stats.scanned == 1
    assert stats.skipped == 1
    assert database["repairPacks"].replacements == []


@pytest.mark.asyncio
async def test_backfill_table_upserts_by_mysql_id(db_session):
    from scripts.migrate_mysql_to_mongo import backfill_table

    db_session.add(_repair_pack())
    db_session.commit()
    database = FakeDatabase({"repairPacks": FakeCollection()})

    stats = await backfill_table(db_session, database, table="agent_repair_packs")

    assert stats.written == 1
    filter_doc, doc, upsert = database["repairPacks"].replacements[0]
    assert filter_doc == {"mysqlId": doc["mysqlId"]}
    assert upsert is True


@pytest.mark.asyncio
async def test_verify_table_reports_missing_ids_and_threshold(db_session):
    from scripts.migrate_mysql_to_mongo import verify_table

    db_session.add(_repair_pack())
    db_session.commit()
    database = FakeDatabase({"repairPacks": FakeCollection()})

    report = await verify_table(
        db_session,
        database,
        table="agent_repair_packs",
        mismatch_threshold=0,
    )

    assert report.ok is False
    assert report.mysql_count == 1
    assert report.mongo_count == 0
    assert report.missing_mysql_ids


@pytest.mark.asyncio
async def test_reverse_sync_preview_reports_missing_and_conflicts(db_session):
    from scripts.migrate_mysql_to_mongo import reverse_sync_preview

    row = _repair_pack()
    db_session.add(row)
    db_session.commit()
    database = FakeDatabase(
        {
            "repairPacks": FakeCollection(
                [
                    {
                        "mysqlId": row.id,
                        "farmId": 999,
                        "packId": row.pack_id,
                        "status": row.status,
                    },
                    {"mysqlId": row.id + 100, "farmId": 1, "packId": "missing"},
                ]
            )
        }
    )

    report = await reverse_sync_preview(
        db_session,
        database,
        table="agent_repair_packs",
    )

    assert report["mode"] == "preview_only"
    assert row.id + 100 in report["missing_mysql_ids"]
    assert report["conflicts"][0]["mysqlId"] == row.id
