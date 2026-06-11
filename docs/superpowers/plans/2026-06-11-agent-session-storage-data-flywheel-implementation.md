# Agent Session Storage Data Flywheel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight session storage and data flywheel foundation that keeps online chat fast, makes pending confirmations recoverable, and emits structured event data for later Agent reply tuning and evaluation.

**Architecture:** Keep MySQL as the hot path for sessions, messages, turn summaries, and pending plans. Add append-only JSONL event logs for complete replay/debug/training evidence, then add small asynchronous-style builders for session summaries and dataset exports without introducing MongoDB or heavy infrastructure.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, MySQL in production, SQLite-backed tests, pytest, JSONL files, existing admin-web debug export APIs.

---

## Current Context

Read these files before starting implementation:

- `docs/superpowers/specs/2026-06-11-agent-session-storage-data-flywheel-design.md`
- `docs/superpowers/specs/2026-06-10-skill-router-optimization-design.md`
- `backend/app/models/conversation.py`
- `backend/app/services/conversation_service.py`
- `backend/app/agent/application/chat_use_case.py`
- `backend/app/agent/application/stream_chat_use_case.py`
- `backend/app/agent/application/history_use_case.py`
- `backend/app/infra/pending_actions.py`
- `backend/app/agent/executor/pending_actions.py`
- `backend/app/agent/runtime/tool_executor.py`
- `backend/app/api/admin_trace.py`
- `backend/tests/services/test_conversation_service.py`
- `backend/tests/test_agent_api.py`

Important worktree note: the repository may already contain unrelated modified/untracked files. Do not revert them. Stage and commit only the files listed by each task.

## Target File Structure

Create or modify these backend files:

- Modify `backend/app/models/conversation.py`: add hot-path columns to `Conversation` and `ConversationMessage`.
- Create `backend/app/models/agent_turn.py`: ORM model for one user-to-assistant turn summary.
- Create `backend/app/models/pending_plan.py`: ORM models for recoverable pending plans and steps.
- Modify `backend/app/models/__init__.py`: import new models so metadata creation includes them.
- Create `backend/alembic/versions/20260611_agent_session_flywheel.py`: migration for new columns and tables.
- Modify `backend/app/services/conversation_service.py`: batch message save, title summary helper, turn service helpers.
- Create `backend/app/services/agent_turn_service.py`: focused helpers to create/update turn summaries.
- Create `backend/app/services/pending_plan_service.py`: focused helpers to store/read/update pending plans.
- Create `backend/app/infra/agent_events.py`: JSONL event writer and reader.
- Create `backend/app/agent/application/session_flywheel.py`: orchestration helpers for chat use cases.
- Modify `backend/app/agent/application/chat_use_case.py`: write turn summaries and event logs in non-stream chat.
- Keep `backend/app/agent/application/stream_chat_use_case.py` unchanged because it only re-exports `stream_chat_events` from `chat_use_case.py`.
- Modify `backend/app/agent/application/history_use_case.py`: use light metadata and avoid N+1 full-message scans for conversation list.
- Modify `backend/app/api/agent.py`: expose `GET /agent/conversations/{session_id}/debug-export`.
- Create `backend/app/services/session_debug_export_service.py`: assemble messages, turns, pending plans, and event segments.
- Create `backend/app/services/session_dataset_service.py`: generate JSONL-ready training/evaluation samples from event logs.
- Create tests under `backend/tests/services/`, `backend/tests/infra/`, `backend/tests/agent/`, and `backend/tests/api/`.

Do not create a MongoDB integration. Do not add Kafka, Celery, ClickHouse, or vector DB dependencies in this implementation.

---

### Task 1: Add Hot-Path ORM Models and Migration

**Files:**
- Modify: `backend/app/models/conversation.py`
- Create: `backend/app/models/agent_turn.py`
- Create: `backend/app/models/pending_plan.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260611_agent_session_flywheel.py`
- Test: `backend/tests/test_agent_session_flywheel_models.py`

- [ ] **Step 1: Write failing model tests**

Create `backend/tests/test_agent_session_flywheel_models.py` with this content:

```python
"""Agent 会话飞轮模型测试。"""

from datetime import datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.models.farm import Farm
from app.models.pending_plan import AgentPendingPlan, AgentPendingPlanStep


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_session_flywheel_models.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()


def test_conversation_hot_path_columns_round_trip():
    db = Session()
    conv = Conversation(
        farm_id=1,
        user_id="user-1",
        session_id="sess-hot",
        summary="前面聊过水稻收割",
        last_turn_id=7,
        last_event_seq=12,
        meta_json={"source": "playground"},
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    msg = ConversationMessage(
        conversation_id=conv.id,
        turn_id=7,
        role="assistant",
        content="已为您整理",
        content_hash="hash-1",
        meta_json={"skills": ["get_farm_status"]},
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert conv.summary == "前面聊过水稻收割"
    assert conv.meta_json == {"source": "playground"}
    assert msg.turn_id == 7
    assert msg.meta_json == {"skills": ["get_farm_status"]}
    db.close()


def test_agent_turn_links_messages_and_event_range():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-turn")
    db.add(conv)
    db.commit()
    user_msg = ConversationMessage(conversation_id=conv.id, role="user", content="查一下作物")
    assistant_msg = ConversationMessage(conversation_id=conv.id, role="assistant", content="有水稻")
    db.add_all([user_msg, assistant_msg])
    db.commit()

    turn = AgentTurn(
        farm_id=1,
        session_id="sess-turn",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        input_preview="查一下作物",
        reply_preview="有水稻",
        selected_tools_count=1,
        tool_calls_count=1,
        token_total=320,
        latency_ms=1200,
        status="success",
        event_file="data/agent-events/dt=2026-06-11/farm_id=1/session_id=sess-turn/events.jsonl",
        event_seq_start=1,
        event_seq_end=4,
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)

    assert turn.id is not None
    assert turn.selected_tools_count == 1
    assert turn.event_seq_end == 4
    db.close()


def test_pending_plan_and_steps_are_recoverable():
    db = Session()
    expires_at = datetime.now() + timedelta(minutes=5)
    plan = AgentPendingPlan(
        plan_id="plan-1",
        farm_id=1,
        session_id="sess-pending",
        status="pending",
        current_step_index=0,
        raw_user_input="王大妈工资100一天，去5号棚收水稻",
        router_decision_json={"selected_tools": ["manage_workers", "create_operation_work_order"]},
        expires_at=expires_at,
    )
    step1 = AgentPendingPlanStep(
        plan_id="plan-1",
        step_index=0,
        skill_name="manage_workers",
        params_json={"name": "王大妈", "daily_wage": 100},
        status="pending",
        requires_confirmation=True,
        confirmation_text="确认创建工人王大妈吗？",
    )
    step2 = AgentPendingPlanStep(
        plan_id="plan-1",
        step_index=1,
        skill_name="create_operation_work_order",
        params_json={"field_name": "5号棚", "crop_name": "水稻"},
        status="pending",
        requires_confirmation=True,
        confirmation_text="确认安排王大妈去5号棚收水稻吗？",
    )
    db.add_all([plan, step1, step2])
    db.commit()

    loaded = db.query(AgentPendingPlan).filter_by(plan_id="plan-1").one()
    assert loaded.status == "pending"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].params_json["daily_wage"] == 100
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_session_flywheel_models.py -v
```

Expected: FAIL because `app.models.agent_turn`, `app.models.pending_plan`, and new columns do not exist.

- [ ] **Step 3: Add ORM columns to conversation models**

Modify `backend/app/models/conversation.py` so imports and columns include JSON fields:

```python
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func
```

Add these columns to `Conversation` after `last_active_at`:

```python
    summary = Column(Text, nullable=True)
    summary_updated_at = Column(DateTime(timezone=True), nullable=True)
    last_turn_id = Column(Integer, nullable=True)
    last_event_seq = Column(Integer, nullable=True)
    meta_json = Column(JSON, nullable=True)
```

Add these columns to `ConversationMessage` before `created_at`:

```python
    turn_id = Column(Integer, nullable=True, index=True)
    content_hash = Column(String(64), nullable=True)
    meta_json = Column(JSON, nullable=True)
```

- [ ] **Step 4: Add AgentTurn model**

Create `backend/app/models/agent_turn.py`:

```python
"""Agent 单轮对话聚合模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base


class AgentTurn(Base):
    """一轮用户输入到助手回复的轻量聚合记录。"""

    __tablename__ = "agent_turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    request_id = Column(String(16), nullable=False, index=True)
    user_message_id = Column(
        Integer, ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )
    assistant_message_id = Column(
        Integer, ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )
    input_preview = Column(Text, nullable=True)
    reply_preview = Column(Text, nullable=True)
    intent_count = Column(Integer, nullable=True)
    selected_tools_count = Column(Integer, nullable=True)
    tool_calls_count = Column(Integer, nullable=True)
    token_total = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="success")
    pending_plan_id = Column(String(64), nullable=True, index=True)
    event_file = Column(Text, nullable=True)
    event_seq_start = Column(Integer, nullable=True)
    event_seq_end = Column(Integer, nullable=True)
    event_write_status = Column(String(20), nullable=False, default="not_started")
    created_at = Column(DateTime, default=datetime.now, index=True)
```

- [ ] **Step 5: Add pending plan models**

Create `backend/app/models/pending_plan.py`:

```python
"""可恢复 pending plan 模型。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class AgentPendingPlan(Base):
    """一次或多次写操作组成的待确认计划。"""

    __tablename__ = "agent_pending_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), nullable=False, unique=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    current_step_index = Column(Integer, nullable=False, default=0)
    raw_user_input = Column(Text, nullable=True)
    router_decision_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    steps = relationship(
        "AgentPendingPlanStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        primaryjoin="AgentPendingPlan.plan_id == foreign(AgentPendingPlanStep.plan_id)",
        order_by="AgentPendingPlanStep.step_index",
    )


class AgentPendingPlanStep(Base):
    """pending plan 中的单个执行步骤。"""

    __tablename__ = "agent_pending_plan_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), nullable=False, index=True)
    step_index = Column(Integer, nullable=False)
    skill_name = Column(String(100), nullable=False, index=True)
    params_json = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    requires_confirmation = Column(Boolean, nullable=False, default=True)
    confirmation_text = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    plan = relationship(
        "AgentPendingPlan",
        back_populates="steps",
        primaryjoin="foreign(AgentPendingPlanStep.plan_id) == AgentPendingPlan.plan_id",
    )
```

- [ ] **Step 6: Register models**

Modify `backend/app/models/__init__.py` to import the new models:

```python
from app.models.agent_turn import AgentTurn
from app.models.pending_plan import AgentPendingPlan, AgentPendingPlanStep
```

Append these exact names to the existing `__all__` list in `backend/app/models/__init__.py`:

```python
    "AgentTurn",
    "AgentPendingPlan",
    "AgentPendingPlanStep",
```

- [ ] **Step 7: Add Alembic migration**

Create `backend/alembic/versions/20260611_agent_session_flywheel.py`:

```python
"""agent session flywheel storage

Revision ID: 20260611_agent_session_flywheel
Revises: d4a8b9c3e2f1
Create Date: 2026-06-11 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260611_agent_session_flywheel"
down_revision: Union[str, None] = "d4a8b9c3e2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _add_conversation_columns(inspector)
    _add_message_columns(inspector)
    _create_agent_turns(inspector)
    _create_pending_plan_tables(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _drop_pending_plan_tables(inspector)
    _drop_agent_turns(inspector)
    _drop_message_columns(inspector)
    _drop_conversation_columns(inspector)


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _tables(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _add_conversation_columns(inspector) -> None:
    columns = _columns(inspector, "conversations")
    if "summary" not in columns:
        op.add_column("conversations", sa.Column("summary", sa.Text(), nullable=True))
    if "summary_updated_at" not in columns:
        op.add_column("conversations", sa.Column("summary_updated_at", sa.DateTime(), nullable=True))
    if "last_turn_id" not in columns:
        op.add_column("conversations", sa.Column("last_turn_id", sa.Integer(), nullable=True))
    if "last_event_seq" not in columns:
        op.add_column("conversations", sa.Column("last_event_seq", sa.Integer(), nullable=True))
    if "meta_json" not in columns:
        op.add_column("conversations", sa.Column("meta_json", sa.JSON(), nullable=True))


def _drop_conversation_columns(inspector) -> None:
    columns = _columns(inspector, "conversations")
    for column in ["meta_json", "last_event_seq", "last_turn_id", "summary_updated_at", "summary"]:
        if column in columns:
            op.drop_column("conversations", column)


def _add_message_columns(inspector) -> None:
    columns = _columns(inspector, "conversation_messages")
    if "turn_id" not in columns:
        op.add_column("conversation_messages", sa.Column("turn_id", sa.Integer(), nullable=True))
        op.create_index("ix_conversation_messages_turn_id", "conversation_messages", ["turn_id"])
    if "content_hash" not in columns:
        op.add_column("conversation_messages", sa.Column("content_hash", sa.String(length=64), nullable=True))
    if "meta_json" not in columns:
        op.add_column("conversation_messages", sa.Column("meta_json", sa.JSON(), nullable=True))


def _drop_message_columns(inspector) -> None:
    columns = _columns(inspector, "conversation_messages")
    indexes = {index["name"] for index in inspector.get_indexes("conversation_messages")}
    if "ix_conversation_messages_turn_id" in indexes:
        op.drop_index("ix_conversation_messages_turn_id", table_name="conversation_messages")
    for column in ["meta_json", "content_hash", "turn_id"]:
        if column in columns:
            op.drop_column("conversation_messages", column)


def _create_agent_turns(inspector) -> None:
    if "agent_turns" in _tables(inspector):
        return
    op.create_table(
        "agent_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("request_id", sa.String(length=16), nullable=False),
        sa.Column("user_message_id", sa.Integer(), sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("input_preview", sa.Text(), nullable=True),
        sa.Column("reply_preview", sa.Text(), nullable=True),
        sa.Column("intent_count", sa.Integer(), nullable=True),
        sa.Column("selected_tools_count", sa.Integer(), nullable=True),
        sa.Column("tool_calls_count", sa.Integer(), nullable=True),
        sa.Column("token_total", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("pending_plan_id", sa.String(length=64), nullable=True),
        sa.Column("event_file", sa.Text(), nullable=True),
        sa.Column("event_seq_start", sa.Integer(), nullable=True),
        sa.Column("event_seq_end", sa.Integer(), nullable=True),
        sa.Column("event_write_status", sa.String(length=20), nullable=False, server_default="not_started"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_turns_farm_id", "agent_turns", ["farm_id"])
    op.create_index("ix_agent_turns_session_id", "agent_turns", ["session_id"])
    op.create_index("ix_agent_turns_request_id", "agent_turns", ["request_id"])
    op.create_index("ix_agent_turns_conversation_id", "agent_turns", ["conversation_id"])
    op.create_index("ix_agent_turns_created_at", "agent_turns", ["created_at"])
    op.create_index("ix_agent_turns_pending_plan_id", "agent_turns", ["pending_plan_id"])


def _drop_agent_turns(inspector) -> None:
    if "agent_turns" in _tables(inspector):
        op.drop_table("agent_turns")


def _create_pending_plan_tables(inspector) -> None:
    tables = _tables(inspector)
    if "agent_pending_plans" not in tables:
        op.create_table(
            "agent_pending_plans",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("plan_id", sa.String(length=64), nullable=False, unique=True),
            sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("raw_user_input", sa.Text(), nullable=True),
            sa.Column("router_decision_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_agent_pending_plans_plan_id", "agent_pending_plans", ["plan_id"], unique=True)
        op.create_index("ix_agent_pending_plans_farm_id", "agent_pending_plans", ["farm_id"])
        op.create_index("ix_agent_pending_plans_session_id", "agent_pending_plans", ["session_id"])
        op.create_index("ix_agent_pending_plans_status", "agent_pending_plans", ["status"])
        op.create_index("ix_agent_pending_plans_expires_at", "agent_pending_plans", ["expires_at"])
    if "agent_pending_plan_steps" not in tables:
        op.create_table(
            "agent_pending_plan_steps",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("plan_id", sa.String(length=64), nullable=False),
            sa.Column("step_index", sa.Integer(), nullable=False),
            sa.Column("skill_name", sa.String(length=100), nullable=False),
            sa.Column("params_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("confirmation_text", sa.Text(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_agent_pending_plan_steps_plan_id", "agent_pending_plan_steps", ["plan_id"])
        op.create_index("ix_agent_pending_plan_steps_skill_name", "agent_pending_plan_steps", ["skill_name"])
        op.create_index("ix_agent_pending_plan_steps_status", "agent_pending_plan_steps", ["status"])


def _drop_pending_plan_tables(inspector) -> None:
    tables = _tables(inspector)
    if "agent_pending_plan_steps" in tables:
        op.drop_table("agent_pending_plan_steps")
    if "agent_pending_plans" in tables:
        op.drop_table("agent_pending_plans")
```

- [ ] **Step 8: Run model tests**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_session_flywheel_models.py -v
```

Expected: PASS.

- [ ] **Step 9: Run schema audit and targeted model tests**

Run:

```bash
cd backend && poetry run pytest tests/test_schema_hardening_audit.py tests/test_agent_session_flywheel_models.py -v
```

Expected: PASS. If the schema audit expects explicit known table/column lists, update only the expectations related to the new tables/columns.

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/conversation.py backend/app/models/agent_turn.py backend/app/models/pending_plan.py backend/app/models/__init__.py backend/alembic/versions/20260611_agent_session_flywheel.py backend/tests/test_agent_session_flywheel_models.py backend/tests/test_schema_hardening_audit.py
git commit -m "feat: add agent session flywheel models"
```

---

### Task 2: Add Conversation and Turn Services

**Files:**
- Modify: `backend/app/services/conversation_service.py`
- Create: `backend/app/services/agent_turn_service.py`
- Test: `backend/tests/services/test_conversation_service.py`
- Test: `backend/tests/services/test_agent_turn_service.py`

- [ ] **Step 1: Add failing tests for batch message save and metadata parsing**

Append these tests to `backend/tests/services/test_conversation_service.py`:

```python
class TestBatchMessageSave:
    """批量保存消息测试。"""

    def test_save_messages_batch_uses_one_transaction_and_sets_light_metadata(self):
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-batch")

        messages = save_messages_batch(
            db,
            conv.id,
            [
                {
                    "role": "user",
                    "content": "查一下作物",
                    "turn_id": 1,
                    "meta_json": {"trace_request_id": "abcd1234"},
                },
                {
                    "role": "assistant",
                    "content": "当前有水稻",
                    "turn_id": 1,
                    "meta_json": {"skills": ["get_farm_status"]},
                },
            ],
        )

        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[0].turn_id == 1
        assert messages[1].meta_json == {"skills": ["get_farm_status"]}
        db.refresh(conv)
        assert conv.last_active_at is not None
        db.close()
```

Also update the import list at the top of the same file:

```python
    save_messages_batch,
```

- [ ] **Step 2: Add failing tests for turn service**

Create `backend/tests/services/test_agent_turn_service.py`:

```python
"""Agent turn service 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.models.farm import Farm
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_turn_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()


def test_create_finish_and_mark_event_range():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-turn")
    db.add(conv)
    db.commit()
    msg = ConversationMessage(conversation_id=conv.id, role="user", content="查一下作物")
    db.add(msg)
    db.commit()

    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-turn",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=msg.id,
        input_text="查一下作物",
    )
    finish_turn(
        db,
        turn.id,
        reply_text="当前有水稻",
        assistant_message_id=22,
        selected_tools_count=1,
        tool_calls_count=1,
        token_total=500,
        latency_ms=1200,
        status="success",
    )
    mark_event_range(
        db,
        turn.id,
        event_file="data/agent-events/dt=2026-06-11/farm_id=1/session_id=sess-turn/events.jsonl",
        seq_start=1,
        seq_end=5,
        write_status="success",
    )

    loaded = db.query(AgentTurn).filter_by(id=turn.id).one()
    assert loaded.input_preview == "查一下作物"
    assert loaded.reply_preview == "当前有水稻"
    assert loaded.event_seq_start == 1
    assert loaded.event_seq_end == 5
    assert loaded.event_write_status == "success"
    db.refresh(conv)
    assert conv.last_turn_id == turn.id
    db.close()


def test_preview_is_truncated_to_keep_turn_lightweight():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-long")
    db.add(conv)
    db.commit()
    long_text = "水稻" * 200

    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-long",
        conversation_id=conv.id,
        request_id="req12345",
        user_message_id=None,
        input_text=long_text,
    )

    assert len(turn.input_preview) <= 123
    assert turn.input_preview.endswith("...")
    db.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/services/test_conversation_service.py::TestBatchMessageSave tests/services/test_agent_turn_service.py -v
```

Expected: FAIL because `save_messages_batch` and `agent_turn_service` do not exist.

- [ ] **Step 4: Implement batch message save**

Modify `backend/app/services/conversation_service.py`.

Add imports:

```python
import hashlib
import json
from typing import Any
```

Add helper and function after `save_message`:

```python
def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def save_messages_batch(
    db: Session,
    conversation_id: int,
    messages: list[dict[str, Any]],
) -> list[ConversationMessage]:
    """在一次事务中保存多条消息并更新会话活跃时间。"""
    rows: list[ConversationMessage] = []
    for item in messages:
        meta_json = item.get("meta_json")
        meta_text = item.get("meta")
        if meta_text is None and meta_json is not None:
            meta_text = json.dumps(meta_json, ensure_ascii=False)
        row = ConversationMessage(
            conversation_id=conversation_id,
            role=item["role"],
            content=item["content"],
            meta=meta_text,
            turn_id=item.get("turn_id"),
            content_hash=_content_hash(item["content"]),
            meta_json=meta_json,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    db.query(Conversation).filter(Conversation.id == conversation_id).update(
        {"last_active_at": datetime.now()}
    )
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
```

Add `save_messages_batch` to `__all__`.

- [ ] **Step 5: Implement agent turn service**

Create `backend/app/services/agent_turn_service.py`:

```python
"""Agent turn 聚合记录服务。"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation

_PREVIEW_LIMIT = 120


def _preview(text: str | None) -> str | None:
    if text is None:
        return None
    clean = " ".join(text.split()).strip()
    if len(clean) <= _PREVIEW_LIMIT:
        return clean
    return f"{clean[:_PREVIEW_LIMIT]}..."


def create_turn(
    db: Session,
    *,
    farm_id: int,
    session_id: str,
    conversation_id: int | None,
    request_id: str,
    user_message_id: int | None,
    input_text: str,
) -> AgentTurn:
    """创建一轮对话聚合记录。"""
    turn = AgentTurn(
        farm_id=farm_id,
        session_id=session_id,
        conversation_id=conversation_id,
        request_id=request_id,
        user_message_id=user_message_id,
        input_preview=_preview(input_text),
        status="running",
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    if conversation_id is not None:
        db.query(Conversation).filter(Conversation.id == conversation_id).update(
            {"last_turn_id": turn.id}
        )
        db.commit()
    return turn


def finish_turn(
    db: Session,
    turn_id: int,
    *,
    reply_text: str,
    assistant_message_id: int | None,
    selected_tools_count: int | None = None,
    tool_calls_count: int | None = None,
    token_total: int | None = None,
    latency_ms: int | None = None,
    status: str = "success",
    pending_plan_id: str | None = None,
) -> AgentTurn:
    """补全一轮对话结果。"""
    turn = db.query(AgentTurn).filter(AgentTurn.id == turn_id).one()
    turn.reply_preview = _preview(reply_text)
    turn.assistant_message_id = assistant_message_id
    turn.selected_tools_count = selected_tools_count
    turn.tool_calls_count = tool_calls_count
    turn.token_total = token_total
    turn.latency_ms = latency_ms
    turn.status = status
    turn.pending_plan_id = pending_plan_id
    db.commit()
    db.refresh(turn)
    return turn


def mark_event_range(
    db: Session,
    turn_id: int,
    *,
    event_file: str | None,
    seq_start: int | None,
    seq_end: int | None,
    write_status: str,
) -> AgentTurn:
    """记录 turn 对应的事件文件范围。"""
    turn = db.query(AgentTurn).filter(AgentTurn.id == turn_id).one()
    turn.event_file = event_file
    turn.event_seq_start = seq_start
    turn.event_seq_end = seq_end
    turn.event_write_status = write_status
    db.commit()
    db.refresh(turn)
    if turn.conversation_id is not None and seq_end is not None:
        db.query(Conversation).filter(Conversation.id == turn.conversation_id).update(
            {"last_event_seq": seq_end, "last_active_at": datetime.now()}
        )
        db.commit()
    return turn


def get_turns_for_session(db: Session, *, farm_id: int, session_id: str) -> list[AgentTurn]:
    """按创建顺序返回会话 turn。"""
    return (
        db.query(AgentTurn)
        .filter(AgentTurn.farm_id == farm_id, AgentTurn.session_id == session_id)
        .order_by(AgentTurn.id.asc())
        .all()
    )
```

- [ ] **Step 6: Run service tests**

Run:

```bash
cd backend && poetry run pytest tests/services/test_conversation_service.py::TestBatchMessageSave tests/services/test_agent_turn_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Run broader conversation tests**

Run:

```bash
cd backend && poetry run pytest tests/services/test_conversation_service.py tests/services/test_agent_turn_service.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/conversation_service.py backend/app/services/agent_turn_service.py backend/tests/services/test_conversation_service.py backend/tests/services/test_agent_turn_service.py
git commit -m "feat: add lightweight agent turn services"
```

---

### Task 3: Add Recoverable Pending Plan Service Without Replacing Runtime Yet

**Files:**
- Create: `backend/app/services/pending_plan_service.py`
- Test: `backend/tests/services/test_pending_plan_service.py`

- [ ] **Step 1: Write failing pending plan service tests**

Create `backend/tests/services/test_pending_plan_service.py`:

```python
"""Pending plan service 测试。"""

from datetime import datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.farm import Farm
from app.services.pending_plan_service import (
    cancel_active_plan,
    create_pending_plan,
    expire_stale_plans,
    get_active_plan,
    mark_step_executed,
)


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_pending_plan_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()


def test_create_and_get_active_plan_with_steps():
    db = Session()
    plan = create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-plan",
        raw_user_input="王大妈工资100一天，去5号棚收水稻",
        router_decision={"selected_tools": ["manage_workers", "create_operation_work_order"]},
        steps=[
            {
                "skill_name": "manage_workers",
                "params": {"name": "王大妈", "daily_wage": 100},
                "confirmation_text": "确认创建工人王大妈吗？",
            },
            {
                "skill_name": "create_operation_work_order",
                "params": {"field_name": "5号棚", "crop_name": "水稻"},
                "confirmation_text": "确认安排作业吗？",
            },
        ],
        ttl_seconds=300,
    )

    loaded = get_active_plan(db, farm_id=1, session_id="sess-plan")
    assert loaded is not None
    assert loaded.plan_id == plan.plan_id
    assert len(loaded.steps) == 2
    assert loaded.steps[0].params_json["daily_wage"] == 100
    db.close()


def test_mark_step_executed_advances_current_step():
    db = Session()
    plan = create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-exec",
        raw_user_input="记一笔支出",
        router_decision={"selected_tools": ["create_cost_record"]},
        steps=[
            {
                "skill_name": "create_cost_record",
                "params": {"amount": 20},
                "confirmation_text": "确认记账吗？",
            }
        ],
        ttl_seconds=300,
    )

    mark_step_executed(
        db,
        plan_id=plan.plan_id,
        step_index=0,
        result={"record_id": 9},
    )

    loaded = get_active_plan(db, farm_id=1, session_id="sess-exec")
    assert loaded is None
    db.close()


def test_cancel_active_plan():
    db = Session()
    create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-cancel",
        raw_user_input="停用李一凡",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[{"skill_name": "manage_workers", "params": {"name": "李一凡"}}],
        ttl_seconds=300,
    )

    cancelled = cancel_active_plan(db, farm_id=1, session_id="sess-cancel")

    assert cancelled is True
    assert get_active_plan(db, farm_id=1, session_id="sess-cancel") is None
    db.close()


def test_expire_stale_plans():
    db = Session()
    plan = create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-expire",
        raw_user_input="停用李一凡",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[{"skill_name": "manage_workers", "params": {"name": "李一凡"}}],
        ttl_seconds=1,
    )
    plan.expires_at = datetime.now() - timedelta(seconds=1)
    db.commit()

    count = expire_stale_plans(db, now=datetime.now())

    assert count == 1
    assert get_active_plan(db, farm_id=1, session_id="sess-expire") is None
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/services/test_pending_plan_service.py -v
```

Expected: FAIL because `pending_plan_service` does not exist.

- [ ] **Step 3: Implement pending plan service**

Create `backend/app/services/pending_plan_service.py`:

```python
"""可恢复 pending plan 服务。"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.pending_plan import AgentPendingPlan, AgentPendingPlanStep

_ACTIVE_STATUSES = {"pending", "running"}


def create_pending_plan(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    raw_user_input: str,
    router_decision: dict[str, Any] | None,
    steps: list[dict[str, Any]],
    ttl_seconds: int,
) -> AgentPendingPlan:
    """创建待确认计划并取消同会话旧计划。"""
    cancel_active_plan(db, farm_id=farm_id, session_id=session_id)
    plan_id = uuid.uuid4().hex
    plan = AgentPendingPlan(
        plan_id=plan_id,
        farm_id=farm_id,
        session_id=session_id,
        status="pending",
        current_step_index=0,
        raw_user_input=raw_user_input,
        router_decision_json=router_decision,
        expires_at=datetime.now() + timedelta(seconds=ttl_seconds),
    )
    db.add(plan)
    for index, item in enumerate(steps):
        db.add(
            AgentPendingPlanStep(
                plan_id=plan_id,
                step_index=index,
                skill_name=item["skill_name"],
                params_json=item.get("params") or {},
                status="pending",
                requires_confirmation=item.get("requires_confirmation", True),
                confirmation_text=item.get("confirmation_text"),
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def get_active_plan(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    now: datetime | None = None,
) -> AgentPendingPlan | None:
    """获取当前会话未过期的 pending plan。"""
    current = now or datetime.now()
    plan = (
        db.query(AgentPendingPlan)
        .filter(
            AgentPendingPlan.farm_id == farm_id,
            AgentPendingPlan.session_id == session_id,
            AgentPendingPlan.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(AgentPendingPlan.created_at.desc(), AgentPendingPlan.id.desc())
        .first()
    )
    if plan is None:
        return None
    if plan.expires_at is not None and plan.expires_at <= current:
        plan.status = "expired"
        db.commit()
        return None
    return plan


def cancel_active_plan(db: Session, *, farm_id: int, session_id: str | None) -> bool:
    """取消当前会话未完成计划。"""
    plans = (
        db.query(AgentPendingPlan)
        .filter(
            AgentPendingPlan.farm_id == farm_id,
            AgentPendingPlan.session_id == session_id,
            AgentPendingPlan.status.in_(_ACTIVE_STATUSES),
        )
        .all()
    )
    for plan in plans:
        plan.status = "cancelled"
        for step in plan.steps:
            if step.status == "pending":
                step.status = "cancelled"
    db.commit()
    return bool(plans)


def mark_step_executed(
    db: Session,
    *,
    plan_id: str,
    step_index: int,
    result: dict[str, Any] | None,
) -> AgentPendingPlan:
    """标记步骤已执行，必要时完成整项计划。"""
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    target = next(step for step in plan.steps if step.step_index == step_index)
    target.status = "executed"
    target.result_json = result
    next_pending = next((step for step in plan.steps if step.status == "pending"), None)
    if next_pending is None:
        plan.status = "completed"
    else:
        plan.current_step_index = next_pending.step_index
        plan.status = "pending"
    db.commit()
    db.refresh(plan)
    return plan


def mark_step_failed(
    db: Session,
    *,
    plan_id: str,
    step_index: int,
    error_message: str,
) -> AgentPendingPlan:
    """标记步骤失败并暂停计划。"""
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    target = next(step for step in plan.steps if step.step_index == step_index)
    target.status = "failed"
    target.error_message = error_message
    plan.status = "failed"
    db.commit()
    db.refresh(plan)
    return plan


def expire_stale_plans(db: Session, *, now: datetime | None = None) -> int:
    """过期所有超时 pending plan。"""
    current = now or datetime.now()
    plans = (
        db.query(AgentPendingPlan)
        .filter(
            AgentPendingPlan.status.in_(_ACTIVE_STATUSES),
            AgentPendingPlan.expires_at.isnot(None),
            AgentPendingPlan.expires_at <= current,
        )
        .all()
    )
    for plan in plans:
        plan.status = "expired"
        for step in plan.steps:
            if step.status == "pending":
                step.status = "expired"
    db.commit()
    return len(plans)
```

- [ ] **Step 4: Run pending plan tests**

Run:

```bash
cd backend && poetry run pytest tests/services/test_pending_plan_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pending_plan_service.py backend/tests/services/test_pending_plan_service.py
git commit -m "feat: add recoverable pending plan service"
```

---

### Task 4: Add JSONL Agent Event Writer and Reader

**Files:**
- Create: `backend/app/infra/agent_events.py`
- Test: `backend/tests/infra/test_agent_events.py`

- [ ] **Step 1: Write failing event writer tests**

Create `backend/tests/infra/test_agent_events.py`:

```python
"""Agent JSONL event writer 测试。"""

import json
from pathlib import Path

from app.infra.agent_events import AgentEvent, AgentEventWriter, read_event_segment


def test_write_event_appends_jsonl_with_partitioned_path(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)

    result = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-event",
        turn_id=3,
        request_id="abcd1234",
        payload={"content": "查一下作物"},
    )

    assert result.status == "success"
    assert result.seq == 1
    path = Path(result.event_file)
    assert path.exists()
    assert "farm_id=1" in str(path)
    assert "session_id=sess-event" in str(path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event_type"] == "message.user"
    assert rows[0]["payload"] == {"content": "查一下作物"}


def test_writer_increments_sequence_per_session_file(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)

    first = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-seq",
        turn_id=1,
        request_id="req1",
        payload={"content": "一"},
    )
    second = writer.write(
        event_type="message.assistant",
        farm_id=1,
        user_id="user-1",
        session_id="sess-seq",
        turn_id=1,
        request_id="req1",
        payload={"content": "二"},
    )

    assert first.seq == 1
    assert second.seq == 2
    assert first.event_file == second.event_file


def test_read_event_segment_filters_by_seq(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)
    for index in range(3):
        writer.write(
            event_type="tool.call.finished",
            farm_id=1,
            user_id="user-1",
            session_id="sess-read",
            turn_id=1,
            request_id="req1",
            payload={"index": index},
        )

    rows = read_event_segment(writer.event_file_for(farm_id=1, session_id="sess-read"), 2, 3)

    assert [row["seq"] for row in rows] == [2, 3]
    assert rows[0]["payload"] == {"index": 1}


def test_agent_event_dataclass_to_dict_has_stable_shape():
    event = AgentEvent(
        event_id="evt-1",
        event_type="message.user",
        schema_version=1,
        created_at="2026-06-11T10:00:00+08:00",
        farm_id=1,
        user_id="user-1",
        session_id="sess",
        turn_id=1,
        request_id="req",
        seq=1,
        payload={"content": "hi"},
    )

    assert event.to_dict()["event_id"] == "evt-1"
    assert event.to_dict()["schema_version"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/infra/test_agent_events.py -v
```

Expected: FAIL because `app.infra.agent_events` does not exist.

- [ ] **Step 3: Implement JSONL event writer**

Create `backend/app/infra/agent_events.py`:

```python
"""Agent append-only JSONL 事件日志。"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.compat import UTC

logger = logging.getLogger(__name__)
_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9_.=-]+")


@dataclass(frozen=True)
class AgentEvent:
    """Agent 事件稳定外壳。"""

    event_id: str
    event_type: str
    schema_version: int
    created_at: str
    farm_id: int
    user_id: str | None
    session_id: str
    turn_id: int | None
    request_id: str | None
    seq: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "farm_id": self.farm_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "request_id": self.request_id,
            "seq": self.seq,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class AgentEventWriteResult:
    """事件写入结果。"""

    status: str
    event_file: str | None
    seq: int | None
    error_message: str | None = None


class AgentEventWriter:
    """按日期、farm、session 分区追加 JSONL 事件。"""

    def __init__(self, base_dir: str | Path = "data/agent-events") -> None:
        self.base_dir = Path(base_dir)

    def write(
        self,
        *,
        event_type: str,
        farm_id: int,
        user_id: str | None,
        session_id: str,
        turn_id: int | None,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> AgentEventWriteResult:
        try:
            path = self.event_file_for(farm_id=farm_id, session_id=session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            seq = _next_seq(path)
            event = AgentEvent(
                event_id=uuid.uuid4().hex,
                event_type=event_type,
                schema_version=1,
                created_at=datetime.now(UTC).isoformat(),
                farm_id=farm_id,
                user_id=user_id,
                session_id=session_id,
                turn_id=turn_id,
                request_id=request_id,
                seq=seq,
                payload=payload,
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str))
                handle.write("\n")
            return AgentEventWriteResult(status="success", event_file=str(path), seq=seq)
        except Exception as exc:
            logger.warning(
                "Agent event 写入失败 | farm_id=%s session_id=%s event_type=%s error=%s",
                farm_id,
                session_id,
                event_type,
                exc,
            )
            return AgentEventWriteResult(status="failed", event_file=None, seq=None, error_message=str(exc))

    def event_file_for(self, *, farm_id: int, session_id: str) -> Path:
        today = datetime.now(UTC).date().isoformat()
        safe_session = _safe_segment(session_id)
        return (
            self.base_dir
            / f"dt={today}"
            / f"farm_id={farm_id}"
            / f"session_id={safe_session}"
            / "events.jsonl"
        )


def _safe_segment(value: str) -> str:
    return _SAFE_SEGMENT_RE.sub("_", value)[:120]


def _next_seq(path: Path) -> int:
    if not path.exists():
        return 1
    last_seq = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                last_seq = int(json.loads(line).get("seq") or last_seq)
            except json.JSONDecodeError:
                continue
    return last_seq + 1


def read_event_segment(event_file: str | Path, seq_start: int | None, seq_end: int | None) -> list[dict[str, Any]]:
    """读取指定事件文件的 seq 范围。"""
    path = Path(event_file)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            seq = int(row.get("seq") or 0)
            if seq_start is not None and seq < seq_start:
                continue
            if seq_end is not None and seq > seq_end:
                continue
            rows.append(row)
    return rows
```

- [ ] **Step 4: Run event writer tests**

Run:

```bash
cd backend && poetry run pytest tests/infra/test_agent_events.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/agent_events.py backend/tests/infra/test_agent_events.py
git commit -m "feat: add agent event jsonl writer"
```

---

### Task 5: Add Session Flywheel Orchestration Helpers

**Files:**
- Create: `backend/app/agent/application/session_flywheel.py`
- Test: `backend/tests/agent/test_session_flywheel.py`

- [ ] **Step 1: Write failing orchestration tests**

Create `backend/tests/agent/test_session_flywheel.py`:

```python
"""Session flywheel orchestration 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent.application.session_flywheel import (
    SessionFlywheelRecorder,
    build_message_meta,
)
from app.core.database import Base
from app.models.farm import Farm
from app.services.conversation_service import get_or_create_conversation


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_session_flywheel.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场", user_id="user-1"))
    db.commit()
    db.close()


def test_build_message_meta_keeps_only_light_fields():
    meta = build_message_meta(
        skills=["get_farm_status"],
        pending_action={"action_id": "a1"},
        trace_request_id="abcd1234",
        event_file="events.jsonl",
        event_seq_range=(1, 4),
    )

    assert meta == {
        "skills": ["get_farm_status"],
        "pending_action": {"action_id": "a1"},
        "trace_request_id": "abcd1234",
        "event_file": "events.jsonl",
        "event_seq_range": [1, 4],
    }


def test_recorder_records_user_and_assistant_messages_turn_and_events(tmp_path):
    db = Session()
    conv = get_or_create_conversation(db, farm_id=1, session_id="sess-flow", user_id="user-1")
    recorder = SessionFlywheelRecorder(event_base_dir=tmp_path)

    started = recorder.start_turn(
        db,
        farm_id=1,
        user_id="user-1",
        session_id="sess-flow",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message="查一下作物",
    )
    finished = recorder.finish_turn(
        db,
        started,
        assistant_reply="当前有水稻",
        skills=["get_farm_status"],
        pending_action=None,
        selected_tools_count=1,
        tool_calls_count=1,
        token_total=500,
        latency_ms=1200,
        status="success",
    )

    assert finished.turn_id == started.turn_id
    assert finished.user_message_id is not None
    assert finished.assistant_message_id is not None
    assert finished.event_file is not None
    assert finished.event_seq_start == 1
    assert finished.event_seq_end == 2
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_session_flywheel.py -v
```

Expected: FAIL because `session_flywheel` does not exist.

- [ ] **Step 3: Implement session flywheel helpers**

Create `backend/app/agent/application/session_flywheel.py`:

```python
"""会话热路径与事件日志协调工具。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.infra.agent_events import AgentEventWriter
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range
from app.services.conversation_service import save_message


@dataclass(frozen=True)
class StartedTurn:
    turn_id: int
    user_message_id: int | None
    event_file: str | None
    event_seq_start: int | None
    last_event_seq: int | None


@dataclass(frozen=True)
class FinishedTurn:
    turn_id: int
    user_message_id: int | None
    assistant_message_id: int | None
    event_file: str | None
    event_seq_start: int | None
    event_seq_end: int | None


def build_message_meta(
    *,
    skills: list[str] | None = None,
    pending_action: dict[str, Any] | None = None,
    trace_request_id: str | None = None,
    event_file: str | None = None,
    event_seq_range: tuple[int | None, int | None] | None = None,
) -> dict[str, Any]:
    """构造消息轻量 meta。"""
    meta: dict[str, Any] = {}
    if skills:
        meta["skills"] = skills
    if pending_action:
        meta["pending_action"] = pending_action
    if trace_request_id:
        meta["trace_request_id"] = trace_request_id
    if event_file:
        meta["event_file"] = event_file
    if event_seq_range is not None:
        meta["event_seq_range"] = [event_seq_range[0], event_seq_range[1]]
    return meta


class SessionFlywheelRecorder:
    """记录消息、turn 聚合和 JSONL 事件。"""

    def __init__(self, event_base_dir: str | Path = "data/agent-events") -> None:
        self._writer = AgentEventWriter(event_base_dir)

    def start_turn(
        self,
        db: Session,
        *,
        farm_id: int,
        user_id: str | None,
        session_id: str,
        conversation_id: int | None,
        request_id: str,
        user_message: str,
    ) -> StartedTurn:
        user_row = None
        if conversation_id is not None:
            user_row = save_message(
                db,
                conversation_id,
                "user",
                user_message,
                meta=None,
            )
        turn = create_turn(
            db,
            farm_id=farm_id,
            session_id=session_id,
            conversation_id=conversation_id,
            request_id=request_id,
            user_message_id=user_row.id if user_row else None,
            input_text=user_message,
        )
        event = self._writer.write(
            event_type="message.user",
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
            turn_id=turn.id,
            request_id=request_id,
            payload={"content": user_message, "message_id": user_row.id if user_row else None},
        )
        return StartedTurn(
            turn_id=turn.id,
            user_message_id=user_row.id if user_row else None,
            event_file=event.event_file,
            event_seq_start=event.seq,
            last_event_seq=event.seq,
        )

    def finish_turn(
        self,
        db: Session,
        started: StartedTurn,
        *,
        assistant_reply: str,
        skills: list[str] | None,
        pending_action: dict[str, Any] | None,
        selected_tools_count: int | None,
        tool_calls_count: int | None,
        token_total: int | None,
        latency_ms: int | None,
        status: str,
    ) -> FinishedTurn:
        turn = finish_turn(
            db,
            started.turn_id,
            reply_text=assistant_reply,
            assistant_message_id=None,
            selected_tools_count=selected_tools_count,
            tool_calls_count=tool_calls_count,
            token_total=token_total,
            latency_ms=latency_ms,
            status=status,
        )
        assistant_row = None
        if turn.conversation_id is not None:
            meta = build_message_meta(
                skills=skills,
                pending_action=pending_action,
                trace_request_id=turn.request_id,
                event_file=started.event_file,
                event_seq_range=(started.event_seq_start, started.last_event_seq),
            )
            assistant_row = save_message(
                db,
                turn.conversation_id,
                "assistant",
                assistant_reply,
                meta=None,
            )
            assistant_row.meta_json = meta
            db.commit()
            db.refresh(assistant_row)
        event = self._writer.write(
            event_type="message.assistant",
            farm_id=turn.farm_id,
            user_id=None,
            session_id=turn.session_id,
            turn_id=turn.id,
            request_id=turn.request_id,
            payload={
                "content": assistant_reply,
                "message_id": assistant_row.id if assistant_row else None,
                "skills": skills or [],
                "pending_action": pending_action,
            },
        )
        seq_start = started.event_seq_start or event.seq
        seq_end = event.seq or started.last_event_seq
        mark_event_range(
            db,
            turn.id,
            event_file=event.event_file or started.event_file,
            seq_start=seq_start,
            seq_end=seq_end,
            write_status=event.status,
        )
        if assistant_row is not None:
            assistant_row.turn_id = turn.id
            if assistant_row.meta_json is None:
                assistant_row.meta_json = {}
            assistant_row.meta_json["event_file"] = event.event_file or started.event_file
            assistant_row.meta_json["event_seq_range"] = [seq_start, seq_end]
            db.commit()
        finish_turn(
            db,
            turn.id,
            reply_text=assistant_reply,
            assistant_message_id=assistant_row.id if assistant_row else None,
            selected_tools_count=selected_tools_count,
            tool_calls_count=tool_calls_count,
            token_total=token_total,
            latency_ms=latency_ms,
            status=status,
        )
        return FinishedTurn(
            turn_id=turn.id,
            user_message_id=started.user_message_id,
            assistant_message_id=assistant_row.id if assistant_row else None,
            event_file=event.event_file or started.event_file,
            event_seq_start=seq_start,
            event_seq_end=seq_end,
        )
```

- [ ] **Step 4: Run orchestration tests**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_session_flywheel.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/application/session_flywheel.py backend/tests/agent/test_session_flywheel.py
git commit -m "feat: add session flywheel recorder"
```

---

### Task 6: Integrate Turn and Event Recording Into Chat Use Cases

**Files:**
- Modify: `backend/app/agent/application/chat_use_case.py`
- Test: `backend/tests/agent/test_chat_use_case.py`

- [ ] **Step 1: Write failing non-stream integration test**

In `backend/tests/agent/test_chat_use_case.py`, add a test that mocks `invoke_advisor` and asserts user/assistant messages have `turn_id` and a turn row exists:

```python
async def test_chat_records_turn_and_event_metadata(db_session, monkeypatch):
    from app.agent.application import chat_use_case
    from app.models.agent_turn import AgentTurn
    from app.models.conversation import ConversationMessage
    from app.models.farm import Farm
    from app.schemas.agent import ChatRequest

    farm = Farm(id=1, name="默认农场", user_id="user-1")
    db_session.add(farm)
    db_session.commit()

    async def fake_invoke_advisor(*_args, **_kwargs):
        return "当前有水稻"

    monkeypatch.setattr(chat_use_case, "invoke_advisor", fake_invoke_advisor)

    response = await chat_use_case.chat(
        db_session,
        ChatRequest(message="我家有哪些作物栽种", session_id="sess-chat"),
        farm,
        request_id="abcd1234",
    )

    assert response.reply == "当前有水稻"
    turn = db_session.query(AgentTurn).filter_by(session_id="sess-chat").one()
    messages = (
        db_session.query(ConversationMessage)
        .filter(ConversationMessage.turn_id == turn.id)
        .order_by(ConversationMessage.id.asc())
        .all()
    )
    assert [message.role for message in messages] == ["user", "assistant"]
    assert turn.input_preview == "我家有哪些作物栽种"
    assert turn.reply_preview == "当前有水稻"
```

- [ ] **Step 2: Write failing stream integration test**

In `backend/tests/agent/test_chat_use_case.py`, add a test that consumes `stream_chat_events`, mocks `stream_advisor`, and asserts a turn row exists after stream completion:

```python
async def test_stream_chat_records_turn_after_completion(db_session, monkeypatch):
    from app.agent.application import chat_use_case
    from app.models.agent_turn import AgentTurn
    from app.models.farm import Farm
    from app.models.user import User
    from app.schemas.agent import ChatRequest

    user = User(
        id="stream-user-1",
        phone="18800000001",
        password_hash="h",
        nickname="流式用户",
        role="user",
        status="active",
    )
    farm = Farm(id=1, name="默认农场", user_id="user-1")
    existing_farm = db_session.query(Farm).filter(Farm.id == 1).first()
    if existing_farm is None:
        db_session.add(farm)
        db_session.commit()

    async def fake_stream_advisor(*_args, **_kwargs):
        yield "当前"
        yield "有水稻"

    async def fake_flush_trace_queue():
        return None

    monkeypatch.setattr(chat_use_case, "stream_advisor", fake_stream_advisor)
    monkeypatch.setattr(chat_use_case, "_flush_trace_queue", fake_flush_trace_queue)
    monkeypatch.setattr(chat_use_case, "_get_skill_names", lambda *_args, **_kwargs: [])

    chunks = []
    async for chunk in chat_use_case.stream_chat_events(
        db_session,
        ChatRequest(message="我家有哪些作物栽种", session_id="sess-stream"),
        user,
        existing_farm or farm,
        request_id="abcd1234",
    ):
        chunks.append(chunk)

    assert any("当前" in chunk for chunk in chunks)
    turn = db_session.query(AgentTurn).filter_by(session_id="sess-stream").one()
    assert turn.reply_preview == "当前有水稻"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_chat_use_case.py::test_chat_records_turn_and_event_metadata tests/agent/test_chat_use_case.py::test_stream_chat_records_turn_after_completion -v
```

Expected: FAIL because chat use cases still call `save_message` directly and do not create turn rows.

- [ ] **Step 4: Integrate recorder into non-stream chat**

Modify `backend/app/agent/application/chat_use_case.py`:

Add import:

```python
from app.agent.application.session_flywheel import SessionFlywheelRecorder
```

In `chat`, replace the early direct user `save_message` with recorder start:

```python
    recorder = SessionFlywheelRecorder()
    started_turn = None
    conversation = None
    if chat_request.session_id:
        conversation = get_or_create_conversation(
            db,
            farm.id,
            chat_request.session_id,
            user_id=farm.user_id,
        )
        started_turn = recorder.start_turn(
            db,
            farm_id=farm.id,
            user_id=farm.user_id,
            session_id=chat_request.session_id,
            conversation_id=conversation.id,
            request_id=request_id,
            user_message=chat_request.message,
        )
```

Near the end, replace direct assistant `save_message` with recorder finish:

```python
    if conversation and started_turn:
        recorder.finish_turn(
            db,
            started_turn,
            assistant_reply=reply,
            skills=[],
            pending_action=pending_action.model_dump() if pending_action else None,
            selected_tools_count=None,
            tool_calls_count=None,
            token_total=None,
            latency_ms=int((time.perf_counter() - start) * 1000),
            status="success",
        )
```

Remove the old direct `save_message(db, conversation.id, "assistant", reply)` block.

- [ ] **Step 5: Integrate recorder into stream chat**

Modify `stream_chat_events` in `backend/app/agent/application/chat_use_case.py`. `backend/app/agent/application/stream_chat_use_case.py` only re-exports this function and does not need changes.

At the start of `stream_chat_events`, create `recorder` and `started_turn`. Replace direct user save with `recorder.start_turn`. In the `finally` or after full reply is known, call `recorder.finish_turn` once, with `assistant_reply=full_reply`, pending action metadata if present, and `latency_ms`.

Use this guard so cancelled/errored streams do not create empty assistant messages:

```python
        if conversation and started_turn and full_reply:
            recorder.finish_turn(
                db,
                started_turn,
                assistant_reply=full_reply,
                skills=skill_names,
                pending_action=pending_action.model_dump() if pending_action else None,
                selected_tools_count=None,
                tool_calls_count=None,
                token_total=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
                status="success",
            )
```

Use `skill_names`, which is already computed after `_flush_trace_queue()`, as the `skills` argument.

- [ ] **Step 6: Run integration tests**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_chat_use_case.py::test_chat_records_turn_and_event_metadata tests/agent/test_chat_use_case.py::test_stream_chat_records_turn_after_completion -v
```

Expected: PASS.

- [ ] **Step 7: Run related API tests**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_api.py tests/agent/test_chat_use_case.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/agent/application/chat_use_case.py backend/tests/agent/test_chat_use_case.py
git commit -m "feat: record chat turns and session events"
```

---

### Task 7: Optimize Conversation List and Message Metadata Reads

**Files:**
- Modify: `backend/app/agent/application/history_use_case.py`
- Test: `backend/tests/agent/test_history_use_case.py`

- [ ] **Step 1: Write failing history tests**

Create or update `backend/tests/agent/test_history_use_case.py` with tests for lightweight title/preview and `meta_json` parsing:

```python
"""Agent history use case 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent.application.history_use_case import list_conversation_items, list_message_items
from app.core.database import Base
from app.models.conversation import ConversationMessage
from app.models.farm import Farm
from app.services.conversation_service import get_or_create_conversation, save_message


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_history_use_case.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场", user_id="user-1"))
    db.commit()
    db.close()


def test_list_conversation_items_uses_summary_without_full_scan():
    db = Session()
    farm = db.query(Farm).filter_by(id=1).one()
    conv = get_or_create_conversation(db, farm_id=1, session_id="sess-summary", user_id="user-1")
    conv.summary = "用户询问水稻种植情况，助手查询了农场状态。"
    conv.meta_json = {"title": "水稻种植", "preview": "当前有水稻", "category": "种植"}
    db.commit()

    items = list_conversation_items(db, farm=farm, limit=10)

    assert items[0].title == "水稻种植"
    assert items[0].preview == "当前有水稻"
    assert items[0].category == "种植"
    db.close()


def test_list_message_items_prefers_meta_json_over_text_meta():
    db = Session()
    farm = db.query(Farm).filter_by(id=1).one()
    conv = get_or_create_conversation(db, farm_id=1, session_id="sess-meta", user_id="user-1")
    msg = save_message(db, conv.id, "assistant", "确认吗？")
    msg.meta_json = {
        "skills": ["manage_workers"],
        "pending_action": {
            "action_id": "a1",
            "skill_name": "manage_workers",
            "params": {"姓名": "李一凡"},
            "context": {"original_input": "停用李一凡", "extracted_params": {}, "notes": []},
        },
    }
    db.commit()

    items = list_message_items(db, farm=farm, session_id="sess-meta")

    assert items[0].skills == ["manage_workers"]
    assert items[0].pending_action is not None
    assert items[0].pending_action.action_id == "a1"
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_history_use_case.py -v
```

Expected: FAIL if `meta_json` and summary metadata are not used yet.

- [ ] **Step 3: Modify history use case**

In `backend/app/agent/application/history_use_case.py`, update `_build_conversation_summary` so it first uses `conversation.meta_json`:

```python
def _build_conversation_summary(
    db: Session, session_id: str, farm_id: int
) -> tuple[str, str, str]:
    conversation = get_conversation_by_session(db, session_id, farm_id=farm_id)
    meta = conversation.meta_json if conversation else None
    if isinstance(meta, dict):
        title = meta.get("title")
        preview = meta.get("preview")
        category = meta.get("category")
        if title and preview and category:
            return str(title), str(preview), str(category)
    if conversation and conversation.summary:
        return (
            _truncate_text(conversation.summary, 18),
            _truncate_text(conversation.summary, 24),
            "对话",
        )
    messages = get_conversation_messages(db, session_id, farm_id=farm_id)
    ...
```

In `list_message_items`, prefer `message.meta_json` and fall back to `message.meta`:

```python
        meta_obj = message.meta_json if isinstance(message.meta_json, dict) else None
        if meta_obj is None and message.meta:
            try:
                parsed = json.loads(message.meta)
                if isinstance(parsed, dict):
                    meta_obj = parsed
            except (json.JSONDecodeError, AttributeError):
                meta_obj = None
        if meta_obj:
            skills = meta_obj.get("skills")
            pending_raw = meta_obj.get("pending_action")
            if pending_raw:
                pending_action = PendingActionResponse.model_validate(pending_raw)
```

- [ ] **Step 4: Run history tests**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_history_use_case.py -v
```

Expected: PASS.

- [ ] **Step 5: Run agent API history tests**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_api.py tests/api/test_agent_api.py tests/agent/test_history_use_case.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/application/history_use_case.py backend/tests/agent/test_history_use_case.py backend/tests/test_agent_api.py backend/tests/api/test_agent_api.py
git commit -m "perf: use lightweight conversation history metadata"
```

---

### Task 8: Add Debug Export v2 Service and API

**Files:**
- Create: `backend/app/services/session_debug_export_service.py`
- Modify: `backend/app/api/agent.py`
- Test: `backend/tests/services/test_session_debug_export_service.py`
- Test: `backend/tests/api/test_agent_debug_export.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/services/test_session_debug_export_service.py`:

```python
"""Session debug export service 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.infra.agent_events import AgentEventWriter
from app.models.farm import Farm
from app.services.agent_turn_service import create_turn, mark_event_range
from app.services.conversation_service import get_or_create_conversation, save_message
from app.services.pending_plan_service import create_pending_plan
from app.services.session_debug_export_service import build_session_debug_export


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_session_debug_export_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场", user_id="user-1"))
    db.commit()
    db.close()


def test_build_session_debug_export_includes_messages_turns_pending_and_events(tmp_path):
    db = Session()
    conv = get_or_create_conversation(db, farm_id=1, session_id="sess-debug", user_id="user-1")
    user_msg = save_message(db, conv.id, "user", "停用李一凡")
    assistant_msg = save_message(db, conv.id, "assistant", "确认停用吗？")
    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-debug",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=user_msg.id,
        input_text="停用李一凡",
    )
    writer = AgentEventWriter(base_dir=tmp_path)
    first = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-debug",
        turn_id=turn.id,
        request_id="abcd1234",
        payload={"content": "停用李一凡"},
    )
    second = writer.write(
        event_type="pending.plan.created",
        farm_id=1,
        user_id="user-1",
        session_id="sess-debug",
        turn_id=turn.id,
        request_id="abcd1234",
        payload={"plan_id": "p1"},
    )
    mark_event_range(
        db,
        turn.id,
        event_file=first.event_file,
        seq_start=first.seq,
        seq_end=second.seq,
        write_status="success",
    )
    create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-debug",
        raw_user_input="停用李一凡",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[{"skill_name": "manage_workers", "params": {"name": "李一凡"}}],
        ttl_seconds=300,
    )

    result = build_session_debug_export(db, farm_id=1, session_id="sess-debug")

    assert result["format"] == "farm-manager.chat-session-debug.v2"
    assert len(result["messages"]) == 2
    assert result["turns"][0]["request_id"] == "abcd1234"
    assert result["events"][0]["event_type"] == "message.user"
    assert result["pending_plans"][0]["raw_user_input"] == "停用李一凡"
    db.close()
```

- [ ] **Step 2: Run service test to verify it fails**

Run:

```bash
cd backend && poetry run pytest tests/services/test_session_debug_export_service.py -v
```

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement debug export service**

Create `backend/app/services/session_debug_export_service.py`:

```python
"""Session debug export v2 组装服务。"""

from typing import Any

from sqlalchemy.orm import Session

from app.infra.agent_events import read_event_segment
from app.models.pending_plan import AgentPendingPlan
from app.services.agent_turn_service import get_turns_for_session
from app.services.conversation_service import get_conversation_by_session, get_conversation_messages


def build_session_debug_export(db: Session, *, farm_id: int, session_id: str) -> dict[str, Any]:
    """组装包含热数据和事件证据的调试 JSON。"""
    conversation = get_conversation_by_session(db, session_id, farm_id=farm_id)
    messages = get_conversation_messages(db, session_id, farm_id=farm_id)
    turns = get_turns_for_session(db, farm_id=farm_id, session_id=session_id)
    pending_plans = (
        db.query(AgentPendingPlan)
        .filter(AgentPendingPlan.farm_id == farm_id, AgentPendingPlan.session_id == session_id)
        .order_by(AgentPendingPlan.id.asc())
        .all()
    )
    events: list[dict[str, Any]] = []
    missing_segments: list[dict[str, Any]] = []
    for turn in turns:
        if not turn.event_file:
            continue
        rows = read_event_segment(turn.event_file, turn.event_seq_start, turn.event_seq_end)
        if rows:
            events.extend(rows)
        else:
            missing_segments.append(
                {
                    "turn_id": turn.id,
                    "event_file": turn.event_file,
                    "event_seq_start": turn.event_seq_start,
                    "event_seq_end": turn.event_seq_end,
                }
            )
    return {
        "format": "farm-manager.chat-session-debug.v2",
        "session": {
            "id": conversation.id if conversation else None,
            "farm_id": farm_id,
            "session_id": session_id,
            "status": conversation.status if conversation else None,
            "summary": conversation.summary if conversation else None,
            "created_at": conversation.created_at.isoformat() if conversation and conversation.created_at else None,
            "last_active_at": conversation.last_active_at.isoformat() if conversation and conversation.last_active_at else None,
        },
        "messages": [
            {
                "id": message.id,
                "turn_id": message.turn_id,
                "role": message.role,
                "content": message.content,
                "meta": message.meta_json,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message in messages
        ],
        "turns": [
            {
                "id": turn.id,
                "request_id": turn.request_id,
                "input_preview": turn.input_preview,
                "reply_preview": turn.reply_preview,
                "selected_tools_count": turn.selected_tools_count,
                "tool_calls_count": turn.tool_calls_count,
                "token_total": turn.token_total,
                "latency_ms": turn.latency_ms,
                "status": turn.status,
                "pending_plan_id": turn.pending_plan_id,
                "event_file": turn.event_file,
                "event_seq_start": turn.event_seq_start,
                "event_seq_end": turn.event_seq_end,
                "event_write_status": turn.event_write_status,
            }
            for turn in turns
        ],
        "pending_plans": [_pending_plan_to_dict(plan) for plan in pending_plans],
        "events": events,
        "missing_event_segments": missing_segments,
    }


def _pending_plan_to_dict(plan: AgentPendingPlan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "plan_id": plan.plan_id,
        "farm_id": plan.farm_id,
        "session_id": plan.session_id,
        "status": plan.status,
        "current_step_index": plan.current_step_index,
        "raw_user_input": plan.raw_user_input,
        "router_decision": plan.router_decision_json,
        "expires_at": plan.expires_at.isoformat() if plan.expires_at else None,
        "steps": [
            {
                "id": step.id,
                "step_index": step.step_index,
                "skill_name": step.skill_name,
                "params": step.params_json,
                "status": step.status,
                "requires_confirmation": step.requires_confirmation,
                "confirmation_text": step.confirmation_text,
                "result": step.result_json,
                "error_message": step.error_message,
            }
            for step in plan.steps
        ],
    }
```

- [ ] **Step 4: Add API endpoint test**

Create `backend/tests/api/test_agent_debug_export.py`:

```python
"""Agent debug export API 测试。"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.agent import router
from app.api.deps import get_current_farm, get_current_user, get_db
from app.core.database import Base
from app.infra.limiter import limiter
from app.models.farm import Farm
from app.models.user import User
from app.services.conversation_service import get_or_create_conversation, save_message


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_debug_export_api.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(
        User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            status="active",
        )
    )
    db.add(Farm(id=1, name="默认农场", user_id="test-user-001"))
    conv = get_or_create_conversation(db, farm_id=1, session_id="sess-debug", user_id="test-user-001")
    save_message(db, conv.id, "user", "查一下作物")
    db.close()


def _client() -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_farm(db=Depends(override_get_db)) -> Farm:
        return db.query(Farm).filter(Farm.id == 1).one()

    def override_get_current_user() -> User:
        return User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            role="user",
            status="active",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


def test_get_session_debug_export_v2():
    client = _client()

    response = client.get("/agent/conversations/sess-debug/debug-export")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "farm-manager.chat-session-debug.v2"
    assert "messages" in body
    assert "turns" in body
    assert "events" in body
```

- [ ] **Step 5: Add API endpoint**

Modify `backend/app/api/agent.py`.

Add import:

```python
from app.services.session_debug_export_service import build_session_debug_export
```

Add route after the messages route:

```python
@router.get("/conversations/{session_id}/debug-export")
@limiter.limit("10/minute")
def get_session_debug_export(
    request: Request,
    response: Response,
    session_id: str,
    simulate_user_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    farm: Farm = Depends(get_current_farm),
) -> dict:
    """导出会话调试 JSON v2。"""
    if simulate_user_id:
        _, farm = resolve_stream_user_and_farm(db, current_user, simulate_user_id)
    return build_session_debug_export(db, farm_id=farm.id, session_id=session_id)
```

- [ ] **Step 6: Run debug export tests**

Run:

```bash
cd backend && poetry run pytest tests/services/test_session_debug_export_service.py tests/api/test_agent_debug_export.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/session_debug_export_service.py backend/app/api/agent.py backend/tests/services/test_session_debug_export_service.py backend/tests/api/test_agent_debug_export.py
git commit -m "feat: add session debug export v2"
```

---

### Task 9: Add Session Summary and Dataset Export Builders

**Files:**
- Create: `backend/app/services/session_dataset_service.py`
- Test: `backend/tests/services/test_session_dataset_service.py`

- [ ] **Step 1: Write failing dataset builder tests**

Create `backend/tests/services/test_session_dataset_service.py`:

```python
"""Session dataset service 测试。"""

from app.services.session_dataset_service import build_sft_samples, build_tool_selection_samples


def test_build_sft_samples_from_events():
    events = [
        {"event_type": "message.user", "turn_id": 1, "payload": {"content": "我家有哪些作物"}},
        {"event_type": "tool.call.finished", "turn_id": 1, "payload": {"tool_name": "get_farm_status", "result": {"crops": ["水稻"]}}},
        {"event_type": "message.assistant", "turn_id": 1, "payload": {"content": "当前有水稻"}},
    ]

    samples = build_sft_samples(events)

    assert samples == [
        {
            "turn_id": 1,
            "instruction": "我家有哪些作物",
            "tool_results": [{"tool_name": "get_farm_status", "result": {"crops": ["水稻"]}}],
            "response": "当前有水稻",
            "source": "agent_event_log",
        }
    ]


def test_build_tool_selection_samples_from_router_events():
    events = [
        {"event_type": "message.user", "turn_id": 2, "payload": {"content": "停用李一凡"}},
        {
            "event_type": "router.decision",
            "turn_id": 2,
            "payload": {
                "selected_tools": ["manage_workers"],
                "rejected_tools": ["get_workers"],
                "fallback": False,
            },
        },
        {"event_type": "tool.call.finished", "turn_id": 2, "payload": {"tool_name": "manage_workers", "status": "pending"}},
    ]

    samples = build_tool_selection_samples(events)

    assert samples == [
        {
            "turn_id": 2,
            "input": "停用李一凡",
            "selected_tools": ["manage_workers"],
            "rejected_tools": ["get_workers"],
            "actual_tools": ["manage_workers"],
            "fallback": False,
            "source": "agent_event_log",
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/services/test_session_dataset_service.py -v
```

Expected: FAIL because `session_dataset_service` does not exist.

- [ ] **Step 3: Implement dataset builders**

Create `backend/app/services/session_dataset_service.py`:

```python
"""从 Agent 事件日志构建调优/评测样本。"""

from collections import defaultdict
from typing import Any


def _events_by_turn(events: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        turn_id = event.get("turn_id")
        if turn_id is not None:
            grouped[int(turn_id)].append(event)
    return grouped


def build_sft_samples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建回复调优 SFT 样本。"""
    samples: list[dict[str, Any]] = []
    for turn_id, rows in sorted(_events_by_turn(events).items()):
        user = next((row for row in rows if row.get("event_type") == "message.user"), None)
        assistant = next((row for row in rows if row.get("event_type") == "message.assistant"), None)
        if user is None or assistant is None:
            continue
        tool_results = [
            {
                "tool_name": row.get("payload", {}).get("tool_name"),
                "result": row.get("payload", {}).get("result"),
            }
            for row in rows
            if row.get("event_type") == "tool.call.finished"
        ]
        samples.append(
            {
                "turn_id": turn_id,
                "instruction": user.get("payload", {}).get("content", ""),
                "tool_results": tool_results,
                "response": assistant.get("payload", {}).get("content", ""),
                "source": "agent_event_log",
            }
        )
    return samples


def build_tool_selection_samples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建工具选择训练/评测样本。"""
    samples: list[dict[str, Any]] = []
    for turn_id, rows in sorted(_events_by_turn(events).items()):
        user = next((row for row in rows if row.get("event_type") == "message.user"), None)
        router = next((row for row in rows if row.get("event_type") == "router.decision"), None)
        if user is None or router is None:
            continue
        actual_tools = [
            row.get("payload", {}).get("tool_name")
            for row in rows
            if row.get("event_type") == "tool.call.finished"
            and row.get("payload", {}).get("tool_name")
        ]
        payload = router.get("payload", {})
        samples.append(
            {
                "turn_id": turn_id,
                "input": user.get("payload", {}).get("content", ""),
                "selected_tools": payload.get("selected_tools") or [],
                "rejected_tools": payload.get("rejected_tools") or [],
                "actual_tools": actual_tools,
                "fallback": bool(payload.get("fallback")),
                "source": "agent_event_log",
            }
        )
    return samples
```

- [ ] **Step 4: Run dataset tests**

Run:

```bash
cd backend && poetry run pytest tests/services/test_session_dataset_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/session_dataset_service.py backend/tests/services/test_session_dataset_service.py
git commit -m "feat: build agent tuning samples from events"
```

---

### Task 10: Final Verification and Documentation Update

**Files:**
- Modify: `docs/superpowers/specs/2026-06-11-agent-session-storage-data-flywheel-design.md` only if implementation decisions diverged from the design.
- Modify: `docs/plans/current-sprint.md` only if the project tracks shipped work there.

- [ ] **Step 1: Run focused backend test suite**

Run:

```bash
cd backend && poetry run pytest \
  tests/test_agent_session_flywheel_models.py \
  tests/services/test_conversation_service.py \
  tests/services/test_agent_turn_service.py \
  tests/services/test_pending_plan_service.py \
  tests/infra/test_agent_events.py \
  tests/agent/test_session_flywheel.py \
  tests/agent/test_chat_use_case.py \
  tests/agent/test_history_use_case.py \
  tests/services/test_session_debug_export_service.py \
  tests/services/test_session_dataset_service.py \
  tests/test_agent_api.py \
  tests/api/test_agent_api.py \
  tests/api/test_agent_debug_export.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run schema and lint checks**

Run:

```bash
cd backend && poetry run pytest tests/test_schema_hardening_audit.py -v
cd backend && poetry run ruff check app tests
cd backend && poetry run ruff format --check app tests
```

Expected: PASS. On failure, stop the implementation run, copy the exact failing command output into the handoff summary, and do not change files outside this plan.

- [ ] **Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected: only files intentionally changed by the implementation remain unstaged. Do not stage unrelated mobile/admin/weather changes already present in the worktree.

- [ ] **Step 4: Inspect and commit final docs adjustments**

Run:

```bash
git diff -- docs/superpowers/specs/2026-06-11-agent-session-storage-data-flywheel-design.md docs/plans/current-sprint.md
```

Expected: empty diff when implementation matched the design without sprint-doc updates.

When the diff is non-empty and only contains implementation-note updates for this work, commit it:

```bash
git add docs/superpowers/specs/2026-06-11-agent-session-storage-data-flywheel-design.md docs/plans/current-sprint.md
git commit -m "docs: update agent session flywheel rollout notes"
```

When the diff is empty, record `No final docs adjustment needed` in the final handoff summary.

- [ ] **Step 5: Final handoff summary**

Report:

- Commits created.
- Tests run and pass/fail status.
- Any unrelated dirty worktree files ignored.
- Remaining follow-up: deeper integration with Skill Router event emission and admin-web v2 consumption if not completed in this plan.
