"""第 5 组服务接入 Repository 的 focused tests。"""

from __future__ import annotations

import asyncio

import pytest

from app.models.data_flywheel import AgentDataFlywheelPrelabel, AgentRepairPack
from app.models.user import User
from app.models.token_stats import TokenDailyStats
from app.models.trace import TraceRecord


class AsyncSpyRepository:
    """用 async 方法验证同步服务不会遗留未 await coroutine。"""

    def __init__(self, row=None, page=None, rows=None) -> None:
        self.row = row
        self.page = page
        self.rows = rows or []
        self.calls: list[tuple[str, dict]] = []

    async def create(self, row):
        self.calls.append(("create", {"row": row}))
        row.id = row.id or 123
        return row

    async def get_by_id_and_sample(self, **kwargs):
        self.calls.append(("get_by_id_and_sample", kwargs))
        return self.row

    async def update_review_fields(self, **kwargs):
        self.calls.append(("update_review_fields", kwargs))
        for key, value in kwargs.items():
            if hasattr(self.row, key):
                setattr(self.row, key, value)
        return self.row

    async def list_by_samples(self, **kwargs):
        self.calls.append(("list_by_samples", kwargs))
        return list(self.rows)

    async def find_active_by_dedup_key(self, **kwargs):
        self.calls.append(("find_active_by_dedup_key", kwargs))
        return self.row


class Page:
    def __init__(self, items, total=1, page=1, page_size=20) -> None:
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size


def test_trace_dao_flush_uses_trace_repository_and_keeps_token_stats_mysql(
    monkeypatch, db_session
) -> None:
    from app.infra import trace_dao

    calls: list[TraceRecord] = []

    class Repo:
        def insert(self, row):
            calls.append(row)
            return row

    monkeypatch.setattr(trace_dao, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(trace_dao, "get_trace_repository", lambda db: Repo())
    db_session.add(
        User(
            id="user-1",
            phone="18800000000",
            password_hash="hash",
            nickname="测试用户",
            status="active",
        )
    )
    db_session.commit()

    dao = trace_dao.TraceDAO()
    dao.record(
        {
            "farm_id": 1,
            "request_id": "req-repo",
            "session_id": "sess-repo",
            "round_index": 0,
            "node_type": "llm_call",
            "node_name": "planner",
            "status": "success",
        }
    )

    assert asyncio.run(dao.flush_now()) == 1
    assert calls[0].request_id == "req-repo"

    dao.accumulate_token_stats(
        farm_id=1,
        user_id="user-1",
        date_str="2026-06-26",
        model="qwen",
        call_type="chat",
        prompt_tokens=3,
        completion_tokens=4,
    )
    assert db_session.query(TraceRecord).count() == 0
    assert db_session.query(TokenDailyStats).count() == 1


@pytest.mark.asyncio
async def test_trace_dao_flush_awaits_async_repository(monkeypatch, db_session) -> None:
    from app.infra import trace_dao

    calls: list[TraceRecord] = []

    class Repo:
        async def insert(self, row):
            calls.append(row)
            return row

    monkeypatch.setattr(trace_dao, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(trace_dao, "get_trace_repository", lambda db: Repo())

    dao = trace_dao.TraceDAO()
    dao.record(
        {
            "farm_id": 1,
            "request_id": "req-async",
            "session_id": "sess-async",
            "round_index": 0,
            "node_type": "llm_call",
            "node_name": "planner",
            "status": "success",
        }
    )

    assert await dao.flush_now() == 1
    assert calls[0].request_id == "req-async"


def test_prelabel_review_uses_repository(monkeypatch, db_session) -> None:
    from app.modules.data_flywheel import service

    row = AgentDataFlywheelPrelabel(
        id=9,
        farm_id=1,
        sample_id="turn:1:sess:1",
        sample_type=service.SAMPLE_TYPE_SESSION_TURN,
        session_id="sess",
        turn_id=1,
        request_id="req",
        source=service.PRELABEL_SOURCE_LLM_JUDGE,
        status=service.PRELABEL_STATUS_PENDING,
        labels=["bad_reply"],
    )
    repo = AsyncSpyRepository(row=row)
    monkeypatch.setattr(service, "get_data_flywheel_repository", lambda *_: repo)
    monkeypatch.setattr(
        service,
        "_upsert_sample_label_row",
        lambda *_, **__: type("Label", (), {"id": 44})(),
    )

    result = service.accept_sample_prelabel(
        db_session,
        farm_id=1,
        sample_id="turn:1:sess:1",
        prelabel_id=9,
        annotator_id="admin",
    )

    assert result["status"] == service.PRELABEL_STATUS_ACCEPTED
    assert [name for name, _ in repo.calls] == [
        "get_by_id_and_sample",
        "update_review_fields",
    ]


def test_repair_pack_dedup_uses_repository(monkeypatch, db_session, tmp_path) -> None:
    from app.modules.data_flywheel import repair_pack_repository as module

    row = AgentRepairPack(
        id=7,
        farm_id=1,
        pack_id="repair-existing",
        fix_target="router",
        labels=["bad_reply"],
        source_sample_ids=["turn:1:sess:1"],
        source_label_ids=[],
        dedup_key="dedup",
        status=module.REPAIR_PACK_STATUS_EXPORTED,
        export_path=str(tmp_path / "repair-existing"),
        manifest_json={},
    )
    repo = AsyncSpyRepository(row=row)
    monkeypatch.setattr(module, "get_data_flywheel_repository", lambda *_: repo)
    monkeypatch.setattr(
        module,
        "list_repair_candidates",
        lambda *_, **__: {
            "items": [
                {
                    "sample_id": "turn:1:sess:1",
                    "fix_target": "router",
                    "labels": ["bad_reply"],
                }
            ]
        },
    )
    monkeypatch.setattr(
        module,
        "get_sample_detail",
        lambda *_, **__: {
            "sample": {"sample_id": "turn:1:sess:1"},
            "quality_labels": ["bad_reply"],
        },
    )
    monkeypatch.setattr(module, "_compute_dedup_key", lambda **_: "dedup")

    result = module.create_repair_pack(
        db_session,
        farm_id=1,
        export_base_dir=tmp_path,
        limit=1,
    )

    assert result["deduplicated"] is True
    assert repo.calls[0] == (
        "find_active_by_dedup_key",
        {"farm_id": 1, "dedup_key": "dedup"},
    )
