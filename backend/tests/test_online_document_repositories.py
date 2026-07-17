"""第 2 期在线文档 Repository 测试。"""

from __future__ import annotations

import asyncio
import inspect
import threading
from datetime import date, datetime, timedelta
from typing import Any

from app.infra.online_document_repositories import (
    build_agent_record_repository,
    build_conversation_message_repository,
    build_guardrails_log_repository,
)
from app.infra.repository_runtime import run_maybe_awaitable
from app.models.agent_record import AgentRecord
from app.models.conversation import Conversation, ConversationMessage
from app.models.crop import CropTemplate
from app.models.cycle import CropCycle
from app.models.data_flywheel import AgentReviewIssueChain
from app.models.guardrails_log import GuardrailsLog
from app.models.user import User
from app.platforms.data_flywheel.document_repository_selector import (
    build_data_flywheel_repository,
)


class FakeResult:
    def __init__(self, *, deleted_count: int = 0, modified_count: int = 0) -> None:
        self.deleted_count = deleted_count
        self.modified_count = modified_count


class FakeCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def sort(self, keys):
        for field, direction in reversed(keys):
            self._docs.sort(
                key=lambda item: (item.get(field) is None, item.get(field)),
                reverse=direction < 0,
            )
        return self

    def skip(self, count: int):
        self._docs = self._docs[max(count, 0) :]
        return self

    def limit(self, count: int):
        if count >= 0:
            self._docs = self._docs[:count]
        return self

    async def to_list(self, _length=None):
        return list(self._docs)


class FakeCollection:
    def __init__(self, *, fail_find: bool = False) -> None:
        self.docs: list[dict[str, Any]] = []
        self.fail_find = fail_find

    async def replace_one(self, filter_doc, doc, upsert=False):
        existing = self._first(filter_doc)
        if existing is None:
            self.docs.append(dict(doc))
        else:
            existing.update(doc)

    def find(self, filter_doc):
        if self.fail_find:
            raise RuntimeError("mongo down")
        return FakeCursor([doc for doc in self.docs if _matches(doc, filter_doc)])

    async def find_one(self, filter_doc):
        if self.fail_find:
            raise RuntimeError("mongo down")
        return self._first(filter_doc)

    async def count_documents(self, filter_doc):
        return len([doc for doc in self.docs if _matches(doc, filter_doc)])

    async def delete_many(self, filter_doc):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not _matches(doc, filter_doc)]
        return FakeResult(deleted_count=before - len(self.docs))

    async def delete_one(self, filter_doc):
        for index, doc in enumerate(self.docs):
            if _matches(doc, filter_doc):
                del self.docs[index]
                return FakeResult(deleted_count=1)
        return FakeResult(deleted_count=0)

    async def update_many(self, filter_doc, update_doc):
        modified = 0
        values = update_doc.get("$set", {})
        for doc in self.docs:
            if _matches(doc, filter_doc):
                doc.update(values)
                modified += 1
        return FakeResult(modified_count=modified)

    def _first(self, filter_doc):
        return next((doc for doc in self.docs if _matches(doc, filter_doc)), None)


def _matches(doc: dict[str, Any], filter_doc: dict[str, Any]) -> bool:
    for key, expected in filter_doc.items():
        actual = doc.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$gte" in expected and not (actual >= expected["$gte"]):
                return False
            if "$lt" in expected and not (actual < expected["$lt"]):
                return False
            continue
        if actual != expected:
            return False
    return True


def _seed_user_and_conversation(db_session):
    db_session.add(
        User(id="repo-user", phone="13900000001", password_hash="x", nickname="测试")
    )
    db_session.flush()
    conversation = Conversation(
        farm_id=1, session_id="repo-session", user_id="repo-user"
    )
    db_session.add(conversation)
    db_session.flush()
    return conversation


def test_repository_runtime_uses_platform_shared_selector() -> None:
    import app.infra.repository_runtime as repository_runtime
    from app.platforms.shared.repository_selector import (
        build_data_flywheel_repository as shared_builder,
    )

    source = inspect.getsource(repository_runtime)

    assert repository_runtime.build_data_flywheel_repository is shared_builder
    assert "app.platforms.data_flywheel" not in source


def test_run_maybe_awaitable_uses_registered_main_loop_from_worker_thread():
    from app.infra import repository_runtime

    async def _worker_loop_id():
        return id(asyncio.get_running_loop())

    async def _main():
        main_loop = asyncio.get_running_loop()
        repository_runtime.set_main_event_loop(main_loop)
        result: dict[str, Any] = {}

        def _worker():
            result["loop_id"] = run_maybe_awaitable(_worker_loop_id())

        thread = threading.Thread(target=_worker)
        thread.start()
        await asyncio.to_thread(thread.join)
        return result["loop_id"], id(main_loop)

    loop_id, main_loop_id = asyncio.run(_main())

    assert loop_id == main_loop_id
    repository_runtime.set_main_event_loop(None)


def test_run_maybe_awaitable_prefers_main_loop_from_worker_event_loop():
    from app.infra import repository_runtime

    async def _worker_loop_id():
        return id(asyncio.get_running_loop())

    async def _main():
        main_loop = asyncio.get_running_loop()
        repository_runtime.set_main_event_loop(main_loop)
        result: dict[str, Any] = {}

        async def _worker_async():
            result["loop_id"] = run_maybe_awaitable(_worker_loop_id())

        def _worker():
            asyncio.run(_worker_async())

        thread = threading.Thread(target=_worker)
        thread.start()
        await asyncio.to_thread(thread.join)
        return result["loop_id"], id(main_loop)

    loop_id, main_loop_id = asyncio.run(_main())

    assert loop_id == main_loop_id
    repository_runtime.set_main_event_loop(None)


def test_conversation_repository_mysql_dual_mongo_read_and_mongo(db_session):
    conversation = _seed_user_and_conversation(db_session)
    mysql_repo = build_conversation_message_repository("mysql", db_session)
    saved = mysql_repo.save_one(
        ConversationMessage(
            conversation_id=conversation.id,
            conversation=conversation,
            role="user",
            content="mysql 消息",
            turn_id=7,
        )
    )

    assert mysql_repo.get_recent(farm_id=1, conversation_id=conversation.id, limit=1)[
        0
    ].id
    collection = FakeCollection()
    hook_calls: list[dict[str, Any]] = []
    dual_repo = build_conversation_message_repository(
        "dual",
        db_session,
        collection=collection,
        hook=lambda payload: hook_calls.append(payload),
    )
    dual_saved = run_maybe_awaitable(
        dual_repo.save_one(
            ConversationMessage(
                conversation_id=conversation.id,
                conversation=conversation,
                role="assistant",
                content="dual 消息",
                turn_id=8,
            )
        )
    )
    assert hook_calls == []
    assert collection.docs[-1]["mysqlId"] == dual_saved.id
    assert collection.docs[-1]["farmId"] == 1

    mongo_read_repo = build_conversation_message_repository(
        "mongo-read", db_session, collection=FakeCollection(fail_find=True)
    )
    fallback_rows = run_maybe_awaitable(
        mongo_read_repo.get_recent(farm_id=1, conversation_id=conversation.id, limit=3)
    )
    assert [row.id for row in fallback_rows] == [saved.id, dual_saved.id]

    mongo_repo = build_conversation_message_repository(
        "mongo",
        db_session,
        collection=collection,
    )
    mongo_rows = run_maybe_awaitable(
        mongo_repo.list_by_turn_ids(farm_id=1, turn_ids=[8])
    )
    assert [row.content for row in mongo_rows] == ["dual 消息"]

    mongo_only = run_maybe_awaitable(
        mongo_repo.save_one(
            ConversationMessage(
                conversation_id=conversation.id,
                role="user",
                content="mongo only",
            )
        )
    )
    assert mongo_only.id is not None
    assert collection.docs[-1]["mysqlId"] == mongo_only.id
    assert collection.docs[-1]["farmId"] == 1
    assert collection.docs[-1]["sessionId"] == "repo-session"
    assert collection.docs[-1]["createdAt"] is not None


def test_agent_record_repository_modes_cache_paging_and_cycle_cleanup(db_session):
    collection = FakeCollection()
    template = CropTemplate(farm_id=1, name="测试作物")
    db_session.add(template)
    db_session.flush()
    cycle = CropCycle(
        farm_id=1,
        name="测试周期",
        crop_template_id=template.id,
        start_date=date.today(),
    )
    db_session.add(cycle)
    db_session.flush()
    mysql_repo = build_agent_record_repository("mysql", db_session)
    daily = mysql_repo.create(
        AgentRecord(farm_id=1, cycle_id=cycle.id, record_type="daily", content="daily")
    )
    report = mysql_repo.create(
        AgentRecord(
            farm_id=1, cycle_id=cycle.id, record_type="report", content="report"
        )
    )

    assert mysql_repo.find_daily_cache(
        farm_id=1, since=datetime.now() - timedelta(days=1)
    ).id
    assert mysql_repo.list_report_page(farm_id=1, page=1, size=10).total == 1

    dual_repo = build_agent_record_repository("dual", db_session, collection=collection)
    dual_record = run_maybe_awaitable(
        dual_repo.create(AgentRecord(farm_id=1, record_type="chat", content="chat"))
    )
    assert collection.docs[-1]["mysqlId"] == dual_record.id

    mongo_repo = build_agent_record_repository(
        "mongo", db_session, collection=collection
    )
    mongo_only_record = run_maybe_awaitable(
        mongo_repo.create(AgentRecord(farm_id=1, record_type="chat", content="mongo"))
    )
    assert mongo_only_record.id is not None
    assert collection.docs[-1]["mysqlId"] == mongo_only_record.id

    mongo_chat_rows = run_maybe_awaitable(
        mongo_repo.list_advice_history(farm_id=1, limit=5)
    )
    assert [row.id for row in mongo_chat_rows] == [
        mongo_only_record.id,
        dual_record.id,
    ]

    mongo_read_repo = build_agent_record_repository(
        "mongo-read",
        db_session,
        collection=FakeCollection(fail_find=True),
    )
    fallback_page = run_maybe_awaitable(
        mongo_read_repo.list_report_page(farm_id=1, page=1, size=10)
    )
    assert [row.id for row in fallback_page.items] == [report.id]

    assert run_maybe_awaitable(dual_repo.clear_cycle_reference(cycle_id=cycle.id)) == 2
    db_session.refresh(daily)
    db_session.refresh(report)
    assert daily.cycle_id is None
    assert report.cycle_id is None


def test_review_issue_chain_repository_lists_from_mongo(db_session):
    collection = FakeCollection()
    repo = build_data_flywheel_repository(
        "review_issue_chains",
        "mongo",
        db_session,
        collection=collection,
    )
    first = run_maybe_awaitable(
        repo.save(
            AgentReviewIssueChain(
                farm_id=1,
                chain_id="chain:1:s1:1",
                session_id="s1",
                trigger_turn_id=1,
                status="needs_evidence",
                severity="P1",
                dominant_signal="rule",
                context_turn_ids=[],
                result_turn_ids=[],
                final_labels=[],
                source_label_ids=[],
                created_at=datetime(2026, 7, 1, 9, 0, 0),
                updated_at=datetime(2026, 7, 1, 9, 0, 0),
            )
        )
    )
    second = run_maybe_awaitable(
        repo.save(
            AgentReviewIssueChain(
                farm_id=1,
                chain_id="chain:1:s2:2",
                session_id="s2",
                trigger_turn_id=2,
                status="needs_evidence",
                severity="P0",
                dominant_signal="judge",
                context_turn_ids=[],
                result_turn_ids=[],
                final_labels=[],
                source_label_ids=[],
                created_at=datetime(2026, 7, 1, 10, 0, 0),
                updated_at=datetime(2026, 7, 1, 10, 0, 0),
            )
        )
    )

    page = run_maybe_awaitable(repo.list(farm_id=1, severity="all"))

    assert page.total == 2
    assert [row.id for row in page.items] == [second.id, first.id]


def test_guardrails_repository_filters_cleanup_and_mongo_read_fallback(db_session):
    collection = FakeCollection()
    mysql_repo = build_guardrails_log_repository("mysql", db_session)
    old = GuardrailsLog(
        farm_id=1,
        trigger_type="input",
        trigger_detail="old",
        source_text="old text",
        created_at=datetime.now() - timedelta(days=40),
    )
    current = GuardrailsLog(
        farm_id=2,
        trigger_type="output",
        trigger_detail="current",
        source_text="current text",
        created_at=datetime.now(),
    )
    mysql_repo.create(old)
    mysql_repo.create(current)

    page = mysql_repo.list_admin_page(trigger_type="input", farm_id=1, page=1, size=10)
    assert [row.id for row in page.items] == [old.id]

    dual_repo = build_guardrails_log_repository(
        "dual", db_session, collection=collection
    )
    run_maybe_awaitable(
        dual_repo.create(
            GuardrailsLog(
                farm_id=1,
                trigger_type="input",
                trigger_detail="dual",
                source_text="dual text",
            )
        )
    )
    assert collection.docs[-1]["farmId"] == 1
    assert collection.docs[-1]["sourceTextHash"]

    mongo_repo = build_guardrails_log_repository(
        "mongo", db_session, collection=collection
    )
    mongo_only_log = run_maybe_awaitable(
        mongo_repo.create(
            GuardrailsLog(
                farm_id=1,
                trigger_type="input",
                trigger_detail="mongo",
                source_text="mongo text",
            )
        )
    )
    assert mongo_only_log.id is not None
    assert collection.docs[-1]["mysqlId"] == mongo_only_log.id

    mongo_page = run_maybe_awaitable(
        mongo_repo.list_admin_page(trigger_type="input", farm_id=1, page=1, size=10)
    )
    assert mongo_page.total == 2

    mongo_read_repo = build_guardrails_log_repository(
        "mongo-read",
        db_session,
        collection=FakeCollection(fail_find=True),
    )
    fallback_page = run_maybe_awaitable(
        mongo_read_repo.list_admin_page(
            trigger_type="output", farm_id=2, page=1, size=10
        )
    )
    assert [row.id for row in fallback_page.items] == [current.id]

    assert mysql_repo.cleanup_before(cutoff=datetime.now() - timedelta(days=30)) == 1
