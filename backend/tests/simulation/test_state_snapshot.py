"""测试数据库状态快照系统。"""

from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, _set_sqlite_pragma
from app.simulation.state_snapshot import DbStateSnapshot, _TABLE_PRIMARY_KEYS

_test_engine = create_engine(
    "sqlite:///tests/test_simulation.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


class TestTablePrimaryKeys:
    def test_all_tables_have_pk(self):
        assert "cost_records" in _TABLE_PRIMARY_KEYS
        assert _TABLE_PRIMARY_KEYS["cost_records"] == "id"


class TestDbStateSnapshot:
    def _get_db(self):
        Base.metadata.create_all(bind=_test_engine)
        db = _TestSession()
        from app.models.farm import Farm
        db.add(Farm(id=1, name="农场1"))
        db.add(Farm(id=2, name="农场2"))
        db.commit()
        return db

    @pytest.mark.asyncio
    async def test_take_snapshot_empty(self):
        db = self._get_db()
        try:
            snapshot = DbStateSnapshot(db, farm_id=1)
            result = await snapshot.take(["cost_records"])
            assert "cost_records" in result
            assert result["cost_records"] == []
        finally:
            db.close()
            Base.metadata.drop_all(bind=_test_engine)

    @pytest.mark.asyncio
    async def test_take_snapshot_with_data(self):
        from app.models.cost import CostRecord

        db = self._get_db()
        try:
            record = CostRecord(
                farm_id=1,
                record_type="expense",
                category="化肥",
                amount=200,
                record_date=date(2026, 5, 26),
            )
            db.add(record)
            db.commit()

            snapshot = DbStateSnapshot(db, farm_id=1)
            result = await snapshot.take(["cost_records"])
            assert len(result["cost_records"]) == 1
            assert result["cost_records"][0]["category"] == "化肥"
        finally:
            db.close()
            Base.metadata.drop_all(bind=_test_engine)

    @pytest.mark.asyncio
    async def test_take_snapshot_farm_isolation(self):
        from app.models.cost import CostRecord

        db = self._get_db()
        try:
            db.add(CostRecord(
                farm_id=1, record_type="expense", category="化肥", amount=100, record_date=date(2026, 5, 26)
            ))
            db.add(CostRecord(
                farm_id=2, record_type="expense", category="农药", amount=200, record_date=date(2026, 5, 26)
            ))
            db.commit()

            snapshot = DbStateSnapshot(db, farm_id=1)
            result = await snapshot.take(["cost_records"])
            assert len(result["cost_records"]) == 1
            assert result["cost_records"][0]["category"] == "化肥"
        finally:
            db.close()
            Base.metadata.drop_all(bind=_test_engine)

    def test_compute_diff_no_changes(self):
        before = {"cost_records": [{"id": 1, "amount": 100, "__table__": "cost_records"}]}
        after = {"cost_records": [{"id": 1, "amount": 100, "__table__": "cost_records"}]}

        snapshot = DbStateSnapshot(None, farm_id=1)
        diff = snapshot.compute_diff(before, after)
        assert diff.added == []
        assert diff.removed == []
        assert diff.modified == []

    def test_compute_diff_added(self):
        before = {"cost_records": []}
        after = {"cost_records": [{"id": 1, "amount": 100, "__table__": "cost_records"}]}

        snapshot = DbStateSnapshot(None, farm_id=1)
        diff = snapshot.compute_diff(before, after)
        assert len(diff.added) == 1
        assert diff.added[0]["__table__"] == "cost_records"
        assert diff.removed == []
        assert diff.modified == []

    def test_compute_diff_removed(self):
        before = {"cost_records": [{"id": 1, "amount": 100, "__table__": "cost_records"}]}
        after = {"cost_records": []}

        snapshot = DbStateSnapshot(None, farm_id=1)
        diff = snapshot.compute_diff(before, after)
        assert len(diff.removed) == 1
        assert diff.removed[0]["__table__"] == "cost_records"

    def test_compute_diff_modified(self):
        before = {"cost_records": [{"id": 1, "amount": 100, "__table__": "cost_records"}]}
        after = {"cost_records": [{"id": 1, "amount": 200, "__table__": "cost_records"}]}

        snapshot = DbStateSnapshot(None, farm_id=1)
        diff = snapshot.compute_diff(before, after)
        assert len(diff.modified) == 1
        assert diff.modified[0]["__table__"] == "cost_records"
        assert "__before__" in diff.modified[0]
        assert "__after__" in diff.modified[0]

    def test_compute_diff_ignores_created_at(self):
        before = {"cost_records": [{"id": 1, "amount": 100, "created_at": "t1", "__table__": "cost_records"}]}
        after = {"cost_records": [{"id": 1, "amount": 100, "created_at": "t2", "__table__": "cost_records"}]}

        snapshot = DbStateSnapshot(None, farm_id=1)
        diff = snapshot.compute_diff(before, after)
        assert diff.modified == []

    def test_compute_diff_multiple_tables(self):
        before = {
            "cost_records": [{"id": 1, "amount": 100, "__table__": "cost_records"}],
            "farm_logs": [],
        }
        after = {
            "cost_records": [{"id": 1, "amount": 100, "__table__": "cost_records"}],
            "farm_logs": [{"id": 1, "operation_type": "浇水", "__table__": "farm_logs"}],
        }

        snapshot = DbStateSnapshot(None, farm_id=1)
        diff = snapshot.compute_diff(before, after)
        assert len(diff.added) == 1
        assert diff.added[0]["__table__"] == "farm_logs"

    def test_record_key(self):
        snapshot = DbStateSnapshot(None, farm_id=1)
        key = snapshot._record_key("cost_records", {"id": 5, "amount": 100})
        assert key == "cost_records:5"

    def test_normalize_record_excludes_timestamps(self):
        snapshot = DbStateSnapshot(None, farm_id=1)
        normalized = snapshot._normalize_record({
            "id": 1,
            "amount": 100,
            "created_at": "t1",
            "updated_at": "t2",
            "__table__": "cost_records",
        })
        assert "created_at" not in normalized
        assert "updated_at" not in normalized
        assert "__table__" not in normalized
        assert "id" in normalized
        assert "amount" in normalized
