# Agent Data Flywheel Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight Data Flywheel admin page that lists Agent turn samples, shows event/debug evidence, supports quality labels, exports JSONL, and creates regression case drafts.

**Architecture:** Keep the online chat path unchanged. Add two small ORM models for labels and case drafts, a focused service that composes sample list/detail data from `agent_turns`, conversations, labels, debug export, and event logs, then expose admin-only APIs consumed by a new React page. The frontend uses existing Ant Design, dark theme tokens, trace payload helpers, and focused components for queue, detail, annotation, tool comparison, pending lifecycle, and case draft preview.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, pytest, React 19, TypeScript, Ant Design 5, Vitest, Testing Library.

---

## Current Context

Read these files before starting implementation:

- `docs/superpowers/specs/2026-06-11-agent-data-flywheel-admin-design.md`
- `docs/superpowers/specs/2026-06-11-agent-session-storage-data-flywheel-design.md`
- `backend/app/models/agent_turn.py`
- `backend/app/models/conversation.py`
- `backend/app/models/pending_plan.py`
- `backend/app/models/simulation.py`
- `backend/app/services/session_debug_export_service.py`
- `backend/app/services/session_dataset_service.py`
- `backend/app/infra/agent_events.py`
- `backend/app/api/admin_trace.py`
- `backend/app/bootstrap/routes.py`
- `admin-web/src/pages/TraceMonitor/index.tsx`
- `admin-web/src/pages/Simulation/index.tsx`
- `admin-web/src/pages/Playground/index.tsx`
- `admin-web/src/api/admin.ts`
- `admin-web/src/api/agent.ts`
- `admin-web/src/layouts/AdminLayout.tsx`
- `admin-web/src/App.tsx`
- `admin-web/src/styles/theme.ts`

Important worktree note: the repository may already contain unrelated modified/untracked files. Do not revert them. Stage and commit only the files listed by each task.

## Target File Structure

Backend files:

- Create `backend/app/models/data_flywheel.py`: ORM models for labels and case drafts.
- Modify `backend/app/models/__init__.py`: import/export the new models.
- Create `backend/alembic/versions/20260611_agent_data_flywheel.py`: idempotent migration.
- Create `backend/app/services/data_flywheel_service.py`: sample listing, detail assembly, label persistence, JSONL export payloads, case draft creation.
- Create `backend/app/api/admin_data_flywheel.py`: admin API routes.
- Modify `backend/app/bootstrap/routes.py`: register the admin data flywheel router.
- Create `backend/tests/test_agent_data_flywheel_models.py`: model tests.
- Create `backend/tests/services/test_data_flywheel_service.py`: service tests.
- Create `backend/tests/api/test_admin_data_flywheel.py`: API tests.

Frontend files:

- Create `admin-web/src/api/dataFlywheel.ts`: API types and functions.
- Create `admin-web/src/pages/DataFlywheel/index.tsx`: page shell and orchestration.
- Create `admin-web/src/pages/DataFlywheel/components/SampleQueueTable.tsx`: sample list table.
- Create `admin-web/src/pages/DataFlywheel/components/SampleDetailPanel.tsx`: evidence detail panel.
- Create `admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx`: label and actions panel.
- Create `admin-web/src/pages/DataFlywheel/components/ToolComparison.tsx`: selected vs actual tools.
- Create `admin-web/src/pages/DataFlywheel/components/PendingLifecycleView.tsx`: pending lifecycle timeline.
- Create `admin-web/src/pages/DataFlywheel/components/CaseDraftPreview.tsx`: case draft preview modal.
- Create `admin-web/src/pages/DataFlywheel/index.test.tsx`: page integration tests.
- Create `admin-web/src/api/dataFlywheel.test.ts`: API wrapper tests.
- Modify `admin-web/src/App.tsx`: add route.
- Modify `admin-web/src/layouts/AdminLayout.tsx`: add menu item and title.

Implementation should not add MongoDB, Kafka, ClickHouse, Celery, vector DBs, or new frontend component libraries.

---

### Task 1: Add Data Flywheel ORM Models and Migration

**Files:**
- Create: `backend/app/models/data_flywheel.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260611_agent_data_flywheel.py`
- Test: `backend/tests/test_agent_data_flywheel_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `backend/tests/test_agent_data_flywheel_models.py`:

```python
"""Agent 数据飞轮模型测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.data_flywheel import AgentCaseDraft, AgentDataFlywheelLabel
from app.models.farm import Farm


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_data_flywheel_models.db",
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


def test_label_round_trip():
    db = Session()
    label = AgentDataFlywheelLabel(
        farm_id=1,
        sample_id="turn:1:sess-1:12",
        sample_type="session_turn",
        session_id="sess-1",
        turn_id=12,
        request_id="abcd1234",
        label="wrong_tool_selection",
        comment="选了写工具但实际只需要查询",
        annotator_id="admin-1",
    )
    db.add(label)
    db.commit()
    db.refresh(label)

    assert label.id is not None
    assert label.sample_id == "turn:1:sess-1:12"
    assert label.label == "wrong_tool_selection"
    assert label.comment == "选了写工具但实际只需要查询"
    assert label.created_at is not None
    assert label.updated_at is not None
    db.close()


def test_case_draft_round_trip():
    db = Session()
    draft = AgentCaseDraft(
        farm_id=1,
        draft_id="draft-abc123",
        source_sample_id="turn:1:sess-1:12",
        target_type="evaluation_replay",
        status="draft",
        case_json={
            "case_id": "regression-sess-1-12",
            "description": "王大妈工资缺失回归",
            "user_input": "王大妈工资100一天去5号棚收水稻",
            "reply_assertions": [{"contains": "100"}],
            "metadata": {"source_sample_id": "turn:1:sess-1:12"},
        },
        created_by="admin-1",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    assert draft.id is not None
    assert draft.status == "draft"
    assert draft.case_json["case_id"] == "regression-sess-1-12"
    assert draft.case_json["metadata"]["source_sample_id"] == "turn:1:sess-1:12"
    db.close()
```

- [ ] **Step 2: Run the model test to verify it fails**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_data_flywheel_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.data_flywheel'`.

- [ ] **Step 3: Create the ORM models**

Create `backend/app/models/data_flywheel.py`:

```python
"""Agent 数据飞轮标注与用例草稿模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.core.database import Base


class AgentDataFlywheelLabel(Base):
    """Data Flywheel 样本标注。"""

    __tablename__ = "agent_data_flywheel_labels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    sample_id = Column(String(160), nullable=False, index=True)
    sample_type = Column(String(40), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    turn_id = Column(Integer, nullable=True, index=True)
    request_id = Column(String(32), nullable=True, index=True)
    label = Column(String(64), nullable=False, index=True)
    comment = Column(Text, nullable=True)
    annotator_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )


class AgentCaseDraft(Base):
    """从飞轮样本生成的 simulation / evaluation case 草稿。"""

    __tablename__ = "agent_case_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    draft_id = Column(String(64), nullable=False, unique=True, index=True)
    source_sample_id = Column(String(160), nullable=False, index=True)
    target_type = Column(String(32), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    case_json = Column(JSON, nullable=False)
    created_by = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )
```

- [ ] **Step 4: Register models in `backend/app/models/__init__.py`**

Add this import near the other model imports:

```python
from app.models.data_flywheel import AgentCaseDraft, AgentDataFlywheelLabel
```

Add these names to `__all__`:

```python
    "AgentDataFlywheelLabel",
    "AgentCaseDraft",
```

- [ ] **Step 5: Create the Alembic migration**

Create `backend/alembic/versions/20260611_agent_data_flywheel.py`:

```python
"""agent data flywheel admin storage

Revision ID: 20260611_agent_data_flywheel
Revises: 20260611_agent_session_flywheel
Create Date: 2026-06-11 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260611_agent_data_flywheel"
down_revision: Union[str, None] = "20260611_agent_session_flywheel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_data_flywheel_labels" not in tables:
        op.create_table(
            "agent_data_flywheel_labels",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
            sa.Column("sample_id", sa.String(length=160), nullable=False),
            sa.Column("sample_type", sa.String(length=40), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("turn_id", sa.Integer(), nullable=True),
            sa.Column("request_id", sa.String(length=32), nullable=True),
            sa.Column("label", sa.String(length=64), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("annotator_id", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_agent_data_flywheel_labels_farm_id", "agent_data_flywheel_labels", ["farm_id"])
        op.create_index("ix_agent_data_flywheel_labels_sample_id", "agent_data_flywheel_labels", ["sample_id"])
        op.create_index("ix_agent_data_flywheel_labels_sample_type", "agent_data_flywheel_labels", ["sample_type"])
        op.create_index("ix_agent_data_flywheel_labels_session_id", "agent_data_flywheel_labels", ["session_id"])
        op.create_index("ix_agent_data_flywheel_labels_turn_id", "agent_data_flywheel_labels", ["turn_id"])
        op.create_index("ix_agent_data_flywheel_labels_request_id", "agent_data_flywheel_labels", ["request_id"])
        op.create_index("ix_agent_data_flywheel_labels_label", "agent_data_flywheel_labels", ["label"])
        op.create_index("ix_agent_data_flywheel_labels_annotator_id", "agent_data_flywheel_labels", ["annotator_id"])
        op.create_index("ix_agent_data_flywheel_labels_created_at", "agent_data_flywheel_labels", ["created_at"])
    if "agent_case_drafts" not in tables:
        op.create_table(
            "agent_case_drafts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
            sa.Column("draft_id", sa.String(length=64), nullable=False, unique=True),
            sa.Column("source_sample_id", sa.String(length=160), nullable=False),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("case_json", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_agent_case_drafts_farm_id", "agent_case_drafts", ["farm_id"])
        op.create_index("ix_agent_case_drafts_draft_id", "agent_case_drafts", ["draft_id"], unique=True)
        op.create_index("ix_agent_case_drafts_source_sample_id", "agent_case_drafts", ["source_sample_id"])
        op.create_index("ix_agent_case_drafts_target_type", "agent_case_drafts", ["target_type"])
        op.create_index("ix_agent_case_drafts_status", "agent_case_drafts", ["status"])
        op.create_index("ix_agent_case_drafts_created_by", "agent_case_drafts", ["created_by"])
        op.create_index("ix_agent_case_drafts_created_at", "agent_case_drafts", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_case_drafts" in tables:
        op.drop_table("agent_case_drafts")
    if "agent_data_flywheel_labels" in tables:
        op.drop_table("agent_data_flywheel_labels")
```

- [ ] **Step 6: Run model tests**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_data_flywheel_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Run formatting and lint for touched backend files**

Run:

```bash
cd backend && poetry run ruff format app/models/data_flywheel.py tests/test_agent_data_flywheel_models.py alembic/versions/20260611_agent_data_flywheel.py && poetry run ruff check app/models/data_flywheel.py app/models/__init__.py tests/test_agent_data_flywheel_models.py alembic/versions/20260611_agent_data_flywheel.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  backend/app/models/data_flywheel.py \
  backend/app/models/__init__.py \
  backend/alembic/versions/20260611_agent_data_flywheel.py \
  backend/tests/test_agent_data_flywheel_models.py
git commit -m "feat: add agent data flywheel storage"
```

---

### Task 2: Add Data Flywheel Service

**Files:**
- Create: `backend/app/services/data_flywheel_service.py`
- Test: `backend/tests/services/test_data_flywheel_service.py`

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/services/test_data_flywheel_service.py`:

```python
"""Agent 数据飞轮服务测试。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.infra.agent_events import AgentEventWriter
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.models.farm import Farm
from app.services.data_flywheel_service import (
    add_sample_label,
    build_case_draft,
    export_sample_jsonl,
    get_sample_detail,
    list_samples,
)

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_data_flywheel_service.db",
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


def _seed_turn(db, tmp_path):
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-flywheel")
    db.add(conv)
    db.commit()
    user_msg = ConversationMessage(
        conversation_id=conv.id,
        turn_id=1,
        role="user",
        content="王大妈工资100一天，去5号棚收水稻",
    )
    assistant_msg = ConversationMessage(
        conversation_id=conv.id,
        turn_id=1,
        role="assistant",
        content="已安排王大妈去5号棚收水稻",
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()

    writer = AgentEventWriter(base_dir=tmp_path)
    event_rows = [
        ("message.user", {"content": user_msg.content}),
        (
            "router.decision",
            {
                "selected_tools": [
                    "manage_workers",
                    "create_operation_work_order",
                ],
                "rejected_tools": ["get_weather_forecast"],
                "fallback": False,
            },
        ),
        ("tool.call.finished", {"tool_name": "manage_workers", "result": {"id": 7}}),
        (
            "pending.plan.created",
            {"plan_id": "plan-1", "steps": [{"skill_name": "manage_workers"}]},
        ),
        ("message.assistant", {"content": assistant_msg.content}),
    ]
    first = None
    last = None
    for event_type, payload in event_rows:
        result = writer.write(
            event_type=event_type,
            farm_id=1,
            user_id="user-1",
            session_id="sess-flywheel",
            turn_id=1,
            request_id="abcd1234",
            payload=payload,
        )
        first = first or result
        last = result

    turn = AgentTurn(
        farm_id=1,
        session_id="sess-flywheel",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        input_preview=user_msg.content,
        reply_preview=assistant_msg.content,
        selected_tools_count=2,
        tool_calls_count=1,
        token_total=680,
        latency_ms=1320,
        status="success",
        pending_plan_id="plan-1",
        event_file=first.event_file,
        event_seq_start=first.seq,
        event_seq_end=last.seq,
        event_write_status="success",
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return turn


def test_list_samples_returns_lightweight_turn_rows(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)

    result = list_samples(db, farm_id=1)

    assert result["total"] == 1
    item = result["items"][0]
    assert item["sample_id"] == f"turn:1:sess-flywheel:{turn.id}"
    assert item["sample_type"] == "session_turn"
    assert item["session_id"] == "sess-flywheel"
    assert item["request_id"] == "abcd1234"
    assert item["user_input_preview"] == "王大妈工资100一天，去5号棚收水稻"
    assert item["assistant_reply_preview"] == "已安排王大妈去5号棚收水稻"
    assert item["selected_tools"] == ["manage_workers", "create_operation_work_order"]
    assert item["actual_tools"] == ["manage_workers"]
    assert item["annotation_status"] == "unlabeled"
    db.close()


def test_labels_are_reflected_in_sample_list(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    add_sample_label(
        db,
        farm_id=1,
        sample_id=sample_id,
        sample_type="session_turn",
        session_id="sess-flywheel",
        turn_id=turn.id,
        request_id="abcd1234",
        label="wrong_tool_selection",
        comment="实际只执行了一个工具",
        annotator_id="admin-1",
    )
    result = list_samples(db, farm_id=1, label="wrong_tool_selection")

    assert result["total"] == 1
    assert result["items"][0]["quality_labels"] == ["wrong_tool_selection"]
    assert result["items"][0]["annotation_status"] == "labeled"
    db.close()


def test_get_sample_detail_includes_events_and_debug_export(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert detail["sample"]["sample_id"] == sample_id
    assert detail["turn"]["request_id"] == "abcd1234"
    assert detail["router_decision"]["selected_tools"] == [
        "manage_workers",
        "create_operation_work_order",
    ]
    assert detail["tool_events"][0]["payload"]["tool_name"] == "manage_workers"
    assert detail["pending_lifecycle"][0]["event_type"] == "pending.plan.created"
    assert detail["source"]["event_seq_start"] == 1
    assert detail["debug_export"]["format"] == "farm-manager.chat-session-debug.v2"
    db.close()


def test_export_sample_jsonl_returns_one_serializable_line(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"
    add_sample_label(
        db,
        farm_id=1,
        sample_id=sample_id,
        sample_type="session_turn",
        session_id="sess-flywheel",
        turn_id=turn.id,
        request_id="abcd1234",
        label="missing_wage",
        comment="回复中没有提到工资",
        annotator_id="admin-1",
    )

    payload = export_sample_jsonl(db, farm_id=1, sample_id=sample_id)

    assert payload["filename"].startswith("data-flywheel-sample-")
    assert '"sample_id": "turn:1:sess-flywheel:' in payload["content"]
    assert '"quality_labels": ["missing_wage"]' in payload["content"]
    db.close()


def test_build_case_draft_from_sample(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"
    add_sample_label(
        db,
        farm_id=1,
        sample_id=sample_id,
        sample_type="session_turn",
        session_id="sess-flywheel",
        turn_id=turn.id,
        request_id="abcd1234",
        label="needs_regression",
        comment="需要覆盖多工具执行",
        annotator_id="admin-1",
    )

    draft = build_case_draft(
        db,
        farm_id=1,
        sample_id=sample_id,
        target_type="evaluation_replay",
        created_by="admin-1",
    )

    assert draft["status"] == "draft"
    assert draft["target_type"] == "evaluation_replay"
    assert draft["case_json"]["user_input"] == "王大妈工资100一天，去5号棚收水稻"
    assert draft["case_json"]["expected_skills"][0]["name"] == "manage_workers"
    assert draft["case_json"]["metadata"]["source_sample_id"] == sample_id
    db.close()
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/services/test_data_flywheel_service.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.data_flywheel_service'`.

- [ ] **Step 3: Create service module with constants and helpers**

Create the first part of `backend/app/services/data_flywheel_service.py`:

```python
"""Agent 数据飞轮样本聚合、标注和用例草稿服务。"""

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.infra.agent_events import read_event_segment
from app.models.agent_turn import AgentTurn
from app.models.conversation import ConversationMessage
from app.models.data_flywheel import AgentCaseDraft, AgentDataFlywheelLabel
from app.services.session_debug_export_service import build_session_debug_export


ALLOWED_LABELS = {
    "good_reply",
    "bad_reply",
    "wrong_tool_selection",
    "pending_missed",
    "hallucinated_execution",
    "missing_wage",
    "disabled_worker_used",
    "needs_regression",
    "not_actionable",
}

SAMPLE_TYPE_SESSION_TURN = "session_turn"


def _sample_id(turn: AgentTurn) -> str:
    return f"turn:{turn.farm_id}:{turn.session_id}:{turn.id}"


def _parse_sample_id(sample_id: str) -> tuple[int, str, int]:
    parts = sample_id.split(":")
    if len(parts) != 4 or parts[0] != "turn":
        raise ValueError("INVALID_SAMPLE_ID")
    return int(parts[1]), parts[2], int(parts[3])


def _events_for_turn(turn: AgentTurn) -> list[dict[str, Any]]:
    if not turn.event_file:
        return []
    return read_event_segment(turn.event_file, turn.event_seq_start, turn.event_seq_end)


def _labels_by_sample(
    db: Session,
    *,
    farm_id: int,
    sample_ids: list[str],
) -> dict[str, list[AgentDataFlywheelLabel]]:
    if not sample_ids:
        return {}
    rows = (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_id.in_(sample_ids),
        )
        .order_by(AgentDataFlywheelLabel.created_at.asc())
        .all()
    )
    grouped: dict[str, list[AgentDataFlywheelLabel]] = {}
    for row in rows:
        grouped.setdefault(row.sample_id, []).append(row)
    return grouped


def _message_content(db: Session, message_id: int | None) -> str:
    if message_id is None:
        return ""
    message = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.id == message_id)
        .first()
    )
    return message.content if message else ""


def _router_decision(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in events:
        if event.get("event_type") == "router.decision":
            payload = event.get("payload") or {}
            return payload if isinstance(payload, dict) else {}
    return {}


def _selected_tools(events: list[dict[str, Any]]) -> list[str]:
    payload = _router_decision(events)
    tools = payload.get("selected_tools") or []
    return [str(tool) for tool in tools]


def _actual_tools(events: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for event in events:
        if event.get("event_type") not in {"tool.call.finished", "tool.call.failed"}:
            continue
        tool_name = (event.get("payload") or {}).get("tool_name")
        if tool_name:
            tools.append(str(tool_name))
    return tools


def _tool_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if str(event.get("event_type", "")).startswith("tool.call.")
    ]


def _pending_lifecycle(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if str(event.get("event_type", "")).startswith("pending.")
    ]
```

- [ ] **Step 4: Add sample listing and labeling functions**

Append to `backend/app/services/data_flywheel_service.py`:

```python
def list_samples(
    db: Session,
    *,
    farm_id: int,
    sample_type: str | None = None,
    label: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    unannotated_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """返回 turn 级轻量样本列表。"""
    query = db.query(AgentTurn).filter(AgentTurn.farm_id == farm_id)
    if sample_type and sample_type != SAMPLE_TYPE_SESSION_TURN:
        return {"items": [], "total": 0}
    if session_id:
        query = query.filter(AgentTurn.session_id == session_id)
    if request_id:
        query = query.filter(AgentTurn.request_id == request_id)
    if label:
        label_turn_ids = (
            db.query(AgentDataFlywheelLabel.turn_id)
            .filter(
                AgentDataFlywheelLabel.farm_id == farm_id,
                AgentDataFlywheelLabel.label == label,
                AgentDataFlywheelLabel.turn_id.isnot(None),
            )
        )
        query = query.filter(AgentTurn.id.in_(label_turn_ids))
    if unannotated_only:
        annotated_turn_ids = (
            db.query(AgentDataFlywheelLabel.turn_id)
            .filter(
                AgentDataFlywheelLabel.farm_id == farm_id,
                AgentDataFlywheelLabel.turn_id.isnot(None),
            )
        )
        query = query.filter(~AgentTurn.id.in_(annotated_turn_ids))

    total = query.count()
    page_turns = (
        query.order_by(AgentTurn.created_at.desc(), AgentTurn.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    sample_ids = [_sample_id(turn) for turn in page_turns]
    labels_map = _labels_by_sample(db, farm_id=farm_id, sample_ids=sample_ids)

    rows: list[dict[str, Any]] = []
    for turn in page_turns:
        sid = _sample_id(turn)
        labels = labels_map.get(sid, [])
        label_names = [row.label for row in labels]
        # Only read the current page's event segments. The list query never scans
        # every JSONL file that matches the filters.
        events = _events_for_turn(turn)
        rows.append(
            {
                "sample_id": sid,
                "sample_type": SAMPLE_TYPE_SESSION_TURN,
                "quality_labels": label_names,
                "annotation_status": "labeled" if label_names else "unlabeled",
                "session_id": turn.session_id,
                "turn_id": turn.id,
                "request_id": turn.request_id,
                "user_input_preview": turn.input_preview or "",
                "assistant_reply_preview": turn.reply_preview or "",
                "selected_tools": _selected_tools(events),
                "actual_tools": _actual_tools(events),
                "token_total": turn.token_total,
                "latency_ms": turn.latency_ms,
                "source_type": "agent_event_log" if turn.event_file else "agent_turns",
                "created_at": turn.created_at.isoformat() if turn.created_at else None,
            }
        )

    return {"items": rows, "total": total}


def add_sample_label(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    sample_type: str,
    session_id: str | None,
    turn_id: int | None,
    request_id: str | None,
    label: str,
    comment: str | None,
    annotator_id: str | None,
) -> dict[str, Any]:
    """保存一个样本标注。"""
    if label not in ALLOWED_LABELS:
        raise ValueError("INVALID_LABEL")
    if sample_type == SAMPLE_TYPE_SESSION_TURN and (turn_id is None or session_id is None):
        parsed_farm_id, parsed_session_id, parsed_turn_id = _parse_sample_id(sample_id)
        if parsed_farm_id != farm_id:
            raise ValueError("SAMPLE_NOT_FOUND")
        session_id = session_id or parsed_session_id
        turn_id = turn_id or parsed_turn_id
        if request_id is None:
            turn = (
                db.query(AgentTurn)
                .filter(AgentTurn.farm_id == farm_id, AgentTurn.id == parsed_turn_id)
                .first()
            )
            request_id = turn.request_id if turn else None
    row = AgentDataFlywheelLabel(
        farm_id=farm_id,
        sample_id=sample_id,
        sample_type=sample_type,
        session_id=session_id,
        turn_id=turn_id,
        request_id=request_id,
        label=label,
        comment=comment,
        annotator_id=annotator_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _label_to_dict(row)


def _label_to_dict(row: AgentDataFlywheelLabel) -> dict[str, Any]:
    return {
        "id": row.id,
        "sample_id": row.sample_id,
        "sample_type": row.sample_type,
        "session_id": row.session_id,
        "turn_id": row.turn_id,
        "request_id": row.request_id,
        "label": row.label,
        "comment": row.comment,
        "annotator_id": row.annotator_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
```

- [ ] **Step 5: Add detail, export, and case draft functions**

Append to `backend/app/services/data_flywheel_service.py`:

```python
def get_sample_detail(db: Session, *, farm_id: int, sample_id: str) -> dict[str, Any]:
    """返回单条样本的完整证据。"""
    parsed_farm_id, _session_id, turn_id = _parse_sample_id(sample_id)
    if parsed_farm_id != farm_id:
        raise ValueError("SAMPLE_NOT_FOUND")
    turn = (
        db.query(AgentTurn)
        .filter(AgentTurn.farm_id == farm_id, AgentTurn.id == turn_id)
        .first()
    )
    if turn is None:
        raise ValueError("SAMPLE_NOT_FOUND")

    list_result = list_samples(
        db,
        farm_id=farm_id,
        session_id=turn.session_id,
        request_id=turn.request_id,
        limit=100,
    )
    sample = next(
        item for item in list_result["items"] if item["sample_id"] == sample_id
    )
    events = _events_for_turn(turn)
    labels = _labels_by_sample(db, farm_id=farm_id, sample_ids=[sample_id]).get(
        sample_id,
        [],
    )
    debug_export = build_session_debug_export(
        db,
        farm_id=farm_id,
        session_id=turn.session_id,
    )
    return {
        "sample": sample,
        "labels": [_label_to_dict(label) for label in labels],
        "messages": [
            {
                "role": "user",
                "content": _message_content(db, turn.user_message_id),
            },
            {
                "role": "assistant",
                "content": _message_content(db, turn.assistant_message_id),
            },
        ],
        "turn": {
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
        },
        "router_decision": _router_decision(events),
        "tool_events": _tool_events(events),
        "pending_lifecycle": _pending_lifecycle(events),
        "debug_export": debug_export,
        "source": {
            "event_file": turn.event_file,
            "event_seq_start": turn.event_seq_start,
            "event_seq_end": turn.event_seq_end,
            "missing_event_segments": debug_export.get("missing_event_segments", []),
        },
    }


def export_sample_jsonl(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
) -> dict[str, str]:
    """导出单条样本 JSONL 内容。"""
    detail = get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
    sample = detail["sample"]
    row = {
        "sample_id": sample_id,
        "sample_type": sample["sample_type"],
        "quality_labels": sample["quality_labels"],
        "session_id": sample["session_id"],
        "turn_id": sample["turn_id"],
        "request_id": sample["request_id"],
        "user_input": detail["messages"][0]["content"],
        "assistant_reply": detail["messages"][1]["content"],
        "selected_tools": sample["selected_tools"],
        "actual_tools": sample["actual_tools"],
        "router_decision": detail["router_decision"],
        "tool_events": detail["tool_events"],
        "pending_lifecycle": detail["pending_lifecycle"],
        "source": detail["source"],
    }
    filename = f"data-flywheel-sample-{datetime.now().strftime('%Y%m%d%H%M%S')}.jsonl"
    return {
        "filename": filename,
        "content": json.dumps(row, ensure_ascii=False, separators=(",", ": "))
        + "\n",
    }


def build_case_draft(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    target_type: str,
    created_by: str | None,
) -> dict[str, Any]:
    """根据样本生成 regression case 草稿。"""
    if target_type not in {"simulation", "evaluation_replay"}:
        raise ValueError("INVALID_TARGET_TYPE")
    detail = get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
    sample = detail["sample"]
    selected_tools = sample["selected_tools"]
    labels = sample["quality_labels"]
    case_id = f"regression-{sample['session_id']}-{sample['turn_id']}"
    case_json = {
        "case_id": case_id,
        "description": _draft_description(labels),
        "user_input": detail["messages"][0]["content"],
        "category": _draft_category(labels),
        "expected_skills": [{"name": tool} for tool in selected_tools],
        "expected_pending_action": None,
        "confirmation_flow": [],
        "expected_database_diff": [],
        "reply_assertions": _reply_assertions(labels),
        "metadata": {
            "source": "data_flywheel",
            "source_sample_id": sample_id,
            "source_session_id": sample["session_id"],
            "source_request_id": sample["request_id"],
            "quality_labels": labels,
        },
    }
    if "pending_missed" in labels or detail["pending_lifecycle"]:
        pending_tool = selected_tools[0] if selected_tools else ""
        case_json["expected_pending_action"] = {
            "skill_name": pending_tool,
            "params": {},
            "status": "created",
            "confirmation_required": True,
        }
    draft = AgentCaseDraft(
        farm_id=farm_id,
        draft_id=f"draft-{uuid.uuid4().hex[:12]}",
        source_sample_id=sample_id,
        target_type=target_type,
        status="draft",
        case_json=case_json,
        created_by=created_by,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_to_dict(draft)


def _draft_description(labels: list[str]) -> str:
    if "missing_wage" in labels:
        return "工资缺失回归样本"
    if "wrong_tool_selection" in labels:
        return "工具选择错误回归样本"
    if "pending_missed" in labels:
        return "pending 漏拦截回归样本"
    return "Agent 数据飞轮回归样本"


def _draft_category(labels: list[str]) -> str:
    if "hallucinated_execution" in labels:
        return "hallucination"
    if "pending_missed" in labels:
        return "pending"
    if "wrong_tool_selection" in labels:
        return "tool_selection"
    return "regression"


def _reply_assertions(labels: list[str]) -> list[dict[str, Any]]:
    if "missing_wage" in labels:
        return [{"contains": "100"}]
    if "hallucinated_execution" in labels:
        return [{"not_contains": "已执行"}]
    return []


def _draft_to_dict(draft: AgentCaseDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "draft_id": draft.draft_id,
        "source_sample_id": draft.source_sample_id,
        "target_type": draft.target_type,
        "status": draft.status,
        "case_json": draft.case_json,
        "created_by": draft.created_by,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }
```

- [ ] **Step 6: Run service tests**

Run:

```bash
cd backend && poetry run pytest tests/services/test_data_flywheel_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Run formatting and lint for service files**

Run:

```bash
cd backend && poetry run ruff format app/services/data_flywheel_service.py tests/services/test_data_flywheel_service.py && poetry run ruff check app/services/data_flywheel_service.py tests/services/test_data_flywheel_service.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/data_flywheel_service.py backend/tests/services/test_data_flywheel_service.py
git commit -m "feat: add agent data flywheel service"
```

---

### Task 3: Expose Admin Data Flywheel API

**Files:**
- Create: `backend/app/api/admin_data_flywheel.py`
- Modify: `backend/app/bootstrap/routes.py`
- Test: `backend/tests/api/test_admin_data_flywheel.py`

- [ ] **Step 1: Write the failing API tests**

Create `backend/tests/api/test_admin_data_flywheel.py`:

```python
"""Admin Data Flywheel API 测试。"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.admin_data_flywheel import router
from app.api.deps import get_current_farm, get_current_user, get_db
from app.core.database import Base
from app.infra.agent_events import AgentEventWriter
from app.infra.limiter import limiter
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.models.farm import Farm
from app.models.user import User


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_admin_data_flywheel_api.db",
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
            id="admin-1",
            phone="18800000002",
            password_hash="h",
            nickname="管理员",
            role="admin",
            status="active",
        )
    )
    db.add(Farm(id=1, name="默认农场", user_id="admin-1"))
    db.commit()
    db.close()


def _seed_turn(tmp_path):
    db = Session()
    conv = Conversation(farm_id=1, user_id="admin-1", session_id="sess-api")
    db.add(conv)
    db.commit()
    user_msg = ConversationMessage(
        conversation_id=conv.id,
        turn_id=1,
        role="user",
        content="查一下水稻",
    )
    assistant_msg = ConversationMessage(
        conversation_id=conv.id,
        turn_id=1,
        role="assistant",
        content="当前有水稻",
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()
    writer = AgentEventWriter(base_dir=tmp_path)
    first = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="admin-1",
        session_id="sess-api",
        turn_id=1,
        request_id="req12345",
        payload={"content": "查一下水稻"},
    )
    second = writer.write(
        event_type="router.decision",
        farm_id=1,
        user_id="admin-1",
        session_id="sess-api",
        turn_id=1,
        request_id="req12345",
        payload={"selected_tools": ["get_farm_status"]},
    )
    turn = AgentTurn(
        farm_id=1,
        session_id="sess-api",
        conversation_id=conv.id,
        request_id="req12345",
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        input_preview="查一下水稻",
        reply_preview="当前有水稻",
        selected_tools_count=1,
        tool_calls_count=0,
        token_total=320,
        latency_ms=900,
        status="success",
        event_file=first.event_file,
        event_seq_start=first.seq,
        event_seq_end=second.seq,
        event_write_status="success",
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    sample_id = f"turn:1:sess-api:{turn.id}"
    db.close()
    return sample_id


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
            id="admin-1",
            phone="18800000002",
            password_hash="h",
            nickname="管理员",
            role="admin",
            status="active",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


def test_list_samples(tmp_path):
    _seed_turn(tmp_path)
    client = _client()

    response = client.get("/admin/data-flywheel/samples")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["request_id"] == "req12345"


def test_get_detail_and_add_label(tmp_path):
    sample_id = _seed_turn(tmp_path)
    client = _client()

    label_response = client.post(
        f"/admin/data-flywheel/samples/{sample_id}/labels",
        json={"label": "good_reply", "comment": "回答准确"},
    )

    assert label_response.status_code == 200
    assert label_response.json()["label"] == "good_reply"

    detail_response = client.get(f"/admin/data-flywheel/samples/{sample_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["sample"]["quality_labels"] == ["good_reply"]
    assert detail["router_decision"]["selected_tools"] == ["get_farm_status"]


def test_export_jsonl_and_create_case_draft(tmp_path):
    sample_id = _seed_turn(tmp_path)
    client = _client()

    export_response = client.post(
        "/admin/data-flywheel/export-jsonl",
        json={"sample_id": sample_id},
    )
    assert export_response.status_code == 200
    assert export_response.json()["content"].endswith("\n")

    draft_response = client.post(
        f"/admin/data-flywheel/samples/{sample_id}/case-draft",
        json={"target_type": "evaluation_replay"},
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()
    assert draft["status"] == "draft"
    assert draft["case_json"]["metadata"]["source_sample_id"] == sample_id
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_data_flywheel.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.admin_data_flywheel'`.

- [ ] **Step 3: Create the API router**

Create `backend/app/api/admin_data_flywheel.py`:

```python
"""Admin Data Flywheel API。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_current_user, get_db, require_admin
from app.models.farm import Farm
from app.models.user import User
from app.services.data_flywheel_service import (
    add_sample_label,
    build_case_draft,
    export_sample_jsonl,
    get_sample_detail,
    list_samples,
)


router = APIRouter(
    prefix="/admin/data-flywheel",
    tags=["admin-data-flywheel"],
    dependencies=[Depends(require_admin)],
)


class AddLabelRequest(BaseModel):
    label: str
    comment: str | None = None
    sample_type: str = "session_turn"
    session_id: str | None = None
    turn_id: int | None = None
    request_id: str | None = None


class ExportJsonlRequest(BaseModel):
    sample_id: str


class CaseDraftRequest(BaseModel):
    target_type: str = "evaluation_replay"


@router.get("/samples")
def list_data_flywheel_samples(
    sample_type: str | None = Query(None),
    label: str | None = Query(None),
    session_id: str | None = Query(None),
    request_id: str | None = Query(None),
    unannotated_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """查询 Data Flywheel 样本列表。"""
    return list_samples(
        db,
        farm_id=farm.id,
        sample_type=sample_type,
        label=label,
        session_id=session_id,
        request_id=request_id,
        unannotated_only=unannotated_only,
        limit=limit,
        offset=offset,
    )


@router.get("/samples/{sample_id}")
def get_data_flywheel_sample_detail(
    sample_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取单条样本详情。"""
    try:
        return get_sample_detail(db, farm_id=farm.id, sample_id=sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": str(exc)})


@router.post("/samples/{sample_id}/labels")
def add_data_flywheel_label(
    sample_id: str,
    body: AddLabelRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """给样本添加质量标签。"""
    try:
        return add_sample_label(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            sample_type=body.sample_type,
            session_id=body.session_id,
            turn_id=body.turn_id,
            request_id=body.request_id,
            label=body.label,
            comment=body.comment,
            annotator_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": str(exc)})


@router.post("/samples/{sample_id}/bad-case")
def mark_data_flywheel_bad_case(
    sample_id: str,
    body: AddLabelRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """快捷标记坏例。"""
    label = body.label if body.label != "good_reply" else "bad_reply"
    return add_sample_label(
        db,
        farm_id=farm.id,
        sample_id=sample_id,
        sample_type=body.sample_type,
        session_id=body.session_id,
        turn_id=body.turn_id,
        request_id=body.request_id,
        label=label or "bad_reply",
        comment=body.comment,
        annotator_id=current_user.id,
    )


@router.post("/export-jsonl")
def export_data_flywheel_jsonl(
    body: ExportJsonlRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, str]:
    """导出单条样本 JSONL。"""
    try:
        return export_sample_jsonl(db, farm_id=farm.id, sample_id=body.sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": str(exc)})


@router.post("/samples/{sample_id}/case-draft")
def create_data_flywheel_case_draft(
    sample_id: str,
    body: CaseDraftRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """生成 regression case 草稿。"""
    try:
        return build_case_draft(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            target_type=body.target_type,
            created_by=current_user.id,
        )
    except ValueError as exc:
        status_code = 400 if str(exc) == "INVALID_TARGET_TYPE" else 404
        raise HTTPException(status_code=status_code, detail={"code": str(exc)})
```

- [ ] **Step 4: Register the router in `backend/app/bootstrap/routes.py`**

Modify imports at the top of `backend/app/bootstrap/routes.py` to include `admin_data_flywheel`:

```python
from app.api import (
    admin,
    admin_config,
    admin_data_flywheel,
    admin_stats,
    admin_trace,
    admin_users,
    agent,
    app_version,
    auth,
    cost,
    cost_categories,
    crop,
    cycle,
    debt,
    feedback,
    log,
    planting,
    smart_fill,
    user_settings,
    weather,
)
```

Add this registration after `admin_trace.router`:

```python
    app.include_router(admin_data_flywheel.router)
```

- [ ] **Step 5: Run API tests**

Run:

```bash
cd backend && poetry run pytest tests/api/test_admin_data_flywheel.py -v
```

Expected: PASS.

- [ ] **Step 6: Run focused backend regression tests**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_data_flywheel_models.py tests/services/test_data_flywheel_service.py tests/api/test_admin_data_flywheel.py tests/api/test_admin_trace.py tests/api/test_agent_debug_export.py -v
```

Expected: PASS.

- [ ] **Step 7: Run formatting and lint for API files**

Run:

```bash
cd backend && poetry run ruff format app/api/admin_data_flywheel.py app/bootstrap/routes.py tests/api/test_admin_data_flywheel.py && poetry run ruff check app/api/admin_data_flywheel.py app/bootstrap/routes.py tests/api/test_admin_data_flywheel.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/admin_data_flywheel.py backend/app/bootstrap/routes.py backend/tests/api/test_admin_data_flywheel.py
git commit -m "feat: expose agent data flywheel admin api"
```

---

### Task 4: Add Frontend API Client

**Files:**
- Create: `admin-web/src/api/dataFlywheel.ts`
- Test: `admin-web/src/api/dataFlywheel.test.ts`

- [ ] **Step 1: Write failing frontend API tests**

Create `admin-web/src/api/dataFlywheel.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest';
import apiClient from './client';
import {
  addSampleLabel,
  createCaseDraft,
  exportSampleJsonl,
  getSampleDetail,
  listDataFlywheelSamples,
} from './dataFlywheel';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedClient = vi.mocked(apiClient, true);

describe('dataFlywheel api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('listDataFlywheelSamples 调用列表接口并传递筛选参数', async () => {
    mockedClient.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });

    const result = await listDataFlywheelSamples({
      label: 'wrong_tool_selection',
      unannotated_only: true,
      limit: 20,
      offset: 0,
    });

    expect(result).toEqual({ items: [], total: 0 });
    expect(mockedClient.get).toHaveBeenCalledWith('/admin/data-flywheel/samples', {
      params: {
        label: 'wrong_tool_selection',
        unannotated_only: true,
        limit: 20,
        offset: 0,
      },
    });
  });

  it('getSampleDetail 调用样本详情接口', async () => {
    mockedClient.get.mockResolvedValueOnce({ data: { sample: { sample_id: 'turn:1:s:1' } } });

    const result = await getSampleDetail('turn:1:s:1');

    expect(result.sample.sample_id).toBe('turn:1:s:1');
    expect(mockedClient.get).toHaveBeenCalledWith('/admin/data-flywheel/samples/turn%3A1%3As%3A1');
  });

  it('addSampleLabel 提交标注', async () => {
    mockedClient.post.mockResolvedValueOnce({ data: { label: 'good_reply' } });

    const result = await addSampleLabel('turn:1:s:1', {
      label: 'good_reply',
      comment: '准确',
      session_id: 's',
      turn_id: 1,
      request_id: 'req',
    });

    expect(result.label).toBe('good_reply');
    expect(mockedClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/samples/turn%3A1%3As%3A1/labels',
      {
        label: 'good_reply',
        comment: '准确',
        session_id: 's',
        turn_id: 1,
        request_id: 'req',
      }
    );
  });

  it('exportSampleJsonl 提交导出请求', async () => {
    mockedClient.post.mockResolvedValueOnce({ data: { filename: 'a.jsonl', content: '{}\n' } });

    const result = await exportSampleJsonl('turn:1:s:1');

    expect(result.filename).toBe('a.jsonl');
    expect(mockedClient.post).toHaveBeenCalledWith('/admin/data-flywheel/export-jsonl', {
      sample_id: 'turn:1:s:1',
    });
  });

  it('createCaseDraft 提交草稿请求', async () => {
    mockedClient.post.mockResolvedValueOnce({ data: { draft_id: 'draft-1' } });

    const result = await createCaseDraft('turn:1:s:1', 'evaluation_replay');

    expect(result.draft_id).toBe('draft-1');
    expect(mockedClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/samples/turn%3A1%3As%3A1/case-draft',
      { target_type: 'evaluation_replay' }
    );
  });
});
```

- [ ] **Step 2: Run frontend API tests to verify they fail**

Run:

```bash
cd admin-web && pnpm exec vitest run src/api/dataFlywheel.test.ts
```

Expected: FAIL because `src/api/dataFlywheel.ts` does not exist.

- [ ] **Step 3: Create frontend API module**

Create `admin-web/src/api/dataFlywheel.ts`:

```typescript
import apiClient from './client';

export type DataFlywheelLabel =
  | 'good_reply'
  | 'bad_reply'
  | 'wrong_tool_selection'
  | 'pending_missed'
  | 'hallucinated_execution'
  | 'missing_wage'
  | 'disabled_worker_used'
  | 'needs_regression'
  | 'not_actionable';

export interface DataFlywheelSample {
  sample_id: string;
  sample_type: string;
  quality_labels: DataFlywheelLabel[];
  annotation_status: 'labeled' | 'unlabeled';
  session_id: string;
  turn_id: number;
  request_id: string;
  user_input_preview: string;
  assistant_reply_preview: string;
  selected_tools: string[];
  actual_tools: string[];
  token_total: number | null;
  latency_ms: number | null;
  source_type: string;
  created_at: string | null;
}

export interface ListDataFlywheelSamplesParams {
  sample_type?: string;
  label?: DataFlywheelLabel;
  session_id?: string;
  request_id?: string;
  unannotated_only?: boolean;
  limit?: number;
  offset?: number;
}

export interface ListDataFlywheelSamplesResponse {
  items: DataFlywheelSample[];
  total: number;
}

export interface DataFlywheelLabelRecord {
  id: number;
  sample_id: string;
  sample_type: string;
  session_id: string | null;
  turn_id: number | null;
  request_id: string | null;
  label: DataFlywheelLabel;
  comment: string | null;
  annotator_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DataFlywheelDetail {
  sample: DataFlywheelSample;
  labels: DataFlywheelLabelRecord[];
  messages: Array<{ role: string; content: string }>;
  turn: Record<string, unknown>;
  router_decision: Record<string, unknown>;
  tool_events: Array<Record<string, unknown>>;
  pending_lifecycle: Array<Record<string, unknown>>;
  debug_export: Record<string, unknown>;
  source: {
    event_file: string | null;
    event_seq_start: number | null;
    event_seq_end: number | null;
    missing_event_segments: Array<Record<string, unknown>>;
  };
}

export interface AddSampleLabelRequest {
  label: DataFlywheelLabel;
  comment?: string;
  sample_type?: string;
  session_id?: string;
  turn_id?: number;
  request_id?: string;
}

export interface ExportJsonlResponse {
  filename: string;
  content: string;
}

export interface CaseDraft {
  id: number;
  draft_id: string;
  source_sample_id: string;
  target_type: string;
  status: string;
  case_json: Record<string, unknown>;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export async function listDataFlywheelSamples(
  params: ListDataFlywheelSamplesParams = {}
): Promise<ListDataFlywheelSamplesResponse> {
  const res = await apiClient.get<ListDataFlywheelSamplesResponse>('/admin/data-flywheel/samples', { params });
  return res.data;
}

export async function getSampleDetail(sampleId: string): Promise<DataFlywheelDetail> {
  const res = await apiClient.get<DataFlywheelDetail>(`/admin/data-flywheel/samples/${encodeURIComponent(sampleId)}`);
  return res.data;
}

export async function addSampleLabel(
  sampleId: string,
  body: AddSampleLabelRequest
): Promise<DataFlywheelLabelRecord> {
  const res = await apiClient.post<DataFlywheelLabelRecord>(
    `/admin/data-flywheel/samples/${encodeURIComponent(sampleId)}/labels`,
    body
  );
  return res.data;
}

export async function markBadCase(
  sampleId: string,
  body: AddSampleLabelRequest
): Promise<DataFlywheelLabelRecord> {
  const res = await apiClient.post<DataFlywheelLabelRecord>(
    `/admin/data-flywheel/samples/${encodeURIComponent(sampleId)}/bad-case`,
    body
  );
  return res.data;
}

export async function exportSampleJsonl(sampleId: string): Promise<ExportJsonlResponse> {
  const res = await apiClient.post<ExportJsonlResponse>('/admin/data-flywheel/export-jsonl', {
    sample_id: sampleId,
  });
  return res.data;
}

export async function createCaseDraft(
  sampleId: string,
  targetType: 'simulation' | 'evaluation_replay'
): Promise<CaseDraft> {
  const res = await apiClient.post<CaseDraft>(
    `/admin/data-flywheel/samples/${encodeURIComponent(sampleId)}/case-draft`,
    { target_type: targetType }
  );
  return res.data;
}
```

- [ ] **Step 4: Run frontend API tests**

Run:

```bash
cd admin-web && pnpm exec vitest run src/api/dataFlywheel.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run frontend lint for API files**

Run:

```bash
cd admin-web && pnpm exec eslint src/api/dataFlywheel.ts src/api/dataFlywheel.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add admin-web/src/api/dataFlywheel.ts admin-web/src/api/dataFlywheel.test.ts
git commit -m "feat: add data flywheel frontend api"
```

---

### Task 5: Build Data Flywheel Page Components

**Files:**
- Create: `admin-web/src/pages/DataFlywheel/components/SampleQueueTable.tsx`
- Create: `admin-web/src/pages/DataFlywheel/components/ToolComparison.tsx`
- Create: `admin-web/src/pages/DataFlywheel/components/PendingLifecycleView.tsx`
- Create: `admin-web/src/pages/DataFlywheel/components/SampleDetailPanel.tsx`
- Create: `admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx`
- Create: `admin-web/src/pages/DataFlywheel/components/CaseDraftPreview.tsx`
- Create: `admin-web/src/pages/DataFlywheel/index.tsx`
- Test: `admin-web/src/pages/DataFlywheel/index.test.tsx`

- [ ] **Step 1: Write the failing page tests**

Create `admin-web/src/pages/DataFlywheel/index.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DataFlywheel from './index';
import * as api from '../../api/dataFlywheel';

vi.mock('../../api/dataFlywheel', () => ({
  listDataFlywheelSamples: vi.fn(),
  getSampleDetail: vi.fn(),
  addSampleLabel: vi.fn(),
  exportSampleJsonl: vi.fn(),
  createCaseDraft: vi.fn(),
}));

const mockedApi = vi.mocked(api, true);

const sample = {
  sample_id: 'turn:1:sess-1:12',
  sample_type: 'session_turn',
  quality_labels: [],
  annotation_status: 'unlabeled' as const,
  session_id: 'sess-1',
  turn_id: 12,
  request_id: 'abcd1234',
  user_input_preview: '王大妈工资100一天，去5号棚收水稻',
  assistant_reply_preview: '已安排王大妈去5号棚收水稻',
  selected_tools: ['manage_workers', 'create_operation_work_order'],
  actual_tools: ['manage_workers'],
  token_total: 680,
  latency_ms: 1320,
  source_type: 'agent_event_log',
  created_at: '2026-06-11T10:00:00+08:00',
};

const detail = {
  sample,
  labels: [],
  messages: [
    { role: 'user', content: '王大妈工资100一天，去5号棚收水稻' },
    { role: 'assistant', content: '已安排王大妈去5号棚收水稻' },
  ],
  turn: { status: 'success' },
  router_decision: { selected_tools: sample.selected_tools },
  tool_events: [{ event_type: 'tool.call.finished', payload: { tool_name: 'manage_workers' } }],
  pending_lifecycle: [{ event_type: 'pending.plan.created', payload: { plan_id: 'plan-1' } }],
  debug_export: { format: 'farm-manager.chat-session-debug.v2' },
  source: {
    event_file: 'data/agent-events/dt=2026-06-11/farm_id=1/session_id=sess-1/events.jsonl',
    event_seq_start: 1,
    event_seq_end: 5,
    missing_event_segments: [],
  },
};

describe('DataFlywheel Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    mockedApi.listDataFlywheelSamples.mockResolvedValue({ items: [sample], total: 1 });
    mockedApi.getSampleDetail.mockResolvedValue(detail);
  });

  it('渲染样本队列和核心字段', async () => {
    render(<DataFlywheel />);

    await waitFor(() => {
      expect(screen.getByText('Agent 数据飞轮')).toBeInTheDocument();
    });
    expect(screen.getByText('王大妈工资100一天，去5号棚收水稻')).toBeInTheDocument();
    expect(screen.getByText('abcd1234')).toBeInTheDocument();
    expect(screen.getByText('680 tokens')).toBeInTheDocument();
  });

  it('点击样本后加载详情', async () => {
    render(<DataFlywheel />);

    await waitFor(() => {
      expect(screen.getByText('王大妈工资100一天，去5号棚收水稻')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('王大妈工资100一天，去5号棚收水稻'));

    await waitFor(() => {
      expect(mockedApi.getSampleDetail).toHaveBeenCalledWith('turn:1:sess-1:12');
    });
    expect(screen.getByText('样本详情')).toBeInTheDocument();
    expect(screen.getByText('selected_tools')).toBeInTheDocument();
    expect(screen.getByText('pending.plan.created')).toBeInTheDocument();
  });

  it('可以保存标签', async () => {
    mockedApi.addSampleLabel.mockResolvedValue({
      id: 1,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: 'sess-1',
      turn_id: 12,
      request_id: 'abcd1234',
      label: 'missing_wage',
      comment: '回复没有提工资',
      annotator_id: 'admin-1',
      created_at: '2026-06-11T10:00:00+08:00',
      updated_at: '2026-06-11T10:00:00+08:00',
    });
    render(<DataFlywheel />);

    await waitFor(() => {
      expect(screen.getByText('王大妈工资100一天，去5号棚收水稻')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('王大妈工资100一天，去5号棚收水稻'));
    await waitFor(() => {
      expect(screen.getByText('工资缺失')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('工资缺失'));
    fireEvent.change(screen.getByPlaceholderText('标注备注'), {
      target: { value: '回复没有提工资' },
    });
    fireEvent.click(screen.getByText('保存标注'));

    await waitFor(() => {
      expect(mockedApi.addSampleLabel).toHaveBeenCalledWith(sample.sample_id, {
        label: 'missing_wage',
        comment: '回复没有提工资',
        sample_type: sample.sample_type,
        session_id: sample.session_id,
        turn_id: sample.turn_id,
        request_id: sample.request_id,
      });
    });
  });

  it('可以生成 case draft 并展示预览', async () => {
    mockedApi.createCaseDraft.mockResolvedValue({
      id: 1,
      draft_id: 'draft-1',
      source_sample_id: sample.sample_id,
      target_type: 'evaluation_replay',
      status: 'draft',
      case_json: { case_id: 'regression-sess-1-12', user_input: sample.user_input_preview },
      created_by: 'admin-1',
      created_at: '2026-06-11T10:00:00+08:00',
      updated_at: '2026-06-11T10:00:00+08:00',
    });
    render(<DataFlywheel />);

    await waitFor(() => {
      expect(screen.getByText('王大妈工资100一天，去5号棚收水稻')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('王大妈工资100一天，去5号棚收水稻'));
    await waitFor(() => {
      expect(screen.getByText('生成 regression case')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('生成 regression case'));

    await waitFor(() => {
      expect(screen.getByText('Case Draft')).toBeInTheDocument();
    });
    expect(screen.getByText(/regression-sess-1-12/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run page tests to verify they fail**

Run:

```bash
cd admin-web && pnpm exec vitest run src/pages/DataFlywheel/index.test.tsx
```

Expected: FAIL because the page and components do not exist.

- [ ] **Step 3: Create `ToolComparison`**

Create `admin-web/src/pages/DataFlywheel/components/ToolComparison.tsx`:

```tsx
import { Space, Tag, Typography } from 'antd';
import { palette } from '../../../styles/theme';

const { Text } = Typography;

interface ToolComparisonProps {
  selectedTools: string[];
  actualTools: string[];
}

export default function ToolComparison({ selectedTools, actualTools }: ToolComparisonProps) {
  return (
    <div>
      <Text style={{ color: palette.textMuted, fontSize: 12 }}>selected_tools</Text>
      <Space wrap style={{ display: 'flex', marginTop: 6, marginBottom: 10 }}>
        {selectedTools.length > 0 ? selectedTools.map((tool) => (
          <Tag key={tool} color={actualTools.includes(tool) ? 'blue' : 'default'}>{tool}</Tag>
        )) : <Text type="secondary">无</Text>}
      </Space>
      <Text style={{ color: palette.textMuted, fontSize: 12 }}>actual_tools</Text>
      <Space wrap style={{ display: 'flex', marginTop: 6 }}>
        {actualTools.length > 0 ? actualTools.map((tool) => (
          <Tag key={tool} color="green">{tool}</Tag>
        )) : <Text type="secondary">无</Text>}
      </Space>
    </div>
  );
}
```

- [ ] **Step 4: Create `PendingLifecycleView`**

Create `admin-web/src/pages/DataFlywheel/components/PendingLifecycleView.tsx`:

```tsx
import { Empty, Timeline, Typography } from 'antd';
import { palette } from '../../../styles/theme';

const { Text } = Typography;

interface PendingLifecycleViewProps {
  events: Array<Record<string, unknown>>;
}

export default function PendingLifecycleView({ events }: PendingLifecycleViewProps) {
  if (events.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无 pending 生命周期事件" />;
  }
  return (
    <Timeline
      items={events.map((event, index) => ({
        color: 'gold',
        children: (
          <div>
            <Text style={{ color: palette.text }}>{String(event.event_type ?? `pending-${index}`)}</Text>
            <pre style={{
              marginTop: 6,
              padding: 8,
              borderRadius: 6,
              background: palette.bg,
              border: `1px solid ${palette.border}`,
              color: palette.textMuted,
              fontSize: 12,
              whiteSpace: 'pre-wrap',
            }}>
              {JSON.stringify(event.payload ?? {}, null, 2)}
            </pre>
          </div>
        ),
      }))}
    />
  );
}
```

- [ ] **Step 5: Create `SampleQueueTable`**

Create `admin-web/src/pages/DataFlywheel/components/SampleQueueTable.tsx`:

```tsx
import { Table, Tag, Space, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { DataFlywheelSample } from '../../../api/dataFlywheel';

const { Text } = Typography;

interface SampleQueueTableProps {
  samples: DataFlywheelSample[];
  loading: boolean;
  selectedSampleId?: string | null;
  onSelect: (sample: DataFlywheelSample) => void;
}

export default function SampleQueueTable({ samples, loading, selectedSampleId, onSelect }: SampleQueueTableProps) {
  const columns: ColumnsType<DataFlywheelSample> = [
    {
      title: '标签',
      dataIndex: 'quality_labels',
      width: 150,
      render: (labels: string[], record) => (
        <Space size={4} wrap>
          {labels.length > 0 ? labels.map((label) => <Tag key={label} color="gold">{label}</Tag>) : <Tag>{record.annotation_status}</Tag>}
        </Space>
      ),
    },
    {
      title: '输入摘要',
      dataIndex: 'user_input_preview',
      render: (text: string) => <Text>{text}</Text>,
    },
    {
      title: 'Request',
      dataIndex: 'request_id',
      width: 120,
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: 'Tools',
      width: 110,
      render: (_, record) => <Text>{record.selected_tools.length}/{record.actual_tools.length}</Text>,
    },
    {
      title: '耗时 / Token',
      width: 160,
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>{record.latency_ms ?? '-'} ms</Text>
          <Text type="secondary">{record.token_total ?? '-'} tokens</Text>
        </Space>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      width: 130,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
  ];

  return (
    <Table
      rowKey="sample_id"
      size="small"
      loading={loading}
      dataSource={samples}
      columns={columns}
      pagination={false}
      rowClassName={(record) => record.sample_id === selectedSampleId ? 'ant-table-row-selected' : ''}
      onRow={(record) => ({
        onClick: () => onSelect(record),
        style: { cursor: 'pointer' },
      })}
    />
  );
}
```

- [ ] **Step 6: Create `SampleDetailPanel`**

Create `admin-web/src/pages/DataFlywheel/components/SampleDetailPanel.tsx`:

```tsx
import { Card, Col, Empty, Row, Space, Tag, Typography } from 'antd';
import type { DataFlywheelDetail } from '../../../api/dataFlywheel';
import SkillOutputFormatter from '../../../components/SkillOutputFormatter';
import { formatTracePayload, hasTracePayload } from '../../../utils/tracePayload';
import { cardStyle, palette } from '../../../styles/theme';
import PendingLifecycleView from './PendingLifecycleView';
import ToolComparison from './ToolComparison';

const { Text, Title } = Typography;

interface SampleDetailPanelProps {
  detail: DataFlywheelDetail | null;
  loading: boolean;
}

export default function SampleDetailPanel({ detail, loading }: SampleDetailPanelProps) {
  if (!detail && !loading) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择样本" />;
  }
  if (!detail) {
    return <Card loading style={cardStyle} />;
  }

  const userMessage = detail.messages.find((item) => item.role === 'user')?.content ?? '';
  const assistantMessage = detail.messages.find((item) => item.role === 'assistant')?.content ?? '';

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>样本详情</Title>
      <Row gutter={16}>
        <Col span={12}>
          <Card size="small" title="User Input" style={cardStyle}>
            <Text style={{ whiteSpace: 'pre-wrap' }}>{userMessage}</Text>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="Assistant Reply" style={cardStyle}>
            <Text style={{ whiteSpace: 'pre-wrap' }}>{assistantMessage}</Text>
          </Card>
        </Col>
      </Row>
      <Card size="small" title="Tools" style={cardStyle}>
        <ToolComparison selectedTools={detail.sample.selected_tools} actualTools={detail.sample.actual_tools} />
      </Card>
      <Card size="small" title="Router Decision" style={cardStyle}>
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: palette.textMuted }}>
          {JSON.stringify(detail.router_decision, null, 2)}
        </pre>
      </Card>
      <Card size="small" title="Tool Events" style={cardStyle}>
        {detail.tool_events.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无工具事件" /> : detail.tool_events.map((event, index) => (
          <div key={index} style={{ marginBottom: 12 }}>
            <Tag color="green">{String(event.event_type)}</Tag>
            {hasTracePayload(event.payload) ? (
              <SkillOutputFormatter outputData={event.payload} />
            ) : (
              <pre style={{ whiteSpace: 'pre-wrap', color: palette.textMuted }}>{formatTracePayload(event.payload)}</pre>
            )}
          </div>
        ))}
      </Card>
      <Card size="small" title="Pending Plan Lifecycle" style={cardStyle}>
        <PendingLifecycleView events={detail.pending_lifecycle} />
      </Card>
      <Card size="small" title="Source" style={cardStyle}>
        <Space direction="vertical" size={4}>
          <Text code>{detail.source.event_file ?? '无 event file'}</Text>
          <Text type="secondary">seq: {detail.source.event_seq_start ?? '-'} - {detail.source.event_seq_end ?? '-'}</Text>
        </Space>
      </Card>
    </Space>
  );
}
```

- [ ] **Step 7: Create `AnnotationPanel`**

Create `admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx`:

```tsx
import { Button, Card, Input, Radio, Space, Typography } from 'antd';
import type { DataFlywheelLabel, DataFlywheelSample } from '../../../api/dataFlywheel';
import { cardStyle } from '../../../styles/theme';

const { Text } = Typography;
const { TextArea } = Input;

const LABEL_OPTIONS: Array<{ label: string; value: DataFlywheelLabel }> = [
  { label: '好回复', value: 'good_reply' },
  { label: '坏回复', value: 'bad_reply' },
  { label: '工具选错', value: 'wrong_tool_selection' },
  { label: 'pending 漏拦截', value: 'pending_missed' },
  { label: '幻觉执行', value: 'hallucinated_execution' },
  { label: '工资缺失', value: 'missing_wage' },
  { label: '禁用工人', value: 'disabled_worker_used' },
  { label: '需要回归', value: 'needs_regression' },
  { label: '暂不处理', value: 'not_actionable' },
];

interface AnnotationPanelProps {
  sample: DataFlywheelSample | null;
  selectedLabel: DataFlywheelLabel;
  comment: string;
  saving: boolean;
  onLabelChange: (label: DataFlywheelLabel) => void;
  onCommentChange: (comment: string) => void;
  onSaveLabel: () => void;
  onCopyDebug: () => void;
  onExportJsonl: () => void;
  onCreateDraft: () => void;
  onOpenTrace: () => void;
}

export default function AnnotationPanel({
  sample,
  selectedLabel,
  comment,
  saving,
  onLabelChange,
  onCommentChange,
  onSaveLabel,
  onCopyDebug,
  onExportJsonl,
  onCreateDraft,
  onOpenTrace,
}: AnnotationPanelProps) {
  return (
    <Card title="标注与动作" style={cardStyle}>
      {!sample ? (
        <Text type="secondary">请选择样本后开始标注</Text>
      ) : (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Radio.Group
            optionType="button"
            buttonStyle="solid"
            value={selectedLabel}
            options={LABEL_OPTIONS}
            onChange={(event) => onLabelChange(event.target.value)}
            style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}
          />
          <TextArea
            placeholder="标注备注"
            value={comment}
            onChange={(event) => onCommentChange(event.target.value)}
            autoSize={{ minRows: 3, maxRows: 5 }}
          />
          <Button type="primary" loading={saving} onClick={onSaveLabel} block>
            保存标注
          </Button>
          <Button onClick={onCopyDebug} block>复制 debug JSON</Button>
          <Button onClick={onExportJsonl} block>导出 JSONL</Button>
          <Button onClick={onCreateDraft} block>生成 regression case</Button>
          <Button onClick={onOpenTrace} block>跳转 TraceMonitor</Button>
        </Space>
      )}
    </Card>
  );
}
```

- [ ] **Step 8: Create `CaseDraftPreview`**

Create `admin-web/src/pages/DataFlywheel/components/CaseDraftPreview.tsx`:

```tsx
import { Modal } from 'antd';
import type { CaseDraft } from '../../../api/dataFlywheel';

interface CaseDraftPreviewProps {
  draft: CaseDraft | null;
  open: boolean;
  onClose: () => void;
}

export default function CaseDraftPreview({ draft, open, onClose }: CaseDraftPreviewProps) {
  return (
    <Modal
      title="Case Draft"
      open={open}
      onCancel={onClose}
      onOk={onClose}
      okText="知道了"
      cancelButtonProps={{ style: { display: 'none' } }}
      width={760}
    >
      <pre style={{ maxHeight: 520, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
        {draft ? JSON.stringify(draft.case_json, null, 2) : ''}
      </pre>
    </Modal>
  );
}
```

- [ ] **Step 9: Create the page shell**

Create `admin-web/src/pages/DataFlywheel/index.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card, Checkbox, Col, Input, Row, Select, Space, Typography, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import {
  addSampleLabel,
  createCaseDraft,
  exportSampleJsonl,
  getSampleDetail,
  listDataFlywheelSamples,
  type CaseDraft,
  type DataFlywheelDetail,
  type DataFlywheelLabel,
  type DataFlywheelSample,
} from '../../api/dataFlywheel';
import { cardStyle, palette } from '../../styles/theme';
import AnnotationPanel from './components/AnnotationPanel';
import CaseDraftPreview from './components/CaseDraftPreview';
import SampleDetailPanel from './components/SampleDetailPanel';
import SampleQueueTable from './components/SampleQueueTable';

const { Title, Text } = Typography;

const LABEL_OPTIONS = [
  { label: '好回复', value: 'good_reply' },
  { label: '坏回复', value: 'bad_reply' },
  { label: '工具选错', value: 'wrong_tool_selection' },
  { label: 'pending 漏拦截', value: 'pending_missed' },
  { label: '幻觉执行', value: 'hallucinated_execution' },
  { label: '工资缺失', value: 'missing_wage' },
  { label: '禁用工人', value: 'disabled_worker_used' },
  { label: '需要回归', value: 'needs_regression' },
  { label: '暂不处理', value: 'not_actionable' },
];

export default function DataFlywheel() {
  const [samples, setSamples] = useState<DataFlywheelSample[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedSample, setSelectedSample] = useState<DataFlywheelSample | null>(null);
  const [detail, setDetail] = useState<DataFlywheelDetail | null>(null);
  const [labelFilter, setLabelFilter] = useState<DataFlywheelLabel | undefined>();
  const [search, setSearch] = useState('');
  const [unannotatedOnly, setUnannotatedOnly] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState<DataFlywheelLabel>('good_reply');
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<CaseDraft | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);

  const fetchSamples = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        label: labelFilter,
        request_id: search.trim() || undefined,
        unannotated_only: unannotatedOnly,
        limit: 50,
        offset: 0,
      };
      const result = await listDataFlywheelSamples(params);
      setSamples(result.items);
      setTotal(result.total);
    } catch {
      message.error('加载样本失败');
    } finally {
      setLoading(false);
    }
  }, [labelFilter, search, unannotatedOnly]);

  useEffect(() => {
    void fetchSamples();
  }, [fetchSamples]);

  const handleSelect = useCallback(async (sample: DataFlywheelSample) => {
    setSelectedSample(sample);
    setDetailLoading(true);
    try {
      const result = await getSampleDetail(sample.sample_id);
      setDetail(result);
      setSelectedLabel(result.sample.quality_labels[0] ?? 'good_reply');
      setComment(result.labels[0]?.comment ?? '');
    } catch {
      message.error('加载样本详情失败');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const handleSaveLabel = async () => {
    if (!selectedSample) return;
    setSaving(true);
    try {
      await addSampleLabel(selectedSample.sample_id, {
        label: selectedLabel,
        comment,
        sample_type: selectedSample.sample_type,
        session_id: selectedSample.session_id,
        turn_id: selectedSample.turn_id,
        request_id: selectedSample.request_id,
      });
      message.success('标注已保存');
      await fetchSamples();
      await handleSelect(selectedSample);
    } catch {
      message.error('保存标注失败');
    } finally {
      setSaving(false);
    }
  };

  const handleCopyDebug = async () => {
    if (!detail) return;
    await navigator.clipboard.writeText(JSON.stringify(detail.debug_export, null, 2));
    message.success('已复制 debug JSON');
  };

  const handleExportJsonl = async () => {
    if (!selectedSample) return;
    const result = await exportSampleJsonl(selectedSample.sample_id);
    await navigator.clipboard.writeText(result.content);
    message.success(`已复制 ${result.filename} 内容`);
  };

  const handleCreateDraft = async () => {
    if (!selectedSample) return;
    try {
      const result = await createCaseDraft(selectedSample.sample_id, 'evaluation_replay');
      setDraft(result);
      setDraftOpen(true);
    } catch {
      message.error('生成 case draft 失败');
    }
  };

  const handleOpenTrace = () => {
    if (!selectedSample) return;
    window.location.href = `/dev/traces?request_id=${encodeURIComponent(selectedSample.request_id)}&session_id=${encodeURIComponent(selectedSample.session_id)}`;
  };

  const summary = useMemo(() => `${total} 条样本`, [total]);

  return (
    <div style={{ paddingBottom: 40 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space direction="vertical" size={2}>
            <Title level={3} style={{ margin: 0 }}>Agent 数据飞轮</Title>
            <Text style={{ color: palette.textMuted }}>真实会话与调试事件的样本标注工作台</Text>
          </Space>
        </Col>
        <Col>
          <Space>
            <Text type="secondary">{summary}</Text>
            <Button icon={<ReloadOutlined />} onClick={fetchSamples} loading={loading}>刷新</Button>
          </Space>
        </Col>
      </Row>

      <Card style={{ ...cardStyle, marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="Request ID"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            style={{ width: 220 }}
            allowClear
          />
          <Select
            placeholder="质量标签"
            allowClear
            value={labelFilter}
            onChange={setLabelFilter}
            style={{ width: 180 }}
            options={LABEL_OPTIONS}
          />
          <Checkbox checked={unannotatedOnly} onChange={(event) => setUnannotatedOnly(event.target.checked)}>
            只看未标注
          </Checkbox>
          <Button type="primary" onClick={fetchSamples}>查询</Button>
        </Space>
      </Card>

      <Row gutter={16} align="top">
        <Col xs={24} xl={10}>
          <Card title="样本队列" style={cardStyle}>
            <SampleQueueTable
              samples={samples}
              loading={loading}
              selectedSampleId={selectedSample?.sample_id}
              onSelect={handleSelect}
            />
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <SampleDetailPanel detail={detail} loading={detailLoading} />
        </Col>
        <Col xs={24} xl={5}>
          <AnnotationPanel
            sample={selectedSample}
            selectedLabel={selectedLabel}
            comment={comment}
            saving={saving}
            onLabelChange={setSelectedLabel}
            onCommentChange={setComment}
            onSaveLabel={handleSaveLabel}
            onCopyDebug={handleCopyDebug}
            onExportJsonl={handleExportJsonl}
            onCreateDraft={handleCreateDraft}
            onOpenTrace={handleOpenTrace}
          />
        </Col>
      </Row>

      <CaseDraftPreview draft={draft} open={draftOpen} onClose={() => setDraftOpen(false)} />
    </div>
  );
}
```

- [ ] **Step 10: Run page tests**

Run:

```bash
cd admin-web && pnpm exec vitest run src/pages/DataFlywheel/index.test.tsx
```

Expected: PASS.

- [ ] **Step 11: Run frontend lint for page files**

Run:

```bash
cd admin-web && pnpm exec eslint src/pages/DataFlywheel src/api/dataFlywheel.ts
```

Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add admin-web/src/pages/DataFlywheel admin-web/src/api/dataFlywheel.ts
git commit -m "feat: build agent data flywheel page"
```

---

### Task 6: Wire Data Flywheel Route and Menu

**Files:**
- Modify: `admin-web/src/App.tsx`
- Modify: `admin-web/src/layouts/AdminLayout.tsx`
- Test: extend `admin-web/src/pages/DataFlywheel/index.test.tsx` or create `admin-web/src/layouts/AdminLayout.test.tsx`

- [ ] **Step 1: Add route/menu assertions to the page test**

Add these imports at the top of `admin-web/src/pages/DataFlywheel/index.test.tsx`:

```tsx
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AdminLayout from '../../layouts/AdminLayout';
```

Append this test to the same file:

```tsx

it('菜单中展示数据飞轮入口', () => {
  render(
    <MemoryRouter initialEntries={['/dev/data-flywheel']}>
      <Routes>
        <Route path="/dev/data-flywheel" element={<AdminLayout><div>页面内容</div></AdminLayout>} />
      </Routes>
    </MemoryRouter>
  );

  expect(screen.getByText('数据飞轮')).toBeInTheDocument();
  expect(screen.getByText('页面内容')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the route/menu test to verify it fails**

Run:

```bash
cd admin-web && pnpm exec vitest run src/pages/DataFlywheel/index.test.tsx
```

Expected: FAIL because `AdminLayout` does not yet include the `数据飞轮` menu entry.

- [ ] **Step 3: Modify `admin-web/src/App.tsx`**

Add this import near the other page imports:

```typescript
import DataFlywheel from './pages/DataFlywheel';
```

Add this route near the other `/dev/*` routes, after Playground:

```tsx
          <Route path="/dev/data-flywheel" element={<AuthGuard><DataFlywheel /></AuthGuard>} />
```

- [ ] **Step 4: Modify `admin-web/src/layouts/AdminLayout.tsx`**

Add an icon import:

```typescript
  DatabaseOutlined,
```

Add the menu item in the Agent 平台 group after Playground:

```tsx
      { key: '/dev/data-flywheel', icon: <DatabaseOutlined />, label: '数据飞轮' },
```

Add the page title:

```typescript
  '/dev/data-flywheel': '数据飞轮',
```

- [ ] **Step 5: Run route/menu tests**

Run:

```bash
cd admin-web && pnpm exec vitest run src/pages/DataFlywheel/index.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd admin-web && pnpm build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add admin-web/src/App.tsx admin-web/src/layouts/AdminLayout.tsx admin-web/src/pages/DataFlywheel/index.test.tsx
git commit -m "feat: add data flywheel admin route"
```

---

### Task 7: Final Verification and Documentation Check

**Files:**
- Modify only if verification reveals small fixes in files touched by Tasks 1-6.

- [ ] **Step 1: Run backend focused test suite**

Run:

```bash
cd backend && poetry run pytest \
  tests/test_agent_data_flywheel_models.py \
  tests/services/test_data_flywheel_service.py \
  tests/api/test_admin_data_flywheel.py \
  tests/services/test_session_debug_export_service.py \
  tests/services/test_session_dataset_service.py \
  tests/api/test_admin_trace.py \
  tests/api/test_agent_debug_export.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run backend lint**

Run:

```bash
cd backend && poetry run ruff check app tests
```

Expected: PASS.

- [ ] **Step 3: Run frontend focused tests**

Run:

```bash
cd admin-web && pnpm exec vitest run src/api/dataFlywheel.test.ts src/pages/DataFlywheel/index.test.tsx
```

Expected: PASS.

- [ ] **Step 4: Run frontend lint and build**

Run:

```bash
cd admin-web && pnpm lint && pnpm build
```

Expected: PASS.

- [ ] **Step 5: Manually smoke test in browser**

Start the backend and frontend in separate terminals:

```bash
cd backend && poetry run uvicorn app.main:app --reload
cd admin-web && pnpm dev
```

Open the Vite URL, log in as an admin user, then verify:

- The sidebar shows `数据飞轮` under `Agent 平台`.
- `/dev/data-flywheel` renders without console errors.
- The sample list loads.
- Clicking a sample loads detail.
- Saving a label updates the sample status.
- Copy debug JSON writes valid JSON to the clipboard.
- Export JSONL writes a JSONL line to the clipboard.
- Generating a regression case opens the Case Draft preview.
- Jumping to TraceMonitor uses the selected sample's `request_id` and `session_id`.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short
```

Expected: only intended files are modified. Do not stage unrelated files such as existing SQLite `*.db-shm`, `*.db-wal`, or user-created chat session JSON files.

- [ ] **Step 7: Commit final fixes if needed**

If Step 1-6 required fixes, commit only the relevant files:

```bash
git add <fixed-files>
git commit -m "fix: stabilize data flywheel admin"
```

If no fixes were needed, do not create an empty commit.

## Plan Self-Review

- Spec coverage: the plan covers backend storage, sample list/detail APIs, labels, JSONL export, case draft creation, frontend page, field display, actions, route/menu integration, and verification.
- Scope boundary: the plan does not implement LLM-as-judge, dataset versioning, DB-backed simulation cases, or automatic prompt/router fixes.
- Placeholder scan: no unresolved placeholders are required for execution; commands and expected outcomes are explicit.
- Type consistency: `sample_id`, `sample_type`, label values, case draft fields, API paths, and frontend TypeScript names match across backend and frontend tasks.
