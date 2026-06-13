---
last_updated: 2026-06-12
status: active
---

# DataFlywheel LLM Prelabel MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 DataFlywheel 从“规则候选 -> 人工标注 -> case draft”扩展为“规则候选 -> LLM 预标注 -> 人工采纳/修改/驳回 -> case draft / regression”。

**Architecture:** 新增独立 `agent_data_flywheel_prelabels` 表保存 `llm_judge` 预标注，人工未采纳前不写入 `agent_data_flywheel_labels`，也不进入 `quality_labels`、case draft、regression 或 SFT 真值。后端新增 judge service，把 sample detail/debug evidence 归一化后交给可注入 judge client，输出固定结构；API 暴露生成、采纳、驳回三个动作，其中生成接口受配置开关保护且默认关闭。前端在现有 `AnnotationPanel` 增加 AI 预判卡片，只在管理员手动点击“AI 预判”时触发，不随列表或详情加载自动调用。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, React, TypeScript, Ant Design, Vitest.

---

## Scope Check

本计划只覆盖 LLM 自动预标注 MVP：

- 包含：DB 表、SQLAlchemy 模型、Alembic 迁移、judge service、DataFlywheel service/API 编排、配置开关、前端 API 类型和 AI 预判 UI。
- 包含：人工采纳/修改后才写入 `agent_data_flywheel_labels`，驳回只更新预标注状态。
- 包含：服务/API/前端 Vitest 测试命令。
- 不包含：批量预标注任务、队列、prompt 后台调优面板、统计报表、dataset 版本管理、DB-backed simulation cases。

相关长期设计：

- `/Users/ljn/Documents/demo/explore/docs/architecture/agent-data-flywheel-industrial-roadmap.md`
- `/Users/ljn/Documents/demo/explore/docs/superpowers/specs/2026-06-11-agent-data-flywheel-admin-design.md`
- `/Users/ljn/Documents/demo/explore/docs/superpowers/plans/2026-06-12-data-flywheel-issue-candidates-regression.md`

执行前先检查脏工作区：

```bash
cd /Users/ljn/Documents/demo/explore
git status --short
```

当前仓库可能已有 unrelated dirty files。执行者只允许修改本计划列出的文件；不要回滚、删除、格式化或提交无关内容。

## File Structure

- Modify: `/Users/ljn/Documents/demo/explore/backend/app/models/data_flywheel.py`
  - 新增 `AgentDataFlywheelPrelabel` 模型，专门保存 `llm_judge` 结果和人工审阅状态。
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/models/__init__.py`
  - 导出 `AgentDataFlywheelPrelabel`，让 `Base.metadata.create_all()` 测试能建表。
- Create: `/Users/ljn/Documents/demo/explore/backend/alembic/versions/20260612_agent_data_flywheel_prelabels.py`
  - 创建 `agent_data_flywheel_prelabels` 表和索引。
- Create: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_judge_service.py`
  - 负责构造 judge 输入、校验/归一化 judge 输出、创建预标注记录。
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py`
  - 在 sample detail/list 中返回 prelabels；新增生成、采纳、驳回预标注的服务方法；采纳才调用现有人工标签写入。
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/api/admin_data_flywheel.py`
  - 新增三个 API：`POST /admin/data-flywheel/samples/{sample_id}/prelabel`、`POST /admin/data-flywheel/samples/{sample_id}/prelabels/{id}/accept`、`POST /admin/data-flywheel/samples/{sample_id}/prelabels/{id}/reject`。
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/test_agent_data_flywheel_models.py`
  - 覆盖预标注模型 round-trip。
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_judge_service.py`
  - 覆盖 judge 输入证据和输出归一化。
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`
  - 覆盖预标注不进入人工真值、采纳/修改/驳回流程。
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_admin_data_flywheel.py`
  - 覆盖三个 API 的路由、权限上下文、错误码和安全边界。
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/api/dataFlywheel.ts`
  - 新增 prelabel 类型和 API client。
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/index.tsx`
  - 连接预标注加载、生成、采纳、修改保存、驳回动作。
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx`
  - 增加 AI 预判卡片。
- Test: `/Users/ljn/Documents/demo/explore/admin-web/src/api/dataFlywheel.test.ts`
  - 覆盖三个前端 API client。
- Test: `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/index.test.tsx`
  - 覆盖 AI 预判卡片的生成、采纳、修改后保存、驳回交互。

## Data Contract

`llm_judge` 预标注响应统一为：

```json
{
  "labels": ["bad_reply", "pending_missed", "needs_regression"],
  "root_cause": "写操作没有完整 pending 确认链路",
  "severity": "high",
  "confidence": 0.86,
  "reason": "assistant 回复声称已安排，但证据中缺少 create_operation_work_order 的 pending 确认。",
  "recommended_fix": "补齐写操作 pending plan，并在未确认前禁止执行写工具。"
}
```

安全边界：

- `agent_data_flywheel_prelabels.source` 固定为 `llm_judge`。
- `agent_data_flywheel_prelabels.status = "pending"` 或 `"rejected"` 时，不写入 `agent_data_flywheel_labels`。
- `data_flywheel.llm_prelabel_enabled` 默认 `false`；未开启时 `POST /prelabel` 返回 `LLM_PRELABEL_DISABLED`，不调用 judge client，不消耗 token。
- 只有管理员手动调用 `POST /admin/data-flywheel/samples/{sample_id}/prelabel` 才能创建预标注；列表、详情、刷新和筛选流程都不得自动触发 judge。
- `get_sample_detail()["quality_labels"]` 只来自 `AgentDataFlywheelLabel` 的 open 人工标签。
- `export_sample_jsonl()` 和 `build_case_draft()` 只读取 `quality_labels`，最多在 metadata 附带 `prelabels` 作为参考信息，不能把未采纳的 labels 写成真值。
- `accept_prelabel()` 支持人工修改 labels/comment 后保存，写入 label 的 `annotator_id` 是当前管理员，预标注记录只保存 `accepted_label_ids` 作为来源追溯。

---

### Task 1: Add Prelabel Storage Model And Migration

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/models/data_flywheel.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/models/__init__.py`
- Create: `/Users/ljn/Documents/demo/explore/backend/alembic/versions/20260612_agent_data_flywheel_prelabels.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/test_agent_data_flywheel_models.py`

- [ ] **Step 1: Write failing model test**

Append to `/Users/ljn/Documents/demo/explore/backend/tests/test_agent_data_flywheel_models.py`:

```python
def test_agent_data_flywheel_prelabel_round_trip():
    db = Session()
    prelabel = AgentDataFlywheelPrelabel(
        farm_id=1,
        sample_id="turn:1:sess-1:12",
        sample_type="session_turn",
        session_id="sess-1",
        turn_id=12,
        request_id="abcd1234",
        source="llm_judge",
        status="pending",
        labels=["bad_reply", "pending_missed"],
        root_cause="写操作缺少 pending 确认",
        severity="high",
        confidence=0.86,
        reason="回复声称已安排，但证据中没有完整确认链路。",
        recommended_fix="写操作必须先创建 pending plan。",
        judge_model="gpt-4.1-mini",
        prompt_version="data-flywheel-prelabel-v1",
        raw_response={"labels": ["bad_reply", "pending_missed"]},
    )
    db.add(prelabel)
    db.commit()
    db.refresh(prelabel)

    loaded = db.query(AgentDataFlywheelPrelabel).filter_by(id=prelabel.id).one()

    assert loaded.id is not None
    assert loaded.source == "llm_judge"
    assert loaded.status == "pending"
    assert loaded.labels == ["bad_reply", "pending_missed"]
    assert loaded.root_cause == "写操作缺少 pending 确认"
    assert loaded.severity == "high"
    assert loaded.confidence == 0.86
    assert loaded.accepted_label_ids is None
    assert loaded.reviewed_by is None
    assert loaded.reviewed_at is None
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()
```

Also update the import:

```python
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelLabel,
    AgentDataFlywheelPrelabel,
)
```

- [ ] **Step 2: Run model test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/test_agent_data_flywheel_models.py::test_agent_data_flywheel_prelabel_round_trip -q
```

Expected: FAIL with import error or missing `AgentDataFlywheelPrelabel`.

- [ ] **Step 3: Add SQLAlchemy model**

Modify `/Users/ljn/Documents/demo/explore/backend/app/models/data_flywheel.py`.

Update imports:

```python
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
```

Add below `AgentDataFlywheelLabel`:

```python
class AgentDataFlywheelPrelabel(Base):
    """LLM judge 对 Agent 样本的自动预标注记录。"""

    __tablename__ = "agent_data_flywheel_prelabels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    sample_id = Column(String(160), nullable=False, index=True)
    sample_type = Column(String(40), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    turn_id = Column(Integer, nullable=True, index=True)
    request_id = Column(String(32), nullable=True, index=True)
    source = Column(String(32), nullable=False, default="llm_judge", index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    labels = Column(JSON, nullable=False)
    root_cause = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    reason = Column(Text, nullable=False)
    recommended_fix = Column(Text, nullable=True)
    judge_model = Column(String(80), nullable=False, index=True)
    prompt_version = Column(String(80), nullable=False, index=True)
    raw_response = Column(JSON, nullable=True)
    accepted_label_ids = Column(JSON, nullable=True)
    reviewed_by = Column(String(64), nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )
```

- [ ] **Step 4: Export model**

Modify `/Users/ljn/Documents/demo/explore/backend/app/models/__init__.py`:

```python
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelLabel,
    AgentDataFlywheelPrelabel,
)
```

Add `"AgentDataFlywheelPrelabel"` to `__all__`.

- [ ] **Step 5: Add Alembic migration**

Create `/Users/ljn/Documents/demo/explore/backend/alembic/versions/20260612_agent_data_flywheel_prelabels.py`:

```python
"""add data flywheel llm prelabels

Revision ID: 20260612_agent_data_flywheel_prelabels
Revises: 20260612_add_user_assistant_role
Create Date: 2026-06-12 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260612_agent_data_flywheel_prelabels"
down_revision: Union[str, None] = "20260612_add_user_assistant_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_name = "agent_data_flywheel_prelabels"
    if table_name not in inspector.get_table_names():
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
            sa.Column("sample_id", sa.String(length=160), nullable=False),
            sa.Column("sample_type", sa.String(length=40), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("turn_id", sa.Integer(), nullable=True),
            sa.Column("request_id", sa.String(length=32), nullable=True),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="llm_judge"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("labels", sa.JSON(), nullable=False),
            sa.Column("root_cause", sa.Text(), nullable=True),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("recommended_fix", sa.Text(), nullable=True),
            sa.Column("judge_model", sa.String(length=80), nullable=False),
            sa.Column("prompt_version", sa.String(length=80), nullable=False),
            sa.Column("raw_response", sa.JSON(), nullable=True),
            sa.Column("accepted_label_ids", sa.JSON(), nullable=True),
            sa.Column("reviewed_by", sa.String(length=64), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    for index_name, columns in {
        "ix_agent_data_flywheel_prelabels_farm_id": ["farm_id"],
        "ix_agent_data_flywheel_prelabels_sample_id": ["sample_id"],
        "ix_agent_data_flywheel_prelabels_sample_type": ["sample_type"],
        "ix_agent_data_flywheel_prelabels_session_id": ["session_id"],
        "ix_agent_data_flywheel_prelabels_turn_id": ["turn_id"],
        "ix_agent_data_flywheel_prelabels_request_id": ["request_id"],
        "ix_agent_data_flywheel_prelabels_source": ["source"],
        "ix_agent_data_flywheel_prelabels_status": ["status"],
        "ix_agent_data_flywheel_prelabels_severity": ["severity"],
        "ix_agent_data_flywheel_prelabels_judge_model": ["judge_model"],
        "ix_agent_data_flywheel_prelabels_prompt_version": ["prompt_version"],
        "ix_agent_data_flywheel_prelabels_reviewed_by": ["reviewed_by"],
        "ix_agent_data_flywheel_prelabels_reviewed_at": ["reviewed_at"],
        "ix_agent_data_flywheel_prelabels_created_at": ["created_at"],
    }.items():
        if index_name not in indexes:
            op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_name = "agent_data_flywheel_prelabels"
    if table_name in inspector.get_table_names():
        op.drop_table(table_name)
```

- [ ] **Step 6: Run model test to verify it passes**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/test_agent_data_flywheel_models.py::test_agent_data_flywheel_prelabel_round_trip -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/models/data_flywheel.py backend/app/models/__init__.py backend/alembic/versions/20260612_agent_data_flywheel_prelabels.py backend/tests/test_agent_data_flywheel_models.py
git commit -m "feat: add data flywheel llm prelabel storage"
```

---

### Task 2: Add Judge Service With Deterministic Test Client

**Files:**
- Create: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_judge_service.py`
- Create: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_judge_service.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py`

- [ ] **Step 1: Write failing judge service tests**

Create `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_judge_service.py`:

```python
"""DataFlywheel LLM 预标注 judge service 测试。"""

import pytest

from app.services.data_flywheel_judge_service import (
    DataFlywheelJudgeClient,
    build_judge_input,
    normalize_judge_output,
)

pytestmark = pytest.mark.no_db


class FakeJudgeClient(DataFlywheelJudgeClient):
    judge_model = "fake-judge"
    prompt_version = "data-flywheel-prelabel-v1"

    def judge(self, payload):
        assert payload["sample"]["sample_id"] == "turn:1:sess-1:12"
        assert payload["debug_evidence"]["router_decision"]["selected_tools"] == [
            "create_operation_work_order"
        ]
        assert payload["debug_evidence"]["tool_events"][0]["payload"]["tool_name"] == (
            "create_operation_work_order"
        )
        return {
            "labels": ["bad_reply", "pending_missed", "not_allowed_label"],
            "root_cause": "写操作缺少 pending 确认",
            "severity": "high",
            "confidence": 1.4,
            "reason": "assistant 声称已安排，但 pending lifecycle 为空。",
            "recommended_fix": "写工具执行前必须创建 pending plan。",
        }


def _detail():
    return {
        "sample": {
            "sample_id": "turn:1:sess-1:12",
            "sample_type": "session_turn",
            "session_id": "sess-1",
            "turn_id": 12,
            "request_id": "abcd1234",
            "user_input_preview": "安排王大妈去5号棚收水稻",
            "assistant_reply_preview": "已安排王大妈去5号棚收水稻。",
            "selected_tools": ["create_operation_work_order"],
            "actual_tools": ["create_operation_work_order"],
            "issue_candidates": [
                {
                    "type": "pending_missed",
                    "severity": "high",
                    "reason": "写操作缺少 pending",
                    "evidence": "create_operation_work_order",
                    "suggested_label": "pending_missed",
                }
            ],
        },
        "messages": [
            {"role": "user", "content": "安排王大妈去5号棚收水稻"},
            {"role": "assistant", "content": "已安排王大妈去5号棚收水稻。"},
        ],
        "router_decision": {"selected_tools": ["create_operation_work_order"]},
        "tool_events": [
            {
                "event_type": "tool.call.finished",
                "payload": {"tool_name": "create_operation_work_order", "result": {"id": 9}},
            }
        ],
        "pending_lifecycle": [],
        "debug_export": {"session_id": "sess-1", "turns": [{"request_id": "abcd1234"}]},
        "source": {"event_file": "events.jsonl", "event_seq_start": 1, "event_seq_end": 5},
    }


def test_build_judge_input_contains_sample_detail_and_debug_evidence():
    payload = build_judge_input(_detail())

    assert payload["sample"]["sample_id"] == "turn:1:sess-1:12"
    assert payload["sample"]["user_input"] == "安排王大妈去5号棚收水稻"
    assert payload["sample"]["assistant_reply"] == "已安排王大妈去5号棚收水稻。"
    assert payload["sample"]["issue_candidates"][0]["type"] == "pending_missed"
    assert payload["debug_evidence"]["router_decision"]["selected_tools"] == [
        "create_operation_work_order"
    ]
    assert payload["debug_evidence"]["pending_lifecycle"] == []
    assert payload["debug_evidence"]["source"]["event_file"] == "events.jsonl"


def test_normalize_judge_output_filters_labels_and_clamps_confidence():
    result = normalize_judge_output(
        {
            "labels": ["bad_reply", "pending_missed", "not_allowed_label"],
            "root_cause": "写操作缺少 pending 确认",
            "severity": "critical",
            "confidence": 1.4,
            "reason": "assistant 声称已安排，但 pending lifecycle 为空。",
            "recommended_fix": "写工具执行前必须创建 pending plan。",
        }
    )

    assert result == {
        "labels": ["bad_reply", "pending_missed"],
        "root_cause": "写操作缺少 pending 确认",
        "severity": "critical",
        "confidence": 1.0,
        "reason": "assistant 声称已安排，但 pending lifecycle 为空。",
        "recommended_fix": "写工具执行前必须创建 pending plan。",
    }


def test_judge_client_contract_returns_normalized_output():
    client = FakeJudgeClient()
    raw = client.judge(build_judge_input(_detail()))
    result = normalize_judge_output(raw)

    assert result["labels"] == ["bad_reply", "pending_missed"]
    assert result["confidence"] == 1.0
```

- [ ] **Step 2: Run judge tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_judge_service.py -q
```

Expected: FAIL because `data_flywheel_judge_service.py` does not exist.

- [ ] **Step 3: Implement judge service primitives**

Create `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_judge_service.py`:

```python
"""DataFlywheel LLM judge 预标注服务。"""

from typing import Any, Protocol

ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}
ALLOWED_JUDGE_LABELS = {
    "good_reply",
    "bad_reply",
    "wrong_tool_selection",
    "pending_missed",
    "hallucinated_execution",
    "tool_error_ignored",
    "missing_wage",
    "disabled_worker_used",
    "needs_regression",
    "off_topic",
    "sensitive_info_leak",
    "unclear_intent",
    "not_actionable",
}
DEFAULT_PROMPT_VERSION = "data-flywheel-prelabel-v1"


class DataFlywheelJudgeClient(Protocol):
    """DataFlywheel LLM judge 客户端协议。"""

    judge_model: str
    prompt_version: str

    def judge(self, payload: dict[str, Any]) -> dict[str, Any]:
        """返回 LLM judge 原始 JSON 结果。"""


def build_judge_input(detail: dict[str, Any]) -> dict[str, Any]:
    """从 sample detail/debug evidence 构造 judge 输入。"""
    sample = detail["sample"]
    return {
        "task": "data_flywheel_llm_prelabel",
        "prompt_version": DEFAULT_PROMPT_VERSION,
        "sample": {
            "sample_id": sample["sample_id"],
            "sample_type": sample["sample_type"],
            "session_id": sample["session_id"],
            "turn_id": sample["turn_id"],
            "request_id": sample["request_id"],
            "user_input": _message_content(detail, "user")
            or sample.get("user_input_preview")
            or "",
            "assistant_reply": _message_content(detail, "assistant")
            or sample.get("assistant_reply_preview")
            or "",
            "selected_tools": sample.get("selected_tools", []),
            "actual_tools": sample.get("actual_tools", []),
            "issue_candidates": sample.get("issue_candidates", []),
        },
        "debug_evidence": {
            "router_decision": detail.get("router_decision") or {},
            "tool_events": detail.get("tool_events") or [],
            "pending_lifecycle": detail.get("pending_lifecycle") or [],
            "source": detail.get("source") or {},
            "debug_export": detail.get("debug_export") or {},
        },
        "output_schema": {
            "labels": "list[str]",
            "root_cause": "str",
            "severity": "critical|high|medium|low",
            "confidence": "float 0..1",
            "reason": "str",
            "recommended_fix": "str",
        },
    }


def normalize_judge_output(raw: dict[str, Any]) -> dict[str, Any]:
    """校验并归一化 judge 输出，避免非法标签进入预标注。"""
    labels = [
        str(label)
        for label in raw.get("labels", [])
        if isinstance(label, str) and label in ALLOWED_JUDGE_LABELS
    ]
    severity = str(raw.get("severity") or "medium")
    if severity not in ALLOWED_SEVERITIES:
        severity = "medium"
    confidence = _clamp_confidence(raw.get("confidence"))
    reason = str(raw.get("reason") or "").strip()
    if not labels:
        labels = ["not_actionable"]
    if not reason:
        reason = "LLM judge 未返回判断理由。"
    return {
        "labels": labels,
        "root_cause": str(raw.get("root_cause") or "").strip(),
        "severity": severity,
        "confidence": confidence,
        "reason": reason,
        "recommended_fix": str(raw.get("recommended_fix") or "").strip(),
    }


def _clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number, 1.0))


def _message_content(detail: dict[str, Any], role: str) -> str | None:
    for message in detail.get("messages", []):
        if message.get("role") == role:
            content = message.get("content")
            return str(content) if content is not None else None
    return None
```

- [ ] **Step 4: Run judge tests to verify they pass**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_judge_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/data_flywheel_judge_service.py backend/tests/services/test_data_flywheel_judge_service.py
git commit -m "feat: add data flywheel llm judge service"
```

---

### Task 3: Wire Prelabel Service Methods And Safety Boundary

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`

- [ ] **Step 1: Write failing service tests**

Append to `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`:

```python
from app.services.data_flywheel_judge_service import DataFlywheelJudgeClient


class FakePrelabelJudgeClient(DataFlywheelJudgeClient):
    judge_model = "fake-judge"
    prompt_version = "data-flywheel-prelabel-v1"

    def judge(self, payload):
        assert payload["sample"]["sample_id"].startswith("turn:1:")
        return {
            "labels": ["bad_reply", "pending_missed", "needs_regression"],
            "root_cause": "写操作缺少 pending 确认",
            "severity": "high",
            "confidence": 0.86,
            "reason": "回复声称已安排，但没有完整 pending lifecycle。",
            "recommended_fix": "写操作执行前必须创建 pending plan。",
        }


def test_create_prelabel_does_not_enter_quality_labels_or_case_truth(tmp_path):
    db = Session()
    turn = _seed_turn(
        db,
        tmp_path,
        include_pending=False,
        router_tools=["create_operation_work_order"],
        tool_events=[
            (
                "tool.call.finished",
                {
                    "tool_name": "create_operation_work_order",
                    "params": {"workers": "王大妈"},
                    "result": {"id": 9},
                },
            )
        ],
    )
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    prelabel = create_sample_prelabel(
        db,
        farm_id=1,
        sample_id=sample_id,
        judge_client=FakePrelabelJudgeClient(),
    )
    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)
    draft = build_case_draft(
        db,
        farm_id=1,
        sample_id=sample_id,
        target_type="evaluation_replay",
        created_by="admin-1",
    )

    assert prelabel["source"] == "llm_judge"
    assert prelabel["status"] == "pending"
    assert prelabel["labels"] == ["bad_reply", "pending_missed", "needs_regression"]
    assert detail["quality_labels"] == []
    assert detail["prelabels"][0]["labels"] == [
        "bad_reply",
        "pending_missed",
        "needs_regression",
    ]
    assert draft["case_json"]["metadata"]["quality_labels"] == []
    assert draft["case_json"]["category"] == "data_flywheel"
    db.close()


def test_accept_prelabel_writes_human_labels_and_links_prelabel(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path, include_pending=False, router_tools=["create_operation_work_order"])
    sample_id = f"turn:1:sess-flywheel:{turn.id}"
    prelabel = create_sample_prelabel(
        db,
        farm_id=1,
        sample_id=sample_id,
        judge_client=FakePrelabelJudgeClient(),
    )

    result = accept_sample_prelabel(
        db,
        farm_id=1,
        sample_id=sample_id,
        prelabel_id=prelabel["id"],
        labels=["pending_missed", "needs_regression"],
        comment="采纳 AI 预判，人工确认需要回归。",
        annotator_id="admin-1",
    )
    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert result["status"] == "accepted"
    assert result["reviewed_by"] == "admin-1"
    assert result["accepted_label_ids"]
    assert detail["quality_labels"] == ["pending_missed", "needs_regression"]
    assert detail["prelabels"][0]["status"] == "accepted"
    assert detail["labels"][0]["comment"] == "采纳 AI 预判，人工确认需要回归。"
    db.close()


def test_reject_prelabel_keeps_quality_labels_empty(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path, include_pending=False)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"
    prelabel = create_sample_prelabel(
        db,
        farm_id=1,
        sample_id=sample_id,
        judge_client=FakePrelabelJudgeClient(),
    )

    result = reject_sample_prelabel(
        db,
        farm_id=1,
        sample_id=sample_id,
        prelabel_id=prelabel["id"],
        reviewer_id="admin-1",
    )
    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert result["status"] == "rejected"
    assert result["reviewed_by"] == "admin-1"
    assert detail["quality_labels"] == []
    assert detail["prelabels"][0]["status"] == "rejected"
    db.close()
```

Update the service import block in the test file:

```python
from app.services.data_flywheel_service import (
    SAMPLE_TYPE_SESSION,
    accept_sample_prelabel,
    add_sample_label,
    build_case_draft,
    create_sample_prelabel,
    delete_sample_label,
    export_sample_jsonl,
    get_session_annotation_detail,
    get_sample_detail,
    list_samples,
    reject_sample_prelabel,
    resolve_sample_label,
)
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_service.py::test_create_prelabel_does_not_enter_quality_labels_or_case_truth tests/services/test_data_flywheel_service.py::test_accept_prelabel_writes_human_labels_and_links_prelabel tests/services/test_data_flywheel_service.py::test_reject_prelabel_keeps_quality_labels_empty -q
```

Expected: FAIL because service functions do not exist.

- [ ] **Step 3: Add prelabel imports and constants**

Modify `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py`.

Update imports:

```python
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelLabel,
    AgentDataFlywheelPrelabel,
)
from app.services.data_flywheel_judge_service import (
    DataFlywheelJudgeClient,
    build_judge_input,
    normalize_judge_output,
)
```

Add constants near label status constants:

```python
PRELABEL_STATUS_PENDING = "pending"
PRELABEL_STATUS_ACCEPTED = "accepted"
PRELABEL_STATUS_REJECTED = "rejected"
PRELABEL_SOURCE_LLM_JUDGE = "llm_judge"
```

- [ ] **Step 4: Add prelabel query and serializer helpers**

Add helpers near `_labels_by_sample`:

```python
def _prelabels_by_sample(
    db: Session, sample_ids: list[str]
) -> dict[str, list[AgentDataFlywheelPrelabel]]:
    if not sample_ids:
        return {}
    rows = (
        db.query(AgentDataFlywheelPrelabel)
        .filter(AgentDataFlywheelPrelabel.sample_id.in_(sample_ids))
        .order_by(
            AgentDataFlywheelPrelabel.created_at.desc(),
            AgentDataFlywheelPrelabel.id.desc(),
        )
        .all()
    )
    grouped: dict[str, list[AgentDataFlywheelPrelabel]] = defaultdict(list)
    for row in rows:
        grouped[row.sample_id].append(row)
    return dict(grouped)
```

Add serializer near `_label_to_dict`:

```python
def _prelabel_to_dict(row: AgentDataFlywheelPrelabel) -> dict[str, Any]:
    return {
        "id": row.id,
        "sample_id": row.sample_id,
        "sample_type": row.sample_type,
        "session_id": row.session_id,
        "turn_id": row.turn_id,
        "request_id": row.request_id,
        "source": row.source,
        "status": row.status,
        "labels": row.labels,
        "root_cause": row.root_cause,
        "severity": row.severity,
        "confidence": row.confidence,
        "reason": row.reason,
        "recommended_fix": row.recommended_fix,
        "judge_model": row.judge_model,
        "prompt_version": row.prompt_version,
        "accepted_label_ids": row.accepted_label_ids,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
```

- [ ] **Step 5: Return prelabels in list/detail without mixing quality labels**

In `list_samples()`, after `labels = _labels_by_sample(db, sample_ids)` add:

```python
prelabels = _prelabels_by_sample(db, sample_ids)
```

Pass prelabels into `_sample_row`:

```python
_sample_row(
    turn,
    labels.get(_sample_id(turn), []),
    _events_for_turn(turn),
    prelabels=prelabels.get(_sample_id(turn), []),
    session_labels=session_labels.get(
        session_sample_id(farm_id=turn.farm_id, session_id=turn.session_id),
        [],
    ),
)
```

Change `_sample_row` signature:

```python
def _sample_row(
    turn: AgentTurn,
    labels: list[AgentDataFlywheelLabel],
    events: list[dict[str, Any]],
    *,
    prelabels: list[AgentDataFlywheelPrelabel] | None = None,
    session_labels: list[AgentDataFlywheelLabel] | None = None,
) -> dict[str, Any]:
```

Inside `_sample_row`, add:

```python
prelabels = prelabels or []
```

Add fields to the returned dict:

```python
"prelabels": [_prelabel_to_dict(row) for row in prelabels],
"latest_prelabel": _prelabel_to_dict(prelabels[0]) if prelabels else None,
```

In `get_sample_detail()`, after labels:

```python
prelabels = _prelabels_by_sample(db, [sample_id]).get(sample_id, [])
```

Pass to `_sample_row` and return:

```python
sample = _sample_row(turn, labels, events, prelabels=prelabels)
```

Add:

```python
"prelabels": [_prelabel_to_dict(row) for row in prelabels],
```

- [ ] **Step 6: Add create/accept/reject service functions**

Add below `resolve_sample_label()`:

```python
def create_sample_prelabel(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    judge_client: DataFlywheelJudgeClient,
) -> dict[str, Any]:
    """为样本创建一条 LLM judge 预标注，不写入人工真值。"""
    detail = get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
    sample = detail["sample"]
    raw = judge_client.judge(build_judge_input(detail))
    normalized = normalize_judge_output(raw)
    row = AgentDataFlywheelPrelabel(
        farm_id=farm_id,
        sample_id=sample_id,
        sample_type=SAMPLE_TYPE_SESSION_TURN,
        session_id=sample["session_id"],
        turn_id=sample["turn_id"],
        request_id=sample["request_id"],
        source=PRELABEL_SOURCE_LLM_JUDGE,
        status=PRELABEL_STATUS_PENDING,
        labels=normalized["labels"],
        root_cause=normalized["root_cause"],
        severity=normalized["severity"],
        confidence=normalized["confidence"],
        reason=normalized["reason"],
        recommended_fix=normalized["recommended_fix"],
        judge_model=judge_client.judge_model,
        prompt_version=judge_client.prompt_version,
        raw_response=raw,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _prelabel_to_dict(row)


def accept_sample_prelabel(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    prelabel_id: int,
    labels: list[str] | None,
    comment: str | None,
    annotator_id: str | None,
) -> dict[str, Any]:
    """采纳或人工修改 LLM 预标注后写入人工标签。"""
    prelabel = _prelabel_for_sample(
        db, farm_id=farm_id, sample_id=sample_id, prelabel_id=prelabel_id
    )
    final_labels = labels if labels is not None else list(prelabel.labels or [])
    if not final_labels:
        raise ValueError("INVALID_LABEL")
    accepted_label_ids: list[int] = []
    for label in final_labels:
        if label not in ALLOWED_LABELS:
            raise ValueError("INVALID_LABEL")
        saved = add_sample_label(
            db,
            farm_id=farm_id,
            sample_id=sample_id,
            label=label,
            sample_type=SAMPLE_TYPE_SESSION_TURN,
            comment=comment,
            annotator_id=annotator_id,
        )
        accepted_label_ids.append(int(saved["id"]))
    prelabel.status = PRELABEL_STATUS_ACCEPTED
    prelabel.accepted_label_ids = accepted_label_ids
    prelabel.reviewed_by = annotator_id
    prelabel.reviewed_at = datetime.now()
    db.commit()
    db.refresh(prelabel)
    return _prelabel_to_dict(prelabel)


def reject_sample_prelabel(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    prelabel_id: int,
    reviewer_id: str | None,
) -> dict[str, Any]:
    """驳回 LLM 预标注，不写入人工标签。"""
    prelabel = _prelabel_for_sample(
        db, farm_id=farm_id, sample_id=sample_id, prelabel_id=prelabel_id
    )
    prelabel.status = PRELABEL_STATUS_REJECTED
    prelabel.reviewed_by = reviewer_id
    prelabel.reviewed_at = datetime.now()
    db.commit()
    db.refresh(prelabel)
    return _prelabel_to_dict(prelabel)


def _prelabel_for_sample(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    prelabel_id: int,
) -> AgentDataFlywheelPrelabel:
    row = (
        db.query(AgentDataFlywheelPrelabel)
        .filter(
            AgentDataFlywheelPrelabel.id == prelabel_id,
            AgentDataFlywheelPrelabel.farm_id == farm_id,
            AgentDataFlywheelPrelabel.sample_id == sample_id,
        )
        .first()
    )
    if row is None:
        raise ValueError("PRELABEL_NOT_FOUND")
    return row
```

- [ ] **Step 7: Export functions**

`/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py` 当前没有 `__all__`，本步只需确认文件末尾没有新增导出列表。不要为了这三个函数新建 `__all__`。

- [ ] **Step 8: Run service tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_service.py::test_create_prelabel_does_not_enter_quality_labels_or_case_truth tests/services/test_data_flywheel_service.py::test_accept_prelabel_writes_human_labels_and_links_prelabel tests/services/test_data_flywheel_service.py::test_reject_prelabel_keeps_quality_labels_empty -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/data_flywheel_service.py backend/tests/services/test_data_flywheel_service.py
git commit -m "feat: wire data flywheel prelabel lifecycle"
```

---

### Task 4: Add Admin API Endpoints

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/core/settings/models.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/core/settings/settings.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/core/settings/__init__.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/core/config.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/config.yaml.example`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/api/admin_data_flywheel.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_admin_data_flywheel.py`

- [ ] **Step 1: Write failing API tests**

Append to `/Users/ljn/Documents/demo/explore/backend/tests/api/test_admin_data_flywheel.py`:

```python
def test_prelabel_endpoint_is_disabled_by_default(client, monkeypatch):
    class FailingJudgeClient:
        judge_model = "should-not-run"
        prompt_version = "data-flywheel-prelabel-v1"

        def judge(self, payload):
            raise AssertionError("disabled prelabel endpoint must not call judge")

    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: FailingJudgeClient(),
    )
    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        False,
    )
    sample_id = _sample_id(_seed_turn(db_session, tmp_path))

    auth_scope, client = _admin_client()
    with auth_scope:
        response = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "LLM_PRELABEL_DISABLED"


def test_prelabel_endpoint_creates_pending_llm_judge_prelabel(
    db_session, tmp_path, monkeypatch
) -> None:
    class FakeApiJudgeClient:
        judge_model = "fake-judge"
        prompt_version = "data-flywheel-prelabel-v1"

        def judge(self, payload):
            return {
                "labels": ["bad_reply", "needs_regression"],
                "root_cause": "回复不可验证",
                "severity": "medium",
                "confidence": 0.72,
                "reason": "证据不足但回复声称完成。",
                "recommended_fix": "要求补充证据后再回复完成。",
            }

    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: FakeApiJudgeClient(),
    )
    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        response = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        )
        detail_response = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "llm_judge"
    assert data["status"] == "pending"
    assert data["labels"] == ["bad_reply", "needs_regression"]
    detail = detail_response.json()
    assert detail["quality_labels"] == []
    assert detail["prelabels"][0]["id"] == data["id"]


def test_accept_prelabel_endpoint_supports_human_modified_labels(
    db_session, tmp_path, monkeypatch
) -> None:
    class FakeApiJudgeClient:
        judge_model = "fake-judge"
        prompt_version = "data-flywheel-prelabel-v1"

        def judge(self, payload):
            return {
                "labels": ["bad_reply", "pending_missed"],
                "root_cause": "pending 缺失",
                "severity": "high",
                "confidence": 0.91,
                "reason": "写操作缺少确认链路。",
                "recommended_fix": "补齐 pending plan。",
            }

    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: FakeApiJudgeClient(),
    )
    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        prelabel = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        ).json()
        response = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabels/{prelabel['id']}/accept",
            json={
                "labels": ["pending_missed", "needs_regression"],
                "comment": "人工修改后采纳。",
            },
            headers=admin_headers(),
        )
        detail_response = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["accepted_label_ids"]
    detail = detail_response.json()
    assert detail["quality_labels"] == ["pending_missed", "needs_regression"]


def test_reject_prelabel_endpoint_does_not_write_quality_labels(
    db_session, tmp_path, monkeypatch
) -> None:
    class FakeApiJudgeClient:
        judge_model = "fake-judge"
        prompt_version = "data-flywheel-prelabel-v1"

        def judge(self, payload):
            return {
                "labels": ["bad_reply"],
                "root_cause": "误判",
                "severity": "low",
                "confidence": 0.4,
                "reason": "测试用误判。",
                "recommended_fix": "无需处理。",
            }

    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: FakeApiJudgeClient(),
    )
    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        prelabel = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        ).json()
        response = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabels/{prelabel['id']}/reject",
            headers=admin_headers(),
        )
        detail_response = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    detail = detail_response.json()
    assert detail["quality_labels"] == []
    assert detail["prelabels"][0]["status"] == "rejected"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/api/test_admin_data_flywheel.py::test_prelabel_endpoint_is_disabled_by_default tests/api/test_admin_data_flywheel.py::test_prelabel_endpoint_creates_pending_llm_judge_prelabel tests/api/test_admin_data_flywheel.py::test_accept_prelabel_endpoint_supports_human_modified_labels tests/api/test_admin_data_flywheel.py::test_reject_prelabel_endpoint_does_not_write_quality_labels -q
```

Expected: FAIL with 404 or missing imported service functions.

- [ ] **Step 3: Add request models and imports**

Modify `/Users/ljn/Documents/demo/explore/backend/app/api/admin_data_flywheel.py`.

Add service imports:

```python
from app.services.data_flywheel_service import (
    SAMPLE_TYPE_SESSION_TURN,
    accept_sample_prelabel,
    add_sample_label,
    build_case_draft,
    create_sample_prelabel,
    delete_sample_label,
    export_sample_jsonl,
    get_session_annotation_detail,
    get_sample_detail,
    list_samples,
    reject_sample_prelabel,
    resolve_sample_label,
)
```

Add request model:

```python
class AcceptPrelabelRequest(BaseModel):
    labels: list[str] | None = None
    comment: str | None = None
```

- [ ] **Step 4: Add DataFlywheel config switch**

Modify `/Users/ljn/Documents/demo/explore/backend/app/core/settings/models.py`:

```python
class DataFlywheelConfig(BaseModel):
    llm_prelabel_enabled: bool = False
```

Modify `/Users/ljn/Documents/demo/explore/backend/app/core/settings/settings.py` imports and `Settings`:

```python
from app.core.settings.models import (
    AIConfig,
    AppConfig,
    AuthConfig,
    CircuitBreakerConfig,
    DataFlywheelConfig,
    DatabaseConfig,
    ...
)

class Settings(BaseSettings):
    ...
    data_flywheel: DataFlywheelConfig = DataFlywheelConfig()
```

Modify `/Users/ljn/Documents/demo/explore/backend/app/core/settings/__init__.py` and `/Users/ljn/Documents/demo/explore/backend/app/core/config.py` to import/export `DataFlywheelConfig`.

Add to `/Users/ljn/Documents/demo/explore/backend/config.yaml.example`:

```yaml
data_flywheel:
  # LLM 预标注默认关闭；只有管理员手动点击 AI 预判，且此开关开启时才会消耗 judge token。
  llm_prelabel_enabled: false
```

- [ ] **Step 5: Add judge client factory placeholder**

Add near module constants:

```python
from app.core.config import settings


def build_data_flywheel_judge_client():
    """构造 DataFlywheel judge client。

    MVP 先保留为显式配置入口；没有配置时返回 400，避免误以为已完成线上 LLM 接入。
    """
    raise ValueError("JUDGE_CLIENT_NOT_CONFIGURED")
```

This explicit failure is part of the MVP safety boundary: environments without configured judge client must return `{"code": "JUDGE_CLIENT_NOT_CONFIGURED"}` instead of silently fabricating labels.

- [ ] **Step 6: Add endpoints**

Add below `get_admin_data_flywheel_sample()`:

```python
@router.post("/samples/{sample_id}/prelabel")
def create_admin_data_flywheel_prelabel(
    sample_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """触发 LLM judge 为样本生成预标注。"""
    try:
        if not settings.data_flywheel.llm_prelabel_enabled:
            raise ValueError("LLM_PRELABEL_DISABLED")
        return create_sample_prelabel(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            judge_client=build_data_flywheel_judge_client(),
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/samples/{sample_id}/prelabels/{prelabel_id}/accept")
def accept_admin_data_flywheel_prelabel(
    sample_id: str,
    prelabel_id: int,
    body: AcceptPrelabelRequest | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """采纳或人工修改 LLM 预标注，写入人工真值标签。"""
    payload = body or AcceptPrelabelRequest()
    try:
        return accept_sample_prelabel(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            prelabel_id=prelabel_id,
            labels=payload.labels,
            comment=payload.comment,
            annotator_id=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/samples/{sample_id}/prelabels/{prelabel_id}/reject")
def reject_admin_data_flywheel_prelabel(
    sample_id: str,
    prelabel_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """驳回 LLM 预标注，不写入人工真值标签。"""
    try:
        return reject_sample_prelabel(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            prelabel_id=prelabel_id,
            reviewer_id=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
```

- [ ] **Step 7: Map prelabel errors**

Modify `_http_error()`:

```python
status_code = (
    404
    if code in {"SAMPLE_NOT_FOUND", "LABEL_NOT_FOUND", "PRELABEL_NOT_FOUND"}
    else 400
)
```

- [ ] **Step 8: Run API tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/api/test_admin_data_flywheel.py::test_prelabel_endpoint_is_disabled_by_default tests/api/test_admin_data_flywheel.py::test_prelabel_endpoint_creates_pending_llm_judge_prelabel tests/api/test_admin_data_flywheel.py::test_accept_prelabel_endpoint_supports_human_modified_labels tests/api/test_admin_data_flywheel.py::test_reject_prelabel_endpoint_does_not_write_quality_labels -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/core/settings/models.py backend/app/core/settings/settings.py backend/app/core/settings/__init__.py backend/app/core/config.py backend/config.yaml.example backend/app/api/admin_data_flywheel.py backend/tests/api/test_admin_data_flywheel.py
git commit -m "feat: expose data flywheel prelabel api"
```

---

### Task 5: Add Frontend API Types And Client Methods

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/api/dataFlywheel.ts`
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/api/dataFlywheel.test.ts`

- [ ] **Step 1: Write failing API client tests**

Append to `/Users/ljn/Documents/demo/explore/admin-web/src/api/dataFlywheel.test.ts`:

```typescript
it('触发样本 LLM 预标注', async () => {
  mockedApiClient.post.mockResolvedValueOnce({
    data: {
      id: 3,
      sample_id: 'turn:1:s:1',
      source: 'llm_judge',
      status: 'pending',
      labels: ['bad_reply'],
      root_cause: '回复不可验证',
      severity: 'medium',
      confidence: 0.72,
      reason: '证据不足但回复声称完成。',
      recommended_fix: '要求补充证据。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    },
  });

  const result = await createSamplePrelabel('turn:1:s:1');

  expect(mockedApiClient.post).toHaveBeenCalledWith(
    '/admin/data-flywheel/samples/turn%3A1%3As%3A1/prelabel'
  );
  expect(result.source).toBe('llm_judge');
});

it('采纳并可修改样本 LLM 预标注', async () => {
  mockedApiClient.post.mockResolvedValueOnce({
    data: {
      id: 3,
      sample_id: 'turn:1:s:1',
      status: 'accepted',
      labels: ['pending_missed', 'needs_regression'],
      accepted_label_ids: [7, 8],
    },
  });

  const body = {
    labels: ['pending_missed', 'needs_regression'] as const,
    comment: '人工修改后采纳',
  };
  const result = await acceptSamplePrelabel('turn:1:s:1', 3, body);

  expect(mockedApiClient.post).toHaveBeenCalledWith(
    '/admin/data-flywheel/samples/turn%3A1%3As%3A1/prelabels/3/accept',
    body
  );
  expect(result.status).toBe('accepted');
});

it('驳回样本 LLM 预标注', async () => {
  mockedApiClient.post.mockResolvedValueOnce({
    data: {
      id: 3,
      sample_id: 'turn:1:s:1',
      status: 'rejected',
      labels: ['bad_reply'],
    },
  });

  const result = await rejectSamplePrelabel('turn:1:s:1', 3);

  expect(mockedApiClient.post).toHaveBeenCalledWith(
    '/admin/data-flywheel/samples/turn%3A1%3As%3A1/prelabels/3/reject'
  );
  expect(result.status).toBe('rejected');
});
```

Update import block:

```typescript
import {
  acceptSamplePrelabel,
  addSampleLabel,
  createCaseDraft,
  createSamplePrelabel,
  exportSampleJsonl,
  getSampleDetail,
  getSessionReview,
  getDataFlywheelSyncJob,
  getSessionAnnotations,
  listDataFlywheelSamples,
  markBadCase,
  deleteSampleLabel,
  rejectSamplePrelabel,
  resolveSampleLabel,
  syncDataFlywheelSessions,
} from './dataFlywheel';
```

- [ ] **Step 2: Run frontend API tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/admin-web
pnpm exec vitest run src/api/dataFlywheel.test.ts
```

Expected: FAIL because the new client functions do not exist.

- [ ] **Step 3: Add prelabel types**

Modify `/Users/ljn/Documents/demo/explore/admin-web/src/api/dataFlywheel.ts`.

Add label union members currently accepted by backend but missing in frontend:

```typescript
  | 'tool_error_ignored'
  | 'unclear_intent'
```

Add interfaces:

```typescript
export type DataFlywheelPrelabelStatus = 'pending' | 'accepted' | 'rejected' | string;
export type DataFlywheelPrelabelSource = 'llm_judge' | string;

export interface DataFlywheelPrelabel {
  id: number;
  sample_id: string;
  sample_type: string;
  session_id: string | null;
  turn_id: number | null;
  request_id: string | null;
  source: DataFlywheelPrelabelSource;
  status: DataFlywheelPrelabelStatus;
  labels: DataFlywheelLabel[];
  root_cause: string | null;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  confidence: number;
  reason: string;
  recommended_fix: string | null;
  judge_model: string;
  prompt_version: string;
  accepted_label_ids?: number[] | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AcceptPrelabelRequest {
  labels?: DataFlywheelLabel[];
  comment?: string | null;
}
```

Update `DataFlywheelSample`:

```typescript
  prelabels?: DataFlywheelPrelabel[];
  latest_prelabel?: DataFlywheelPrelabel | null;
```

Update `DataFlywheelDetail`:

```typescript
  prelabels: DataFlywheelPrelabel[];
```

- [ ] **Step 4: Add client methods**

Add below `getSampleDetail()`:

```typescript
export async function createSamplePrelabel(sampleId: string): Promise<DataFlywheelPrelabel> {
  const response = await apiClient.post<DataFlywheelPrelabel>(`${samplePath(sampleId)}/prelabel`);
  return response.data;
}

export async function acceptSamplePrelabel(
  sampleId: string,
  prelabelId: number,
  body: AcceptPrelabelRequest
): Promise<DataFlywheelPrelabel> {
  const response = await apiClient.post<DataFlywheelPrelabel>(
    `${samplePath(sampleId)}/prelabels/${prelabelId}/accept`,
    body
  );
  return response.data;
}

export async function rejectSamplePrelabel(
  sampleId: string,
  prelabelId: number
): Promise<DataFlywheelPrelabel> {
  const response = await apiClient.post<DataFlywheelPrelabel>(
    `${samplePath(sampleId)}/prelabels/${prelabelId}/reject`
  );
  return response.data;
}
```

- [ ] **Step 5: Run frontend API tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/admin-web
pnpm exec vitest run src/api/dataFlywheel.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add admin-web/src/api/dataFlywheel.ts admin-web/src/api/dataFlywheel.test.ts
git commit -m "feat: add data flywheel prelabel frontend api"
```

---

### Task 6: Add AI Prejudge Card To Annotation Panel

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx`
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/index.tsx`
- Modify: `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/index.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Add to `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/index.test.tsx` imports:

```typescript
  acceptSamplePrelabel,
  createSamplePrelabel,
  rejectSamplePrelabel,
```

Add to `vi.mock('../../api/dataFlywheel', () => ({ ... }))`:

```typescript
  acceptSamplePrelabel: vi.fn(),
  createSamplePrelabel: vi.fn(),
  rejectSamplePrelabel: vi.fn(),
```

Add mocked constants:

```typescript
const mockedCreatePrelabel = vi.mocked(createSamplePrelabel);
const mockedAcceptPrelabel = vi.mocked(acceptSamplePrelabel);
const mockedRejectPrelabel = vi.mocked(rejectSamplePrelabel);
```

Ensure base `detail` fixture includes:

```typescript
  prelabels: [],
```

Append tests:

```typescript
it('加载样本详情不会自动触发 AI 预标注', async () => {
  render(<DataFlywheel />);

  await userEvent.click(await screen.findByText('王大妈工资100一天'));

  expect(mockedGetDetail).toHaveBeenCalledWith(sample.sample_id);
  expect(mockedCreatePrelabel).not.toHaveBeenCalled();
});

it('显示 AI 预判卡片并可触发预标注', async () => {
  mockedCreatePrelabel.mockResolvedValueOnce({
    id: 9,
    sample_id: sample.sample_id,
    sample_type: 'session_turn',
    session_id: sample.session_id,
    turn_id: sample.turn_id,
    request_id: sample.request_id,
    source: 'llm_judge',
    status: 'pending',
    labels: ['bad_reply', 'pending_missed'],
    root_cause: '写操作缺少 pending 确认',
    severity: 'high',
    confidence: 0.86,
    reason: '回复声称已安排，但没有完整 pending lifecycle。',
    recommended_fix: '写操作执行前必须创建 pending plan。',
    judge_model: 'fake-judge',
    prompt_version: 'data-flywheel-prelabel-v1',
  });
  render(<DataFlywheel />);

  await userEvent.click(await screen.findByText('王大妈工资100一天'));
  await userEvent.click(await screen.findByRole('button', { name: 'AI 预判' }));

  expect(mockedCreatePrelabel).toHaveBeenCalledWith(sample.sample_id);
  expect(await screen.findByText('写操作缺少 pending 确认')).toBeInTheDocument();
  expect(screen.getByText('bad_reply')).toBeInTheDocument();
});

it('采纳 AI 预判时把建议标签写成人工标签', async () => {
  const detailWithPrelabel = {
    ...detail,
    prelabels: [
      {
        id: 9,
        sample_id: sample.sample_id,
        sample_type: 'session_turn',
        session_id: sample.session_id,
        turn_id: sample.turn_id,
        request_id: sample.request_id,
        source: 'llm_judge',
        status: 'pending',
        labels: ['bad_reply', 'pending_missed'],
        root_cause: '写操作缺少 pending 确认',
        severity: 'high',
        confidence: 0.86,
        reason: '回复声称已安排，但没有完整 pending lifecycle。',
        recommended_fix: '写操作执行前必须创建 pending plan。',
        judge_model: 'fake-judge',
        prompt_version: 'data-flywheel-prelabel-v1',
      },
    ],
  };
  mockedGetDetail.mockResolvedValueOnce(detailWithPrelabel);
  mockedAcceptPrelabel.mockResolvedValueOnce({
    ...detailWithPrelabel.prelabels[0],
    status: 'accepted',
    accepted_label_ids: [7, 8],
  });
  render(<DataFlywheel />);

  await userEvent.click(await screen.findByText('王大妈工资100一天'));
  await userEvent.click(await screen.findByRole('button', { name: '采纳 AI 预判' }));

  expect(mockedAcceptPrelabel).toHaveBeenCalledWith(sample.sample_id, 9, {
    labels: ['bad_reply', 'pending_missed'],
    comment: expect.stringContaining('AI 预判'),
  });
});

it('修改 AI 预判标签后保存为人工标签', async () => {
  const detailWithPrelabel = {
    ...detail,
    prelabels: [
      {
        id: 9,
        sample_id: sample.sample_id,
        sample_type: 'session_turn',
        session_id: sample.session_id,
        turn_id: sample.turn_id,
        request_id: sample.request_id,
        source: 'llm_judge',
        status: 'pending',
        labels: ['bad_reply'],
        root_cause: '回复不可验证',
        severity: 'medium',
        confidence: 0.72,
        reason: '证据不足但回复声称完成。',
        recommended_fix: '要求补充证据。',
        judge_model: 'fake-judge',
        prompt_version: 'data-flywheel-prelabel-v1',
      },
    ],
  };
  mockedGetDetail.mockResolvedValueOnce(detailWithPrelabel);
  mockedAcceptPrelabel.mockResolvedValueOnce({
    ...detailWithPrelabel.prelabels[0],
    status: 'accepted',
    labels: ['needs_regression'],
    accepted_label_ids: [8],
  });
  render(<DataFlywheel />);

  await userEvent.click(await screen.findByText('王大妈工资100一天'));
  const prelabelSelect = await screen.findByLabelText('AI 建议标签');
  await userEvent.click(within(prelabelSelect).getByLabelText('close'));
  await userEvent.click(prelabelSelect);
  await userEvent.click(await screen.findByTitle('需要回归'));
  await userEvent.click(await screen.findByRole('button', { name: '修改后保存' }));

  expect(mockedAcceptPrelabel).toHaveBeenCalledWith(sample.sample_id, 9, {
    labels: ['needs_regression'],
    comment: expect.stringContaining('AI 预判'),
  });
});

it('驳回 AI 预判不会保存人工标签', async () => {
  const detailWithPrelabel = {
    ...detail,
    prelabels: [
      {
        id: 9,
        sample_id: sample.sample_id,
        sample_type: 'session_turn',
        session_id: sample.session_id,
        turn_id: sample.turn_id,
        request_id: sample.request_id,
        source: 'llm_judge',
        status: 'pending',
        labels: ['bad_reply'],
        root_cause: '误判',
        severity: 'low',
        confidence: 0.4,
        reason: '测试用误判。',
        recommended_fix: '无需处理。',
        judge_model: 'fake-judge',
        prompt_version: 'data-flywheel-prelabel-v1',
      },
    ],
  };
  mockedGetDetail.mockResolvedValueOnce(detailWithPrelabel);
  mockedRejectPrelabel.mockResolvedValueOnce({
    ...detailWithPrelabel.prelabels[0],
    status: 'rejected',
  });
  render(<DataFlywheel />);

  await userEvent.click(await screen.findByText('王大妈工资100一天'));
  await userEvent.click(await screen.findByRole('button', { name: '驳回 AI 预判' }));

  expect(mockedRejectPrelabel).toHaveBeenCalledWith(sample.sample_id, 9);
  expect(mockedAddLabel).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run UI tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/admin-web
pnpm exec vitest run src/pages/DataFlywheel/index.test.tsx
```

Expected: FAIL because UI does not render prelabel controls.

- [ ] **Step 3: Add props and AI card in AnnotationPanel**

Modify `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx`.

Update imports:

```typescript
import { Button, Card, Input, Radio, Select, Space, Tag, Typography, message } from 'antd';
import {
  BranchesOutlined,
  BugOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  RobotOutlined,
  SaveOutlined,
} from '@ant-design/icons';

import type {
  DataFlywheelLabel,
  DataFlywheelLabelRecord,
  DataFlywheelPrelabel,
  DataFlywheelSample,
} from '../../../api/dataFlywheel';
```

Add props:

```typescript
  prelabels?: DataFlywheelPrelabel[];
  prelabeling: boolean;
  reviewingPrelabel: boolean;
  selectedPrelabelLabels: DataFlywheelLabel[];
  onSelectedPrelabelLabelsChange: (labels: DataFlywheelLabel[]) => void;
  onCreatePrelabel: () => void;
  onAcceptPrelabel: () => void;
  onRejectPrelabel: () => void;
```

Inside component:

```typescript
  const latestPrelabel = prelabels?.[0] ?? selectedSample?.latest_prelabel ?? null;
  const pendingPrelabel = latestPrelabel?.status === 'pending' ? latestPrelabel : null;
```

Render the AI card before the quality label block:

```tsx
        <div
          style={{
            border: `1px solid ${palette.borderSoft}`,
            borderRadius: 6,
            padding: 12,
            background: palette.bg,
          }}
        >
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Space size={8}>
                <RobotOutlined style={{ color: palette.primary }} />
                <Typography.Text style={{ color: palette.text }}>AI 预判</Typography.Text>
                {latestPrelabel && <Tag>{latestPrelabel.status}</Tag>}
              </Space>
              <Button
                aria-label="AI 预判"
                icon={<RobotOutlined />}
                disabled={disabled}
                loading={prelabeling}
                onClick={onCreatePrelabel}
              >
                AI 预判
              </Button>
            </Space>

            {latestPrelabel && (
              <>
                <Space size={6} wrap>
                  {latestPrelabel.labels.map((item) => (
                    <Tag key={item}>{labelText[item] ?? item}</Tag>
                  ))}
                  <Tag color={latestPrelabel.severity === 'high' ? 'red' : 'blue'}>
                    {latestPrelabel.severity}
                  </Tag>
                  <Tag>{Math.round(latestPrelabel.confidence * 100)}%</Tag>
                </Space>
                {latestPrelabel.root_cause && (
                  <Typography.Text style={{ color: palette.text }}>
                    {latestPrelabel.root_cause}
                  </Typography.Text>
                )}
                <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                  {latestPrelabel.reason}
                </Typography.Text>
                {latestPrelabel.recommended_fix && (
                  <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                    {latestPrelabel.recommended_fix}
                  </Typography.Text>
                )}
                <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                  {latestPrelabel.judge_model} · {latestPrelabel.prompt_version}
                </Typography.Text>
              </>
            )}

            {pendingPrelabel && (
              <>
                <Select
                  aria-label="AI 建议标签"
                  mode="multiple"
                  value={selectedPrelabelLabels}
                  options={labelOptions}
                  onChange={onSelectedPrelabelLabelsChange}
                  style={{ width: '100%' }}
                />
                <Space wrap>
                  <Button
                    type="primary"
                    loading={reviewingPrelabel}
                    onClick={onAcceptPrelabel}
                  >
                    采纳 AI 预判
                  </Button>
                  <Button loading={reviewingPrelabel} onClick={onAcceptPrelabel}>
                    修改后保存
                  </Button>
                  <Button danger loading={reviewingPrelabel} onClick={onRejectPrelabel}>
                    驳回 AI 预判
                  </Button>
                </Space>
              </>
            )}
          </Space>
        </div>
```

- [ ] **Step 4: Wire actions in DataFlywheel page**

Modify `/Users/ljn/Documents/demo/explore/admin-web/src/pages/DataFlywheel/index.tsx`.

Update imports:

```typescript
  acceptSamplePrelabel,
  createSamplePrelabel,
  rejectSamplePrelabel,
```

Add state:

```typescript
  const [prelabeling, setPrelabeling] = useState(false);
  const [reviewingPrelabel, setReviewingPrelabel] = useState(false);
  const [selectedPrelabelLabels, setSelectedPrelabelLabels] = useState<DataFlywheelLabel[]>([]);
```

In `loadDetail()`, after `setDetail(result)`:

```typescript
      setSelectedPrelabelLabels(result.prelabels[0]?.labels ?? []);
```

In `clearSelection()`:

```typescript
    setSelectedPrelabelLabels([]);
```

Add handlers:

```typescript
  const handleCreatePrelabel = async () => {
    if (!selectedSample) return;
    setPrelabeling(true);
    try {
      const result = await createSamplePrelabel(selectedSample.sample_id);
      setSelectedPrelabelLabels(result.labels);
      message.success('AI 预判已生成');
      await loadDetail(selectedSample);
      await fetchSamples(query);
    } catch {
      message.error('生成 AI 预判失败');
    } finally {
      setPrelabeling(false);
    }
  };

  const handleAcceptPrelabel = async () => {
    if (!selectedSample || !detail?.prelabels[0]) return;
    setReviewingPrelabel(true);
    try {
      await acceptSamplePrelabel(selectedSample.sample_id, detail.prelabels[0].id, {
        labels: selectedPrelabelLabels,
        comment: `AI 预判采纳：${detail.prelabels[0].reason}`,
      });
      message.success('AI 预判已保存为人工标注');
      await loadDetail(selectedSample);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('采纳 AI 预判失败');
    } finally {
      setReviewingPrelabel(false);
    }
  };

  const handleRejectPrelabel = async () => {
    if (!selectedSample || !detail?.prelabels[0]) return;
    setReviewingPrelabel(true);
    try {
      await rejectSamplePrelabel(selectedSample.sample_id, detail.prelabels[0].id);
      message.success('AI 预判已驳回');
      await loadDetail(selectedSample);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('驳回 AI 预判失败');
    } finally {
      setReviewingPrelabel(false);
    }
  };
```

Pass props into `AnnotationPanel`:

```tsx
        prelabels={detail?.prelabels ?? selectedSample?.prelabels ?? []}
        prelabeling={prelabeling}
        reviewingPrelabel={reviewingPrelabel}
        selectedPrelabelLabels={selectedPrelabelLabels}
        onSelectedPrelabelLabelsChange={setSelectedPrelabelLabels}
        onCreatePrelabel={handleCreatePrelabel}
        onAcceptPrelabel={handleAcceptPrelabel}
        onRejectPrelabel={handleRejectPrelabel}
```

- [ ] **Step 5: Run UI tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/admin-web
pnpm exec vitest run src/pages/DataFlywheel/index.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx admin-web/src/pages/DataFlywheel/index.tsx admin-web/src/pages/DataFlywheel/index.test.tsx
git commit -m "feat: add data flywheel ai prelabel card"
```

---

### Task 7: Full Regression And Safety Verification

**Files:**
- Read/verify only unless failures require scoped fixes in files above.

- [ ] **Step 1: Run backend model/service/API tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest \
  tests/test_agent_data_flywheel_models.py \
  tests/services/test_data_flywheel_judge_service.py \
  tests/services/test_data_flywheel_service.py \
  tests/api/test_admin_data_flywheel.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend API and page Vitest tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/admin-web
pnpm exec vitest run \
  src/api/dataFlywheel.test.ts \
  src/pages/DataFlywheel/index.test.tsx \
  src/pages/DataFlywheel/layout.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run lint checks required by project guide**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
ruff check .
ruff format --check .
```

Expected: PASS.

Run:

```bash
cd /Users/ljn/Documents/demo/explore/admin-web
pnpm run lint
```

Expected: PASS.

- [ ] **Step 4: Verify safety boundary manually in test outputs**

Confirm these assertions are present and passing:

```text
test_create_prelabel_does_not_enter_quality_labels_or_case_truth
  detail["quality_labels"] == []
  draft["case_json"]["metadata"]["quality_labels"] == []
  draft["case_json"]["category"] == "data_flywheel"

test_reject_prelabel_keeps_quality_labels_empty
  detail["quality_labels"] == []

test_reject_prelabel_endpoint_does_not_write_quality_labels
  detail["quality_labels"] == []

前端驳回测试
  expect(mockedAddLabel).not.toHaveBeenCalled()
```

- [ ] **Step 5: Final commit if verification fixes were needed**

If Task 7 required scoped fixes, inspect the exact changed files and commit only files listed in this plan:

```bash
cd /Users/ljn/Documents/demo/explore
git status --short
git add backend/app/models/data_flywheel.py backend/app/models/__init__.py backend/alembic/versions/20260612_agent_data_flywheel_prelabels.py backend/app/services/data_flywheel_judge_service.py backend/app/services/data_flywheel_service.py backend/app/api/admin_data_flywheel.py backend/tests/test_agent_data_flywheel_models.py backend/tests/services/test_data_flywheel_judge_service.py backend/tests/services/test_data_flywheel_service.py backend/tests/api/test_admin_data_flywheel.py admin-web/src/api/dataFlywheel.ts admin-web/src/api/dataFlywheel.test.ts admin-web/src/pages/DataFlywheel/index.tsx admin-web/src/pages/DataFlywheel/components/AnnotationPanel.tsx admin-web/src/pages/DataFlywheel/index.test.tsx
git commit -m "fix: enforce data flywheel prelabel safety boundary"
```

If no files changed in Task 7, do not create an empty commit.

## Final Acceptance Checklist

- [ ] `agent_data_flywheel_prelabels` stores `llm_judge` output separately from human truth.
- [ ] Judge input includes sample detail plus debug evidence: messages, router decision, tool events, pending lifecycle, source, debug export.
- [ ] Judge output includes labels, root cause, severity, confidence, reason, recommended fix.
- [ ] `POST /admin/data-flywheel/samples/{sample_id}/prelabel` creates a pending prelabel.
- [ ] `POST /admin/data-flywheel/samples/{sample_id}/prelabels/{id}/accept` writes human labels and links accepted label ids.
- [ ] `POST /admin/data-flywheel/samples/{sample_id}/prelabels/{id}/reject` only updates prelabel status.
- [ ] Frontend shows AI 预判 card with labels/root cause/severity/confidence/reason/recommended fix/model/prompt version.
- [ ] Frontend supports AI 预判, 采纳 AI 预判, 修改后保存, 驳回 AI 预判.
- [ ] Unaccepted or rejected `llm_judge` never enters `quality_labels`.
- [ ] Unaccepted or rejected `llm_judge` never enters regression/SFT truth.
- [ ] Backend service/API tests and frontend Vitest tests pass.

## Execution Notes

- This plan intentionally keeps `llm_judge` in a separate table instead of adding `source="llm_judge"` rows to `agent_data_flywheel_labels`; that makes the safety boundary visible in schema and query code.
- The initial API factory returns `JUDGE_CLIENT_NOT_CONFIGURED` until wired to the project’s real LLM gateway. Tests monkeypatch the factory, so all MVP behavior is executable without network calls.
- When implementing with active dirty files, run `git diff -- backend/app/services/data_flywheel_service.py` or the exact target file before editing and preserve unrelated changes.
