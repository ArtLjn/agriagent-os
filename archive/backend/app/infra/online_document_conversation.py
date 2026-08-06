"""`conversation_messages` 在线文档 Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.infra.mongo_mappers import (
    conversation_message_from_mongo_doc,
    conversation_message_to_mongo_doc,
)
from app.infra.mongo_identity import ensure_row_mysql_id
from app.infra.online_document_common import DualWriteBase, mongo_read_many, replace_doc
from app.domains.conversation.models import Conversation, ConversationMessage


class MySQLConversationMessageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def save_one(self, row: ConversationMessage) -> ConversationMessage:
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save_batch(self, rows: list[ConversationMessage]) -> list[ConversationMessage]:
        for row in rows:
            self._db.add(row)
        self._db.flush()
        self._db.commit()
        for row in rows:
            self._db.refresh(row)
        return rows

    def get_recent(
        self, *, farm_id: int, conversation_id: int, limit: int
    ) -> list[ConversationMessage]:
        return (
            self._db.query(ConversationMessage)
            .join(Conversation)
            .filter(
                Conversation.farm_id == farm_id,
                ConversationMessage.conversation_id == conversation_id,
            )
            .order_by(
                ConversationMessage.created_at.desc(), ConversationMessage.id.desc()
            )
            .limit(limit)
            .all()
        )[::-1]

    def list_by_session(
        self, *, farm_id: int, session_id: str
    ) -> list[ConversationMessage]:
        return (
            self._db.query(ConversationMessage)
            .join(Conversation)
            .filter(
                Conversation.farm_id == farm_id, Conversation.session_id == session_id
            )
            .order_by(
                ConversationMessage.created_at.asc(), ConversationMessage.id.asc()
            )
            .all()
        )

    def list_by_turn_ids(
        self, *, farm_id: int, turn_ids: list[int]
    ) -> list[ConversationMessage]:
        if not turn_ids:
            return []
        return (
            self._db.query(ConversationMessage)
            .join(Conversation)
            .filter(
                Conversation.farm_id == farm_id,
                ConversationMessage.turn_id.in_(turn_ids),
            )
            .order_by(
                ConversationMessage.created_at.asc(), ConversationMessage.id.asc()
            )
            .all()
        )

    def get_by_mysql_id(
        self, *, farm_id: int, mysql_id: int
    ) -> ConversationMessage | None:
        return (
            self._db.query(ConversationMessage)
            .options(joinedload(ConversationMessage.conversation))
            .join(Conversation)
            .filter(Conversation.farm_id == farm_id, ConversationMessage.id == mysql_id)
            .first()
        )


class MongoConversationMessageRepository:
    def __init__(self, db: Session, collection: Any) -> None:
        self._db = db
        self._collection = collection

    async def save_one(self, row: ConversationMessage) -> ConversationMessage:
        ensure_row_mysql_id(row)
        if row.created_at is None:
            row.created_at = datetime.now()
        farm_id, session_id = self._resolve_conversation_context(row)
        await replace_doc(
            self._collection,
            conversation_message_to_mongo_doc(
                row,
                farm_id=farm_id,
                session_id=session_id,
            ),
        )
        return row

    async def save_batch(
        self, rows: list[ConversationMessage]
    ) -> list[ConversationMessage]:
        for row in rows:
            await self.save_one(row)
        return rows

    async def get_recent(
        self, *, farm_id: int, conversation_id: int, limit: int
    ) -> list[ConversationMessage]:
        cursor = (
            self._collection.find(
                {"farmId": farm_id, "conversationId": conversation_id}
            )
            .sort([("createdAt", -1), ("mysqlId", -1)])
            .limit(max(limit, 0))
        )
        docs = await cursor.to_list(None)
        return [conversation_message_from_mongo_doc(doc) for doc in reversed(docs)]

    async def list_by_session(
        self, *, farm_id: int, session_id: str
    ) -> list[ConversationMessage]:
        cursor = self._collection.find(
            {"farmId": farm_id, "sessionId": session_id}
        ).sort([("createdAt", 1), ("mysqlId", 1)])
        docs = await cursor.to_list(None)
        return [conversation_message_from_mongo_doc(doc) for doc in docs]

    async def list_by_turn_ids(
        self, *, farm_id: int, turn_ids: list[int]
    ) -> list[ConversationMessage]:
        if not turn_ids:
            return []
        cursor = self._collection.find(
            {"farmId": farm_id, "turnId": {"$in": turn_ids}}
        ).sort([("createdAt", 1), ("mysqlId", 1)])
        docs = await cursor.to_list(None)
        return [conversation_message_from_mongo_doc(doc) for doc in docs]

    async def get_by_mysql_id(
        self, *, farm_id: int, mysql_id: int
    ) -> ConversationMessage | None:
        doc = await self._collection.find_one({"farmId": farm_id, "mysqlId": mysql_id})
        return conversation_message_from_mongo_doc(doc) if doc is not None else None

    def _resolve_conversation_context(
        self, row: ConversationMessage
    ) -> tuple[int | None, str | None]:
        conversation = getattr(row, "conversation", None)
        if conversation is None and row.conversation_id is not None:
            conversation = self._db.get(Conversation, row.conversation_id)
        if conversation is None:
            return None, None
        return conversation.farm_id, conversation.session_id


class DualWriteConversationMessageRepository(DualWriteBase):
    object_type = "conversation_message"

    async def save_one(self, row: ConversationMessage) -> ConversationMessage:
        saved = self._mysql.save_one(row)
        await self._write_secondary("save_one", saved)
        return saved

    async def save_batch(
        self, rows: list[ConversationMessage]
    ) -> list[ConversationMessage]:
        saved = self._mysql.save_batch(rows)
        for row in saved:
            await self._write_secondary("save_one", row)
        return saved

    def get_recent(self, **kwargs):
        return self._mysql.get_recent(**kwargs)

    def list_by_session(self, **kwargs):
        return self._mysql.list_by_session(**kwargs)

    def list_by_turn_ids(self, **kwargs):
        return self._mysql.list_by_turn_ids(**kwargs)

    def get_by_mysql_id(self, **kwargs):
        return self._mysql.get_by_mysql_id(**kwargs)


class MongoReadConversationMessageRepository(DualWriteConversationMessageRepository):
    async def get_recent(self, **kwargs):
        return await mongo_read_many(
            self._mongo.get_recent, self._mysql.get_recent, self.object_type, kwargs
        )

    async def list_by_session(self, **kwargs):
        return await mongo_read_many(
            self._mongo.list_by_session,
            self._mysql.list_by_session,
            self.object_type,
            kwargs,
        )

    async def list_by_turn_ids(self, **kwargs):
        return await mongo_read_many(
            self._mongo.list_by_turn_ids,
            self._mysql.list_by_turn_ids,
            self.object_type,
            kwargs,
        )


def build_conversation_message_repository(
    backend: str, db: Session, collection: Any | None = None, hook: Any = None
) -> Any:
    mysql = MySQLConversationMessageRepository(db)
    if backend == "mysql":
        return mysql
    if collection is None:
        raise ValueError("MONGO_COLLECTION_REQUIRED")
    mongo = MongoConversationMessageRepository(db, collection)
    if backend == "dual":
        return DualWriteConversationMessageRepository(mysql, mongo, hook)
    if backend == "mongo-read":
        return MongoReadConversationMessageRepository(mysql, mongo, hook)
    if backend == "mongo":
        return mongo
    raise ValueError({"code": "INVALID_STORAGE_BACKEND", "backend": backend})
