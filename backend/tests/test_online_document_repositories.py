"""第 2 期在线文档 Repository 测试。"""

from __future__ import annotations

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
from app.models.guardrails_log import GuardrailsLog
from app.models.user import User


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
    mongo_chat_rows = run_maybe_awaitable(
        mongo_repo.list_advice_history(farm_id=1, limit=5)
    )
    assert [row.id for row in mongo_chat_rows] == [dual_record.id]

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
    mongo_page = run_maybe_awaitable(
        mongo_repo.list_admin_page(trigger_type="input", farm_id=1, page=1, size=10)
    )
    assert mongo_page.total == 1

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
