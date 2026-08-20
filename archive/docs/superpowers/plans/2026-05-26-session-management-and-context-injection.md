# Session Management and Context Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现单会话模式的多轮对话历史持久化，并将用户上下文（城市/季节/称呼）注入 system prompt。

**Architecture:** 新增 `Conversation` + `ConversationMessage` 两表持久化对话历史，前端生成 UUID session_id，后端 lazy creation 会话。`advisor.py` 注入最近 10 轮历史到 LangGraph。`base.j2` 新增 `<user_context>` XML 段注入 Farm.location 等信息。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, LangGraph, Jinja2

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/models/conversation.py` | Create | Conversation + ConversationMessage 模型 |
| `app/models/__init__.py` | Modify | 导入新模型 |
| `app/services/conversation_service.py` | Create | 会话 CRUD + 过期清理 |
| `app/schemas/agent.py` | Modify | ChatRequest 新增 session_id；新增 response schemas |
| `app/api/agent.py` | Modify | 聊天接口传入 session_id；新增会话查询接口 |
| `app/agents/advisor.py` | Modify | invoke_advisor / stream_advisor 接受 conversation_id，注入历史 |
| `app/agents/graph.py` | Modify | _llm_node 注入 farm_location / current_season |
| `app/services/agent_service.py` | Modify | chat_with_agent / stream_chat_with_agent 传递 session_id |
| `backend/prompts/base.j2` | Modify | 新增 `<user_context>` XML 段 |
| `app/core/prompt_registry.py` | Modify | _DEFAULT_PROMPTS 同步更新 |
| `tests/services/test_conversation_service.py` | Create | 会话服务测试 |
| `tests/test_agent_api.py` | Modify | 新增会话 API 测试 |
| `tests/test_advisor_agent.py` | Modify | 新增历史注入测试 |

---

## Task 1: Conversation + ConversationMessage 数据模型

**Files:**
- Create: `app/models/conversation.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_conversation_models.py`

---

### Task 1.1: Write the failing test

```python
# tests/test_conversation_models.py
"""Conversation 模型测试。"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationMessage, ConversationStatus
from app.core.database import SessionLocal


class TestConversationModel:
    def test_create_conversation(self, clean_db):
        db = SessionLocal()
        conv = Conversation(
            farm_id=1,
            session_id="test-session-001",
            status=ConversationStatus.ACTIVE,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        assert conv.id is not None
        assert conv.farm_id == 1
        assert conv.session_id == "test-session-001"
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.created_at is not None
        assert conv.last_active_at is not None
        db.close()

    def test_create_conversation_message(self, clean_db):
        db = SessionLocal()
        conv = Conversation(farm_id=1, session_id="test-session-002")
        db.add(conv)
        db.commit()

        msg = ConversationMessage(
            conversation_id=conv.id,
            role="user",
            content="明天天气怎么样",
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        assert msg.id is not None
        assert msg.conversation_id == conv.id
        assert msg.role == "user"
        assert msg.content == "明天天气怎么样"
        assert msg.created_at is not None
        db.close()

    def test_conversation_cascade_delete_messages(self, clean_db):
        db = SessionLocal()
        conv = Conversation(farm_id=1, session_id="test-session-003")
        db.add(conv)
        db.commit()

        msg = ConversationMessage(
            conversation_id=conv.id, role="user", content="test"
        )
        db.add(msg)
        db.commit()

        db.delete(conv)
        db.commit()

        remaining = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conv.id
        ).all()
        assert len(remaining) == 0
        db.close()

    def test_conversation_status_enum(self, clean_db):
        db = SessionLocal()
        conv = Conversation(
            farm_id=1, session_id="test-session-004", status=ConversationStatus.CLOSED
        )
        db.add(conv)
        db.commit()

        fetched = db.query(Conversation).filter(
            Conversation.session_id == "test-session-004"
        ).first()
        assert fetched.status == "closed"
        db.close()
```

---

### Task 1.2: Run test to verify it fails

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_conversation_models.py -v
```

**Expected:** FAIL with `ModuleNotFoundError: No module named 'app.models.conversation'`

---

### Task 1.3: Write minimal implementation

```python
# app/models/conversation.py
"""会话模型 — 持久化用户与 Agent 的多轮对话历史。"""

import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class ConversationStatus(str, enum.Enum):
    """会话状态枚举。"""

    ACTIVE = "active"
    CLOSED = "closed"


class Conversation(Base):
    """会话模型 — 每个 farm 同时只有一个活跃会话。"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True, unique=True)
    status = Column(
        String, nullable=False, default=ConversationStatus.ACTIVE.value
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationMessage(Base):
    """会话消息模型 — 存储单条对话记录。"""

    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

```python
# app/models/__init__.py — 追加导入
from app.models.conversation import Conversation, ConversationMessage, ConversationStatus

__all__ = [
    # ... existing exports ...
    "Conversation",
    "ConversationMessage",
    "ConversationStatus",
]
```

---

### Task 1.4: Run test to verify it passes

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_conversation_models.py -v
```

**Expected:** 4 tests PASS

---

### Task 1.5: Commit

```bash
git add backend/app/models/conversation.py backend/app/models/__init__.py backend/tests/test_conversation_models.py
git commit -m "feat: add Conversation and ConversationMessage models"
```

---

## Task 2: 会话服务层 conversation_service.py

**Files:**
- Create: `app/services/conversation_service.py`
- Test: `tests/services/test_conversation_service.py`

---

### Task 2.1: Write the failing test

```python
# tests/services/test_conversation_service.py
"""ConversationService 测试。"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.conversation import Conversation, ConversationMessage, ConversationStatus
from app.services.conversation_service import (
    get_or_create_conversation,
    save_message,
    get_recent_messages,
    close_expired_conversations,
    list_conversations,
    get_conversation_messages,
)


class TestGetOrCreateConversation:
    def test_create_new_conversation(self, clean_db):
        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-new")

        assert conv.farm_id == 1
        assert conv.session_id == "sess-new"
        assert conv.status == ConversationStatus.ACTIVE
        db.close()

    def test_reuse_active_conversation(self, clean_db):
        db = SessionLocal()
        conv1 = get_or_create_conversation(db, farm_id=1, session_id="sess-reuse")
        conv2 = get_or_create_conversation(db, farm_id=1, session_id="sess-reuse")

        assert conv1.id == conv2.id
        db.close()

    def test_close_old_active_when_new_session(self, clean_db):
        db = SessionLocal()
        old = get_or_create_conversation(db, farm_id=1, session_id="sess-old")
        assert old.status == ConversationStatus.ACTIVE

        new = get_or_create_conversation(db, farm_id=1, session_id="sess-new2")
        db.refresh(old)

        assert old.status == ConversationStatus.CLOSED
        assert new.status == ConversationStatus.ACTIVE
        assert new.session_id == "sess-new2"
        db.close()


class TestSaveAndGetMessages:
    def test_save_user_message(self, clean_db):
        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-msg")
        msg = save_message(db, conv.id, "user", "明天天气如何")

        assert msg.role == "user"
        assert msg.content == "明天天气如何"
        db.close()

    def test_save_assistant_message(self, clean_db):
        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-msg2")
        msg = save_message(db, conv.id, "assistant", "明天晴，适合浇水")

        assert msg.role == "assistant"
        assert msg.content == "明天晴，适合浇水"
        db.close()

    def test_get_recent_messages_limit(self, clean_db):
        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-recent")
        for i in range(5):
            save_message(db, conv.id, "user", f"msg-{i}")
            save_message(db, conv.id, "assistant", f"reply-{i}")

        recent = get_recent_messages(db, conv.id, limit=6)
        assert len(recent) == 6
        assert recent[0].content == "msg-2"  # 从第3轮开始
        db.close()


class TestCloseExpiredConversations:
    def test_close_conversations_older_than_24h(self, clean_db):
        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-expired")
        # 手动设置 last_active_at 为 25 小时前
        conv.last_active_at = datetime.now() - timedelta(hours=25)
        db.commit()

        closed_count = close_expired_conversations(db, farm_id=1)
        assert closed_count == 1

        db.refresh(conv)
        assert conv.status == ConversationStatus.CLOSED
        db.close()

    def test_keep_recent_conversations(self, clean_db):
        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-recent2")

        closed_count = close_expired_conversations(db, farm_id=1)
        assert closed_count == 0

        db.refresh(conv)
        assert conv.status == ConversationStatus.ACTIVE
        db.close()


class TestListConversations:
    def test_list_ordered_by_last_active(self, clean_db):
        db = SessionLocal()
        conv1 = get_or_create_conversation(db, farm_id=1, session_id="sess-list1")
        conv2 = get_or_create_conversation(db, farm_id=1, session_id="sess-list2")
        # 更新 conv1 的 last_active_at 使其排在前面
        save_message(db, conv1.id, "user", "hi")
        db.commit()

        result = list_conversations(db, farm_id=1, limit=10)
        assert len(result) == 2
        assert result[0].session_id == "sess-list1"  # 最新活跃
        db.close()


class TestGetConversationMessages:
    def test_get_full_message_list(self, clean_db):
        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-full")
        save_message(db, conv.id, "user", "Q1")
        save_message(db, conv.id, "assistant", "A1")

        msgs = get_conversation_messages(db, conv.session_id)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        db.close()
```

---

### Task 2.2: Run test to verify it fails

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/services/test_conversation_service.py -v
```

**Expected:** FAIL with `ModuleNotFoundError: No module named 'app.services.conversation_service'`

---

### Task 2.3: Write minimal implementation

```python
# app/services/conversation_service.py
"""会话服务 — 管理 Conversation 生命周期和历史消息。"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationMessage, ConversationStatus

logger = logging.getLogger(__name__)

_EXPIRE_HOURS = 24
_MAX_INJECT_MESSAGES = 20  # 10 轮 = 20 条消息


def get_or_create_conversation(
    db: Session, farm_id: int, session_id: str
) -> Conversation:
    """获取或创建会话。每个 farm 同时只有一个活跃会话。

    如果传入新的 session_id 且存在其他活跃会话，关闭旧会话。
    """
    existing = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .first()
    )
    if existing:
        return existing

    # 关闭同一 farm 的其他活跃会话
    _close_other_active(db, farm_id)

    conv = Conversation(
        farm_id=farm_id,
        session_id=session_id,
        status=ConversationStatus.ACTIVE,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    logger.info("创建新会话 | farm=%s session=%s", farm_id, session_id)
    return conv


def _close_other_active(db: Session, farm_id: int) -> int:
    """关闭指定 farm 的所有活跃会话。"""
    count = (
        db.query(Conversation)
        .filter(
            Conversation.farm_id == farm_id,
            Conversation.status == ConversationStatus.ACTIVE.value,
        )
        .update({"status": ConversationStatus.CLOSED.value})
    )
    db.commit()
    if count > 0:
        logger.info("关闭旧会话 | farm=%s count=%d", farm_id, count)
    return count


def close_expired_conversations(db: Session, farm_id: int) -> int:
    """关闭 24h 无活动的活跃会话。返回关闭数量。"""
    cutoff = datetime.now() - timedelta(hours=_EXPIRE_HOURS)
    count = (
        db.query(Conversation)
        .filter(
            Conversation.farm_id == farm_id,
            Conversation.status == ConversationStatus.ACTIVE.value,
            Conversation.last_active_at < cutoff,
        )
        .update({"status": ConversationStatus.CLOSED.value})
    )
    db.commit()
    if count > 0:
        logger.info("过期会话清理 | farm=%s count=%d", farm_id, count)
    return count


def save_message(
    db: Session, conversation_id: int, role: str, content: str
) -> ConversationMessage:
    """持久化单条消息。"""
    msg = ConversationMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # 更新会话最后活跃时间
    db.query(Conversation).filter(Conversation.id == conversation_id).update(
        {"last_active_at": datetime.now()}
    )
    db.commit()
    return msg


def get_recent_messages(
    db: Session, conversation_id: int, limit: int = _MAX_INJECT_MESSAGES
) -> list[ConversationMessage]:
    """获取最近 N 条消息，按创建时间正序排列（适合注入 LangGraph）。"""
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
        .all()
    )[::-1]  # 反转回正序


def list_conversations(
    db: Session, farm_id: int, limit: int = 20
) -> list[Conversation]:
    """返回 farm 的会话列表，按最后活跃时间倒序。"""
    return (
        db.query(Conversation)
        .filter(Conversation.farm_id == farm_id)
        .order_by(Conversation.last_active_at.desc())
        .limit(limit)
        .all()
    )


def get_conversation_messages(
    db: Session, session_id: str
) -> list[ConversationMessage]:
    """返回指定会话的完整消息列表，按创建时间正序。"""
    conv = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .first()
    )
    if not conv:
        return []
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )


__all__ = [
    "get_or_create_conversation",
    "close_expired_conversations",
    "save_message",
    "get_recent_messages",
    "list_conversations",
    "get_conversation_messages",
]
```

---

### Task 2.4: Run test to verify it passes

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/services/test_conversation_service.py -v
```

**Expected:** 10 tests PASS

---

### Task 2.5: Commit

```bash
git add backend/app/services/conversation_service.py backend/tests/services/test_conversation_service.py
git commit -m "feat: add conversation service with lifecycle and history management"
```

---

## Task 3: ChatRequest 扩展与 Response Schemas

**Files:**
- Modify: `app/schemas/agent.py`
- Test: `tests/test_agent_api.py` (追加测试)

---

### Task 3.1: Write the failing test

在 `tests/test_agent_api.py` 中追加：

```python
class TestChatRequestSessionId:
    def test_chat_request_accepts_session_id(self):
        from app.schemas.agent import ChatRequest

        req = ChatRequest(message="test", session_id="test-sess-123")
        assert req.session_id == "test-sess-123"

    def test_chat_request_session_id_optional(self):
        from app.schemas.agent import ChatRequest

        req = ChatRequest(message="test")
        assert req.session_id is None
```

---

### Task 3.2: Run test to verify it fails

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_api.py::TestChatRequestSessionId -v
```

**Expected:** FAIL with `TypeError: ChatRequest.__init__() got an unexpected keyword argument 'session_id'`

---

### Task 3.3: Write minimal implementation

```python
# app/schemas/agent.py — 修改 ChatRequest 并追加 response schemas

class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    cycle_id: int | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(None, max_length=64)


class ConversationListItem(BaseModel):
    """会话列表项。"""

    id: int
    session_id: str
    status: str
    created_at: datetime
    last_active_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ConversationMessageItem(BaseModel):
    """会话消息项。"""

    id: int
    role: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

---

### Task 3.4: Run test to verify it passes

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_api.py::TestChatRequestSessionId -v
```

**Expected:** PASS

---

### Task 3.5: Commit

```bash
git add backend/app/schemas/agent.py backend/tests/test_agent_api.py
git commit -m "feat: add session_id to ChatRequest and conversation response schemas"
```

---

## Task 4: 会话管理 API 端点

**Files:**
- Modify: `app/api/agent.py`
- Test: `tests/test_agent_api.py` (追加测试)

---

### Task 4.1: Write the failing test

在 `tests/test_agent_api.py` 中追加：

```python
class TestConversationApi:
    def test_list_conversations(self, client, clean_db):
        from app.services.conversation_service import get_or_create_conversation
        from app.core.database import SessionLocal

        db = SessionLocal()
        get_or_create_conversation(db, farm_id=1, session_id="sess-api-1")
        db.close()

        response = client.get("/agent/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["session_id"] == "sess-api-1"

    def test_get_conversation_messages(self, client, clean_db):
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )
        from app.core.database import SessionLocal

        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-api-2")
        save_message(db, conv.id, "user", "hello")
        save_message(db, conv.id, "assistant", "hi")
        db.close()

        response = client.get("/agent/conversations/sess-api-2/messages")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"

    def test_get_messages_not_found(self, client):
        response = client.get("/agent/conversations/nonexistent/messages")
        assert response.status_code == 200
        assert response.json() == []
```

---

### Task 4.2: Run test to verify it fails

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_api.py::TestConversationApi -v
```

**Expected:** FAIL with `404 Not Found`（路由不存在）

---

### Task 4.3: Write minimal implementation

```python
# app/api/agent.py — 追加导入
from app.schemas.agent import (
    # ... existing imports ...
    ConversationListItem,
    ConversationMessageItem,
)
from app.services.conversation_service import (
    get_or_create_conversation,
    save_message,
    list_conversations,
    get_conversation_messages,
)


# 在 agent_chat 中修改调用（注意：此处只展示 diff，完整代码见 Task 5）
# 同时追加 API 端点：

@router.get("/conversations", response_model=list[ConversationListItem])
@limiter.limit("30/minute")
def get_conversations(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[ConversationListItem]:
    """获取当前 farm 的会话列表。"""
    conversations = list_conversations(db, farm_id=farm.id, limit=limit)
    return [
        ConversationListItem(
            id=c.id,
            session_id=c.session_id,
            status=c.status,
            created_at=c.created_at,
            last_active_at=c.last_active_at,
        )
        for c in conversations
    ]


@router.get(
    "/conversations/{session_id}/messages",
    response_model=list[ConversationMessageItem],
)
@limiter.limit("30/minute")
def get_messages_by_session(
    request: Request,
    response: Response,
    session_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[ConversationMessageItem]:
    """获取指定会话的消息列表。"""
    messages = get_conversation_messages(db, session_id)
    return [
        ConversationMessageItem(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]
```

**注意：** `agent_chat` 和 `agent_chat_stream` 的修改（传入 session_id、保存消息）在 Task 5 中完成，因为需要 advisor.py 和 agent_service.py 先支持 conversation_id。

---

### Task 4.4: Run test to verify it passes

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_api.py::TestConversationApi -v
```

**Expected:** 3 tests PASS

---

### Task 4.5: Commit

```bash
git add backend/app/api/agent.py backend/tests/test_agent_api.py
git commit -m "feat: add conversation list and message query APIs"
```

---

## Task 5: 多轮对话注入 Agent 层

**Files:**
- Modify: `app/agents/advisor.py`
- Modify: `app/services/agent_service.py`
- Modify: `app/api/agent.py`
- Test: `tests/test_advisor_agent.py` (追加测试)

---

### Task 5.1: Write the failing test

在 `tests/test_advisor_agent.py` 中追加：

```python
class TestHistoryInjection:
    def test_invoke_advisor_with_conversation_id(self, clean_db):
        """验证 advisor 能接受 conversation_id 参数。"""
        from app.agents.advisor import invoke_advisor

        # 即使不传 conversation_id 也应正常工作（向后兼容）
        result = invoke_advisor("你好", farm_id=1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_history_messages(self, clean_db):
        """验证历史消息正确转为 LangChain message 列表。"""
        from app.agents.advisor import _build_history_messages
        from app.core.database import SessionLocal
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )

        db = SessionLocal()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-history")
        save_message(db, conv.id, "user", "明天天气如何")
        save_message(db, conv.id, "assistant", "明天晴天")
        db.close()

        msgs = _build_history_messages(db, conv.id, limit=20)
        assert len(msgs) == 2
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "明天天气如何"
        assert isinstance(msgs[1], AIMessage)
        assert msgs[1].content == "明天晴天"
        db.close()
```

---

### Task 5.2: Run test to verify it fails

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_advisor_agent.py::TestHistoryInjection -v
```

**Expected:** FAIL with `ImportError: cannot import name '_build_history_messages'`

---

### Task 5.3: Write minimal implementation

**Step 5.3a: 修改 advisor.py**

```python
# app/agents/advisor.py — 完整替换
"""建议 Agent 封装，提供每日建议和用户问答接口。"""

import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from sqlalchemy.orm import Session

from app.agents.graph import compile_advisor_graph
from app.core.guardrails import check_input, filter_output
from app.services.conversation_service import get_recent_messages

logger = logging.getLogger(__name__)

_ADVISOR_GRAPH = None


def _get_advisor_graph():
    """获取全局 Advisor 图实例（单例）。"""
    global _ADVISOR_GRAPH
    if _ADVISOR_GRAPH is None:
        _ADVISOR_GRAPH = compile_advisor_graph()
    return _ADVISOR_GRAPH


def build_advisor_agent():
    """构建并返回建议 Agent 图（主要用于测试）。"""
    return compile_advisor_graph()


def _build_history_messages(
    db: Session, conversation_id: int | None, limit: int = 20
) -> list[HumanMessage | AIMessage]:
    """从数据库加载最近 N 条消息，转为 LangChain message 列表。"""
    if conversation_id is None:
        return []

    records = get_recent_messages(db, conversation_id, limit=limit)
    messages: list[HumanMessage | AIMessage] = []
    for rec in records:
        if rec.role == "user":
            messages.append(HumanMessage(content=rec.content))
        elif rec.role == "assistant":
            messages.append(AIMessage(content=rec.content))
    return messages


async def invoke_advisor(
    user_input: str,
    farm_id: int = 1,
    db: Session | None = None,
    conversation_id: int | None = None,
) -> str:
    """调用建议 Agent 回答用户问题。

    Args:
        user_input: 用户输入文本。
        farm_id: 农场 ID。
        db: 数据库会话（用于加载历史消息）。
        conversation_id: 会话 ID（用于加载历史上下文）。
    """
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        return f"输入内容包含不安全信息，已被拦截。原因：{reason}"

    logger.info("Agent 收到请求 | farm_id=%s: %s", farm_id, user_input[:200])

    # 构建消息列表：历史 + 当前输入
    history = _build_history_messages(db, conversation_id) if db else []
    messages = history + [HumanMessage(content=user_input)]

    graph = _get_advisor_graph()
    try:
        result = await graph.ainvoke(
            {"messages": messages, "farm_id": farm_id},
            config={
                "recursion_limit": 15,
                "run_name": "advisor_invoke",
                "metadata": {"farm_id": farm_id, "request_type": "chat"},
            },
        )
    except GraphRecursionError:
        logger.error("Agent 步数超限 | farm_id=%s", farm_id)
        return "Agent 处理步数超出限制，请简化您的问题后重试。"

    reply = result["messages"][-1].content
    filtered = filter_output(reply)
    logger.info("Agent 回复完成 | farm_id=%s, 长度 %d 字符", farm_id, len(filtered))
    return filtered


async def stream_advisor(
    user_input: str,
    farm_id: int = 1,
    db: Session | None = None,
    conversation_id: int | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用建议 Agent，逐 token 返回最终 AI 回复。

    Args:
        user_input: 用户输入文本。
        farm_id: 农场 ID。
        db: 数据库会话（用于加载历史消息）。
        conversation_id: 会话 ID（用于加载历史上下文）。
    """
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        yield f"输入内容包含不安全信息，已被拦截。原因：{reason}"
        return

    logger.info("Agent 流式请求 | farm_id=%s: %s", farm_id, user_input[:200])

    # 构建消息列表：历史 + 当前输入
    history = _build_history_messages(db, conversation_id) if db else []
    messages = history + [HumanMessage(content=user_input)]

    graph = _get_advisor_graph()
    step = 0
    try:
        async for event in graph.astream(
            {"messages": messages, "farm_id": farm_id},
            config={
                "recursion_limit": 15,
                "run_name": "advisor_stream",
                "metadata": {"farm_id": farm_id, "request_type": "stream_chat"},
            },
        ):
            for node, state in event.items():
                step += 1
                for msg in state.get("messages", []):
                    if isinstance(msg, ToolMessage):
                        logger.info(
                            "[step %d] 工具 %s 返回: %s",
                            step,
                            node,
                            str(msg.content)[:150],
                        )
                    elif isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                logger.info(
                                    "[step %d] LLM 决定调用工具: %s(%s)",
                                    step,
                                    tc["name"],
                                    tc["args"],
                                )
                        elif msg.content:
                            logger.info(
                                "[step %d] LLM 最终回复，长度 %d",
                                step,
                                len(msg.content),
                            )
                            yield filter_output(msg.content)
    except GraphRecursionError:
        logger.error("Agent 流式步数超限 | farm_id=%s", farm_id)
        yield "Agent 处理步数超出限制，请简化您的问题后重试。"
        return

    logger.info("Agent 流式完成，共 %d 步", step)


__all__ = [
    "build_advisor_agent",
    "invoke_advisor",
    "stream_advisor",
    "_build_history_messages",
]
```

**Step 5.3b: 修改 agent_service.py**

```python
# app/services/agent_service.py — chat_with_agent 和 stream_chat_with_agent 修改

# 追加导入
from app.services.conversation_service import (
    get_or_create_conversation,
    save_message,
)


# 替换 chat_with_agent 函数签名和主体
async def chat_with_agent(
    db: Session,
    message: str,
    cycle_id: int | None = None,
    farm_id: int = 1,
    session_id: str | None = None,
) -> ChatResponse:
    """与用户进行 Agent 对话，支持写操作确认流程。"""
    logger.info(
        "开始对话 | farm=%s cycle=%s session=%s | input: %s",
        farm_id, cycle_id, session_id, message[:100]
    )

    # 获取/创建会话
    conversation = None
    if session_id:
        conversation = get_or_create_conversation(db, farm_id, session_id)
        # 先保存用户消息
        save_message(db, conversation.id, "user", message)

    # 检查是否有 pending action
    pending = get_pending(farm_id)
    if pending is not None:
        intent = detect_user_intent(message)

        if intent == "confirm":
            logger.info(
                "用户确认执行 | farm=%s skill=%s params=%s",
                farm_id, pending.skill_name, pending.params,
            )
            try:
                result = await _execute_pending_action(
                    farm_id, pending.skill_name, pending.params
                )
                reply = f"已执行：{result}"
            except Exception as exc:
                logger.error("执行 pending action 失败: %s", exc)
                reply = f"执行失败：{exc}"
            finally:
                remove_pending(farm_id)

            if conversation:
                save_message(db, conversation.id, "assistant", reply)
            _save_advice_record(db, cycle_id, reply, farm_id)
            return ChatResponse(reply=reply)

        if intent == "cancel":
            logger.info("用户取消操作 | farm=%s skill=%s", farm_id, pending.skill_name)
            remove_pending(farm_id)
            reply = "已取消操作。"
            if conversation:
                save_message(db, conversation.id, "assistant", reply)
            _save_advice_record(db, cycle_id, reply, farm_id)
            return ChatResponse(reply=reply)

    # 正常调用 LLM
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    reply = await invoke_advisor(
        full_input,
        farm_id=farm_id,
        db=db,
        conversation_id=conversation.id if conversation else None,
    )

    # 保存 assistant 回复到会话
    if conversation:
        save_message(db, conversation.id, "assistant", reply)

    _save_advice_record(db, cycle_id, reply, farm_id)
    logger.info("对话记录已保存 | farm=%s", farm_id)
    return ChatResponse(reply=reply)


# 新增辅助函数，避免重复代码
async def _save_advice_record(
    db: Session, cycle_id: int | None, content: str, farm_id: int
) -> None:
    """保存 AdviceRecord。"""
    record = AdviceRecord(
        cycle_id=cycle_id, advice_type="chat", content=content, farm_id=farm_id
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


# 替换 stream_chat_with_agent
async def stream_chat_with_agent(
    message: str,
    cycle_id: int | None = None,
    farm_id: int = 1,
    db: Session | None = None,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """流式与 Agent 对话，逐 token 返回。"""
    conversation = None
    if db and session_id:
        conversation = get_or_create_conversation(db, farm_id, session_id)
        save_message(db, conversation.id, "user", message)

    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message

    full_reply = ""
    async for chunk in stream_advisor(
        full_input,
        farm_id=farm_id,
        db=db,
        conversation_id=conversation.id if conversation else None,
    ):
        full_reply += chunk
        yield chunk

    # 流式完成后保存 assistant 回复
    if conversation and db:
        save_message(db, conversation.id, "assistant", full_reply)
```

**Step 5.3c: 修改 api/agent.py**

```python
# app/api/agent.py — agent_chat 和 agent_chat_stream 修改

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def agent_chat(
    request: Request,
    response: Response,
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ChatResponse:
    """与农事顾问 Agent 对话。"""
    rid = _new_request_id()
    logger.info(
        "[%s] POST /agent/chat | message=%s cycle_id=%s session_id=%s",
        rid,
        chat_request.message[:80],
        chat_request.cycle_id,
        chat_request.session_id,
    )
    start = time.perf_counter()
    try:
        result = await chat_with_agent(
            db,
            chat_request.message,
            chat_request.cycle_id,
            farm_id=farm.id,
            session_id=chat_request.session_id,
        )
        logger.info(
            "[%s] /agent/chat 完成 | 耗时 %.2fs | reply %d 字符",
            rid,
            time.perf_counter() - start,
            len(result.reply),
        )
        return result
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat/stream")
@limiter.limit("10/minute")
async def agent_chat_stream(
    request: Request,
    response: Response,
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> StreamingResponse:
    """流式与农事顾问 Agent 对话（SSE）。"""
    rid = _new_request_id()
    logger.info(
        "[%s] POST /agent/chat/stream | message=%s session_id=%s",
        rid,
        chat_request.message[:80],
        chat_request.session_id,
    )

    async def event_generator():
        full_reply = ""
        start = time.perf_counter()
        try:
            async for chunk in stream_chat_with_agent(
                chat_request.message,
                chat_request.cycle_id,
                farm_id=farm.id,
                db=db,
                session_id=chat_request.session_id,
            ):
                full_reply += chunk
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            # 保存 AdviceRecord（兼容旧逻辑）
            record = AdviceRecord(
                cycle_id=chat_request.cycle_id,
                advice_type="chat",
                content=full_reply,
                farm_id=farm.id,
            )
            db.add(record)
            db.commit()
            logger.info(
                "[%s] /chat/stream 完成 | 耗时 %.2fs | reply %d 字符",
                rid,
                time.perf_counter() - start,
                len(full_reply),
            )
        except LlmNotConfiguredError as exc:
            logger.error("[%s] /chat/stream 失败: %s", rid, exc)
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

---

### Task 5.4: Run test to verify it passes

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_advisor_agent.py::TestHistoryInjection -v
```

**Expected:** 2 tests PASS

---

### Task 5.5: Commit

```bash
git add backend/app/agents/advisor.py backend/app/services/agent_service.py backend/app/api/agent.py backend/tests/test_advisor_agent.py
git commit -m "feat: inject conversation history into advisor and save messages to session"
```

---

## Task 6: 用户上下文注入 Prompt

**Files:**
- Modify: `backend/prompts/base.j2`
- Modify: `app/core/prompt_registry.py`
- Modify: `app/agents/graph.py`
- Test: `tests/test_prompt_registry.py` (追加测试)

---

### Task 6.1: Write the failing test

在 `tests/test_prompt_registry.py` 中追加：

```python
class TestUserContextInPrompt:
    def test_prompt_contains_user_context_section(self):
        from app.core.prompt_registry import get_registry

        reg = get_registry()
        fallback = reg.get_fallback("system_base")
        assert "user_context" in fallback

    def test_prompt_renders_with_farm_location(self):
        from app.core.prompt_renderer import render_prompt
        from app.core.prompt_registry import get_registry

        result = render_prompt(
            "system_base",
            variables={
                "farm_context_summary": "",
                "display_name": "张三",
                "farm_location": "云南昆明",
                "current_season": "夏季",
            },
            registry=get_registry(),
        )
        assert "云南昆明" in result
        assert "张三" in result
        assert "夏季" in result

    def test_prompt_skips_location_when_empty(self):
        from app.core.prompt_renderer import render_prompt
        from app.core.prompt_registry import get_registry

        result = render_prompt(
            "system_base",
            variables={
                "farm_context_summary": "",
                "display_name": "张三",
                "farm_location": "",
                "current_season": "夏季",
            },
            registry=get_registry(),
        )
        # location 为空时不应渲染 location 标签
        assert "<location>" not in result
```

---

### Task 6.2: Run test to verify it fails

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_prompt_registry.py::TestUserContextInPrompt -v
```

**Expected:** FAIL with `AssertionError: assert 'user_context' in '【语言规则】...'`

---

### Task 6.3: Write minimal implementation

**Step 6.3a: 修改 base.j2**

```jinja2
【语言规则】（最高优先级）
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 农业专业术语中的英文品种名（如 Watermelon、Tomato）允许保留英文。
- 数字、单位符号（如 ℃、kg、亩）不受此限制。

【角色定义】
你是一位经验丰富的农业技术顾问，擅长西瓜、豆角、番茄等作物的种植管理。你了解农事操作、病虫害防治、施肥浇水、成本收支等农业知识。

【回复格式】（最高优先级，必须遵守）
- 称呼用户为「{{ display_name }}」
- 每条建议/操作不超过2行
- 总共不超过5条
- 先说结论，再说原因（如：明天降温12° → 你那西瓜正伸蔓期怕冻）
- 禁止铺垫、寒暄、总结段
- 用「你」不用「您」，口语化

【能力范围】
你具备以下工具调用能力：
- 查询天气预报和灾害预警
- 查看种植周期和当前阶段
- 了解近期农事记录
- 统计成本收支

【工具调用规则】（最高优先级，违反则回答无效）
- 禁止凭记忆回答天气、成本、农事记录、茬口状态等实时数据。
- 遇到上述信息时，必须先调用对应工具获取真实数据，再回答。
- 如果不确定信息是否最新，一律调用工具确认。
- 回答要简洁明了，适合农民理解。

{% if current_date %}
【时间信息】
今天是 {{ current_date }}，星期{{ current_weekday }}。当前时间 {{ current_time }}。
{% endif %}

{% if farm_location or current_season %}
【用户信息】
<user_context>
  {% if farm_location %}<location>{{ farm_location }}</location>{% endif %}
  {% if display_name %}<name>{{ display_name }}</name>{% endif %}
  {% if current_season %}<season>{{ current_season }}</season>{% endif %}
</user_context>
{% endif %}

{% if farm_context_summary %}
【农场现状】
{{ farm_context_summary }}
{% endif %}
```

**Step 6.3b: 修改 prompt_registry.py**

```python
# app/core/prompt_registry.py — 替换 _DEFAULT_PROMPTS["system_base"]
_DEFAULT_PROMPTS = {
    "system_base": (
        "【语言规则】（最高优先级）\n"
        "- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。\n"
        "- 农业专业术语中的英文品种名允许保留英文。\n\n"
        "【角色定义】\n"
        "你是一位经验丰富的农业技术顾问，擅长西瓜、豆角、番茄等作物的种植管理。"
        "你了解农事操作、病虫害防治、施肥浇水、成本收支等农业知识。\n\n"
        "【回复格式】（最高优先级，必须遵守）\n"
        "- 称呼用户为「{{ display_name }}」\n"
        "- 每条建议/操作不超过2行\n"
        "- 总共不超过5条\n"
        "- 先说结论，再说原因\n"
        "- 禁止铺垫、寒暄、总结段\n"
        "- 用「你」不用「您」，口语化\n\n"
        "【工具调用规则】（最高优先级，违反则回答无效）\n"
        "- 禁止凭记忆回答天气、成本、农事记录、茬口状态等实时数据。\n"
        "- 遇到上述信息时，必须先调用对应工具获取真实数据，再回答。\n"
        "- 如果不确定信息是否最新，一律调用工具确认。\n"
        "- 回答要简洁明了，适合农民理解。\n"
        "{% if current_date %}\n\n"
        "【时间信息】\n"
        "今天是 {{ current_date }}，星期{{ current_weekday }}。当前时间 {{ current_time }}。\n"
        "{% endif %}\n"
        "{% if farm_location or current_season %}\n\n"
        "【用户信息】\n"
        "<user_context>\n"
        "  {% if farm_location %}<location>{{ farm_location }}</location>\n{% endif %}"
        "  {% if display_name %}<name>{{ display_name }}</name>\n{% endif %}"
        "  {% if current_season %}<season>{{ current_season }}</season>\n{% endif %}"
        "</user_context>\n"
        "{% endif %}\n"
        "{% if farm_context_summary %}\n\n"
        "【农场现状】\n"
        "{{ farm_context_summary }}\n"
        "{% endif %}\n"
    ),
    # ... 其他 prompts 保持不变 ...
}
```

**Step 6.3c: 修改 graph.py**

```python
# app/agents/graph.py — _llm_node 中注入 farm_location 和 current_season

from datetime import date


def _get_season(current_date: date | None = None) -> str:
    """根据当前月份返回季节。"""
    if current_date is None:
        current_date = date.today()
    month = current_date.month
    if month in (3, 4, 5):
        return "春季"
    elif month in (6, 7, 8):
        return "夏季"
    elif month in (9, 10, 11):
        return "秋季"
    else:
        return "冬季"


def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    tools = get_langchain_tools()
    llm = get_llm().bind_tools(tools)

    # 获取农场上下文摘要和用户称呼
    db = SessionLocal()
    try:
        farm_context_summary = farm_context_service.build_summary(db, farm_id=1)
        farm = db.query(Farm).filter(Farm.id == 1).first()
        display_name = farm.display_name if farm and farm.display_name else "农友"
        farm_location = farm.location if farm and farm.location else ""
    except Exception:
        logger.warning("获取农场上下文失败，使用默认值", exc_info=True)
        farm_context_summary = ""
        display_name = "农友"
        farm_location = ""
    finally:
        db.close()

    current_date = get_request_date()
    current_season = _get_season(current_date)
    system_text = render_prompt(
        "system_base",
        variables={
            "farm_context_summary": farm_context_summary,
            "display_name": display_name,
            "farm_location": farm_location,
            "current_season": current_season,
        },
        registry=get_registry(),
        current_date=current_date,
    )
    system = HumanMessage(content=system_text)

    messages = micro_compact(state["messages"])
    response = llm.invoke([system] + messages)
    return {"messages": [response]}
```

---

### Task 6.4: Run test to verify it passes

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_prompt_registry.py::TestUserContextInPrompt -v
```

**Expected:** 3 tests PASS

---

### Task 6.5: Commit

```bash
git add backend/prompts/base.j2 backend/app/core/prompt_registry.py backend/app/agents/graph.py backend/tests/test_prompt_registry.py
git commit -m "feat: inject user context (location, season) into system prompt via XML"
```

---

## Task 7: 端到端集成验证

**Files:**
- Test: `tests/test_agent_api.py` (追加集成测试)

---

### Task 7.1: Write the integration tests

在 `tests/test_agent_api.py` 中追加：

```python
class TestChatWithSessionIntegration:
    """端到端集成测试：session_id 全流程。"""

    def test_chat_creates_conversation_and_saves_messages(self, client, clean_db):
        response = client.post(
            "/agent/chat",
            json={"message": "明天天气如何", "session_id": "sess-e2e-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

        # 验证会话已创建
        conv_resp = client.get("/agent/conversations")
        conversations = conv_resp.json()
        assert len(conversations) == 1
        assert conversations[0]["session_id"] == "sess-e2e-1"

        # 验证消息已保存
        msg_resp = client.get("/agent/conversations/sess-e2e-1/messages")
        messages = msg_resp.json()
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "明天天气如何"
        assert messages[1]["role"] == "assistant"

    def test_second_chat_reuses_session(self, client, clean_db):
        # 第一轮
        client.post(
            "/agent/chat",
            json={"message": "第一个问题", "session_id": "sess-e2e-2"},
        )
        # 第二轮
        client.post(
            "/agent/chat",
            json={"message": "第二个问题", "session_id": "sess-e2e-2"},
        )

        msg_resp = client.get("/agent/conversations/sess-e2e-2/messages")
        messages = msg_resp.json()
        assert len(messages) == 4  # 2 user + 2 assistant

    def test_new_session_closes_old_one(self, client, clean_db):
        # 创建旧会话
        client.post(
            "/agent/chat",
            json={"message": "旧问题", "session_id": "sess-e2e-old"},
        )
        # 同一 farm 的新会话
        client.post(
            "/agent/chat",
            json={"message": "新问题", "session_id": "sess-e2e-new"},
        )

        conv_resp = client.get("/agent/conversations")
        conversations = conv_resp.json()
        old_conv = next(c for c in conversations if c["session_id"] == "sess-e2e-old")
        assert old_conv["status"] == "closed"

    def test_chat_without_session_id_still_works(self, client, clean_db):
        """向后兼容：不传 session_id 仍能正常工作。"""
        response = client.post(
            "/agent/chat",
            json={"message": "无会话测试"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
```

---

### Task 7.2: Run tests to verify they pass

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_api.py::TestChatWithSessionIntegration -v
```

**Expected:** 4 tests PASS

---

### Task 7.3: Commit

```bash
git add backend/tests/test_agent_api.py
git commit -m "test: add end-to-end integration tests for session management"
```

---

## Task 8: Lint 和全量测试

---

### Task 8.1: Run lint

```bash
cd /Users/ljn/Documents/demo/explore/backend && ruff check . && ruff format .
```

**Expected:** 无错误

---

### Task 8.2: Run full test suite

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest -v
```

**Expected:** 所有测试 PASS（包括新增的会话相关测试）

---

### Task 8.3: Commit

```bash
git add -A
git commit -m "chore: lint and format all changes"
```

---

## Self-Review

### 1. Spec Coverage

| 设计文档需求 | 对应 Task |
|-------------|-----------|
| Conversation + ConversationMessage 模型 | Task 1 |
| 会话服务层（get_or_create, save, get_recent, close_expired, list, get_messages） | Task 2 |
| ChatRequest 新增 session_id | Task 3 |
| 新增 GET /agent/conversations 和 GET /agent/conversations/{id}/messages | Task 4 |
| invoke_advisor / stream_advisor 注入历史 | Task 5 |
| chat_with_agent / stream_chat_with_agent 传递 session_id 并保存消息 | Task 5 |
| base.j2 新增 `<user_context>` XML 段 | Task 6 |
| graph.py 注入 farm_location 和 current_season | Task 6 |
| 单会话模式（自动关闭旧会话） | Task 2 |
| 24h 过期 | Task 2 |
| 前端生成 session_id，后端 lazy creation | Task 5 |
| 最近 10 轮（20 条）注入 | Task 2/5 |
| location 为空条件渲染 | Task 6 |

**Gap: 无。** 所有设计文档需求已覆盖。

### 2. Placeholder Scan

- [x] 无 "TBD" / "TODO" / "implement later"
- [x] 无 "Add appropriate error handling" 等模糊描述
- [x] 所有测试包含完整代码
- [x] 所有修改的文件包含完整 diff（非 "Similar to Task N"）
- [x] 所有类型、方法签名在全文一致

### 3. Type Consistency

| 类型/方法 | 首次定义 | 后续使用 | 状态 |
|----------|---------|---------|------|
| `ChatRequest.session_id` | Task 3 `str \| None` | Task 5 api/agent.py | 一致 |
| `invoke_advisor(db, conversation_id)` | Task 5 advisor.py | Task 5 agent_service.py | 一致 |
| `stream_chat_with_agent(db, session_id)` | Task 5 agent_service.py | Task 5 api/agent.py | 一致 |
| `ConversationStatus` | Task 1 ACTIVE/CLOSED | Task 2/5 全量 | 一致 |
| `_build_history_messages` | Task 5 advisor.py | Task 5 test | 一致 |
| `_get_season` | Task 6 graph.py | Task 6 内部使用 | 一致 |

**Gap: 无。** 类型一致性通过。
