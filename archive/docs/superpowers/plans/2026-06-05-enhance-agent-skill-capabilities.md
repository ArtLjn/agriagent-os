# Enhance Agent Skill Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Agent 能把“修改玉米茬口9月1开始”稳定识别为已有茬口更新待确认动作，并建立第一期 Skill 元数据、结构化确认、上下文依赖和回归评测基础。

**Architecture:** 第一期采用兼容式演进：在现有 skillify Skill 之上增加本地 metadata adapter，不重写 SkillManager；Tool Executor 优先读 metadata，保留现有硬编码写操作列表作为 fallback。新增 `update_crop_cycle` Skill 复用 `cycle_service` 和 `CropCycleCreate`，pending action 先增加结构化 context 字段并继续生成旧文本，避免移动端和 Playground 立即破坏。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, skillify, LangChain StructuredTool, pytest, OpenSpec。

---

## File Structure

第一期只覆盖 OpenSpec `enhance-agent-skill-capabilities` 的主链路，不实现完整作业单更新和工资结算。相关文件职责如下：

- Create: `backend/app/agent/skills/metadata.py`
  - 定义 `SkillMetadata`、`SkillPermissionLevel`、`SkillRiskLevel`、`ConfirmationSchema`、默认 metadata 和 helper。
- Modify: `backend/app/agent/skills/__init__.py`
  - 在 Skill 注册表、admin registry 和 LangChain tool 对象上挂 metadata。
- Modify: `backend/app/api/admin_config.py`
  - `/admin/skills` 返回 metadata 和 metadata completeness。
- Modify: `backend/app/infra/pending_actions.py`
  - `PendingAction` 增加 `confirmation_context`，`build_confirm_message()` 支持结构化确认上下文并兼容旧调用。
- Modify: `backend/app/agent/runtime/tool_executor.py`
  - Tool Executor 用 metadata 判断 `write_confirm`，保留 `is_write_skill()` fallback。
- Modify: `backend/app/agent/executor/pending_actions.py`
  - 确认执行后基于 metadata 清理缓存，决策 metadata 返回结构化确认上下文。
- Create: `backend/app/agent/skills/update-crop-cycle/skill.md`
  - 新增更新茬口 Skill 文档。
- Create: `backend/app/agent/skills/update-crop-cycle/__init__.py`
  - skillify 包入口。
- Create: `backend/app/agent/skills/update-crop-cycle/scripts/main.py`
  - 实现 `UpdateCropCycleSkill`。
- Modify: `backend/app/context/policy.py`
  - 为 `update_crop_cycle` 选择 `CycleSelector`，并记录 metadata dependency。
- Modify: `backend/app/context/models.py`
  - 若现有 metadata 足够则不改；只在需要记录 `dependency_source` 时改。
- Modify: `backend/app/evaluation/metrics/models.py`
  - 扩展 skill quality 指标字段。
- Modify: `backend/app/evaluation/metrics/skill_quality.py`
  - 统计 unnecessary clarification、execution consistency 等第一期指标。
- Test: `backend/tests/skills/test_skill_metadata.py`
- Test: `backend/tests/skills/test_update_crop_cycle.py`
- Test: `backend/tests/agent/test_tool_executor_metadata.py`
- Test: `backend/tests/test_pending_actions.py`
- Test: `backend/tests/context/test_policy.py`
- Test: `backend/tests/evaluation/test_metrics.py`
- Test: `backend/tests/agent/test_update_crop_cycle_flow.py`

---

### Task 1: Skill Metadata Contract

**Files:**
- Create: `backend/app/agent/skills/metadata.py`
- Modify: `backend/app/agent/skills/__init__.py`
- Modify: `backend/app/api/admin_config.py`
- Test: `backend/tests/skills/test_skill_metadata.py`

- [ ] **Step 1: Write failing metadata tests**

Create `backend/tests/skills/test_skill_metadata.py`:

```python
"""Skill metadata contract tests。"""

from app.agent.skills.metadata import (
    SkillMetadata,
    SkillPermissionLevel,
    SkillRiskLevel,
    get_skill_metadata,
)


class _ReadSkill:
    def name(self):
        return "get_farm_status"


class _WriteSkill:
    def name(self):
        return "create_cost_record"


class _CustomSkill:
    def name(self):
        return "custom_admin_task"

    def metadata(self):
        return {
            "permission_level": "admin",
            "risk_level": "high",
            "context_dependencies": ["farm", "ledger"],
            "cache_invalidation": ["get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["farm_id"],
                "changed_fields": ["status"],
                "inferred_fields": [],
                "editable_fields": ["status"],
            },
            "evaluation_tags": ["admin"],
        }


def test_default_read_skill_metadata():
    metadata = get_skill_metadata(_ReadSkill())

    assert metadata.permission_level == SkillPermissionLevel.READ
    assert metadata.risk_level == SkillRiskLevel.LOW
    assert metadata.metadata_incomplete is True


def test_default_write_skill_metadata():
    metadata = get_skill_metadata(_WriteSkill())

    assert metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM
    assert metadata.risk_level == SkillRiskLevel.MEDIUM
    assert "get_farm_status" in metadata.cache_invalidation
    assert metadata.metadata_incomplete is True


def test_custom_metadata_is_parsed():
    metadata = get_skill_metadata(_CustomSkill())

    assert isinstance(metadata, SkillMetadata)
    assert metadata.permission_level == SkillPermissionLevel.ADMIN
    assert metadata.risk_level == SkillRiskLevel.HIGH
    assert metadata.context_dependencies == ["farm", "ledger"]
    assert metadata.metadata_incomplete is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && poetry run pytest tests/skills/test_skill_metadata.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.agent.skills.metadata'`。

- [ ] **Step 3: Implement metadata model**

Create `backend/app/agent/skills/metadata.py`:

```python
"""Skill runtime metadata。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.compat import StrEnum
from app.infra.pending_actions import WRITE_SKILLS, get_cache_groups_for_skill


class SkillPermissionLevel(StrEnum):
    """Skill 执行权限等级。"""

    READ = "read"
    WRITE_CONFIRM = "write_confirm"
    ADMIN = "admin"
    EXTERNAL_NETWORK = "external_network"


class SkillRiskLevel(StrEnum):
    """Skill 风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfirmationSchema(BaseModel):
    """写操作确认展示字段。"""

    target_fields: list[str] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    editable_fields: list[str] = Field(default_factory=list)


class SkillMetadata(BaseModel):
    """Skill runtime metadata。"""

    permission_level: SkillPermissionLevel = SkillPermissionLevel.READ
    risk_level: SkillRiskLevel = SkillRiskLevel.LOW
    context_dependencies: list[str] = Field(default_factory=list)
    cache_invalidation: list[str] = Field(default_factory=list)
    confirmation_schema: ConfirmationSchema = Field(default_factory=ConfirmationSchema)
    evaluation_tags: list[str] = Field(default_factory=list)
    metadata_incomplete: bool = False


_DEFAULT_WRITE_CONFIRMATION = ConfirmationSchema(
    target_fields=["skill_name"],
    changed_fields=["params"],
    inferred_fields=["original_input"],
    editable_fields=["params"],
)


def get_skill_metadata(skill: Any) -> SkillMetadata:
    """从 Skill 读取 metadata，缺失时提供兼容默认值。"""
    raw_metadata = _call_metadata(skill)
    if raw_metadata is not None:
        metadata = SkillMetadata.model_validate(raw_metadata)
        metadata.metadata_incomplete = False
        return metadata

    skill_name = _get_skill_name(skill)
    if skill_name in WRITE_SKILLS:
        return SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            risk_level=SkillRiskLevel.MEDIUM,
            cache_invalidation=get_cache_groups_for_skill(skill_name),
            confirmation_schema=_DEFAULT_WRITE_CONFIRMATION,
            evaluation_tags=["write"],
            metadata_incomplete=True,
        )

    permission = (
        SkillPermissionLevel.EXTERNAL_NETWORK
        if skill_name in {"web_search", "weather"}
        else SkillPermissionLevel.READ
    )
    return SkillMetadata(
        permission_level=permission,
        risk_level=SkillRiskLevel.LOW,
        evaluation_tags=["read"],
        metadata_incomplete=True,
    )


def metadata_to_dict(skill: Any) -> dict[str, Any]:
    """返回可序列化 metadata。"""
    return get_skill_metadata(skill).model_dump(mode="json")


def _call_metadata(skill: Any) -> dict[str, Any] | None:
    metadata_fn = getattr(skill, "metadata", None)
    if metadata_fn is None:
        return None
    metadata = metadata_fn()
    return dict(metadata) if metadata else None


def _get_skill_name(skill: Any) -> str:
    name_attr = getattr(skill, "name", None)
    if callable(name_attr):
        return str(name_attr())
    return str(name_attr or "")


__all__ = [
    "ConfirmationSchema",
    "SkillMetadata",
    "SkillPermissionLevel",
    "SkillRiskLevel",
    "get_skill_metadata",
    "metadata_to_dict",
]
```

- [ ] **Step 4: Attach metadata to LangChain tools and registry**

Modify `backend/app/agent/skills/__init__.py`:

```python
# add import near top
from app.agent.skills.metadata import get_skill_metadata, metadata_to_dict
```

Inside `skills_to_langchain_tools()`, replace the direct `tools.append(StructuredTool(...))` block with:

```python
        tool = StructuredTool(
            name=skill.name(),
            description=skill.description(),
            args_schema=args_schema,
            func=_make_sync_fn(skill, farm_id=farm_id, farm_uid=farm_uid),
            coroutine=_make_async_fn(skill, farm_id=farm_id, farm_uid=farm_uid),
        )
        setattr(tool, "skill_metadata", get_skill_metadata(skill))
        tools.append(tool)
```

Inside `_build_registry()`, after `registry[skill.name()] = skill`, add:

```python
                setattr(skill, "skill_metadata", get_skill_metadata(skill))
```

- [ ] **Step 5: Expose metadata in admin skill API**

Modify `backend/app/api/admin_config.py`:

```python
# add import
from app.agent.skills.metadata import metadata_to_dict
```

In `list_skills()`, add `"metadata": metadata_to_dict(skill)`:

```python
                {
                    "name": skill.name(),
                    "description": skill.description(),
                    "parameters_schema": skill.parameters_schema(),
                    "metadata": metadata_to_dict(skill),
                    "status": "active",
                }
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd backend && poetry run pytest tests/skills/test_skill_metadata.py -v
```

Expected: PASS。

Commit:

```bash
git add backend/app/agent/skills/metadata.py backend/app/agent/skills/__init__.py backend/app/api/admin_config.py backend/tests/skills/test_skill_metadata.py
git commit -m "feat: add skill metadata contract"
```

---

### Task 2: Metadata-Driven Tool Executor and Cache Invalidation

**Files:**
- Modify: `backend/app/agent/runtime/tool_executor.py`
- Modify: `backend/app/agent/executor/pending_actions.py`
- Test: `backend/tests/agent/test_tool_executor_metadata.py`
- Test: `backend/tests/agent/test_pending_action_executor.py`

- [ ] **Step 1: Write failing Tool Executor metadata tests**

Create `backend/tests/agent/test_tool_executor_metadata.py`:

```python
"""Tool Executor metadata behavior tests。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_actions import get_pending, remove_pending


@pytest.fixture(autouse=True)
def clean_pending():
    remove_pending(1)
    yield
    remove_pending(1)


def _tool(name: str, permission: SkillPermissionLevel):
    tool = MagicMock()
    tool.name = name
    tool.args_schema = None
    tool.ainvoke = AsyncMock(return_value="ok")
    tool.skill_metadata = SkillMetadata(permission_level=permission)
    return tool


@pytest.mark.asyncio
async def test_metadata_write_confirm_creates_pending_action():
    write_tool = _tool("update_crop_cycle", SkillPermissionLevel.WRITE_CONFIRM)

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[write_tool],
    ), patch("app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()):
        result = await _parallel_tool_node(
            {
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "update_crop_cycle",
                                "args": {"cycle_id": 2, "start_date": "2026-09-01"},
                                "id": "tc-1",
                            }
                        ],
                    )
                ],
            }
        )

    message = result["messages"][0]
    assert isinstance(message, ToolMessage)
    assert "PENDING_ACTION" in message.content
    assert get_pending(1).skill_name == "update_crop_cycle"
    write_tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_metadata_read_skill_executes_immediately():
    read_tool = _tool("get_farm_status", SkillPermissionLevel.READ)

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[read_tool],
    ), patch("app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()):
        result = await _parallel_tool_node(
            {
                "farm_id": 1,
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "get_farm_status",
                                "args": {},
                                "id": "tc-1",
                            }
                        ],
                    )
                ],
            }
        )

    assert result["messages"][0].content == "ok"
    read_tool.ainvoke.assert_awaited_once_with({})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_tool_executor_metadata.py -v
```

Expected: FAIL because `update_crop_cycle` is not in `WRITE_SKILLS` and metadata is not used。

- [ ] **Step 3: Add metadata permission helper in Tool Executor**

Modify `backend/app/agent/runtime/tool_executor.py` imports:

```python
from app.agent.skills.metadata import SkillPermissionLevel, get_skill_metadata
```

Add helper before `_parallel_tool_node()`:

```python
def _requires_confirmation(tool, skill_name: str) -> bool:
    """判断工具是否需要 pending action 确认。"""
    metadata = getattr(tool, "skill_metadata", None)
    if metadata is None and tool is not None:
        metadata = get_skill_metadata(tool)
    if metadata is not None:
        return metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM
    return is_write_skill(skill_name)
```

Replace:

```python
        if is_write_skill(name):
```

with:

```python
        if _requires_confirmation(tool, name):
```

In the trace record for pending action, change `output_data` to:

```python
                output_data={
                    "status": "pending_action_created",
                    "permission_level": getattr(
                        getattr(tool, "skill_metadata", None),
                        "permission_level",
                        None,
                    ),
                },
```

- [ ] **Step 4: Use metadata cache invalidation in pending action executor**

Modify `backend/app/agent/executor/pending_actions.py` imports:

```python
from app.agent.skills.metadata import get_skill_metadata
```

Add helper:

```python
def _get_cache_groups_from_metadata(skill_name: str, farm_id: int, farm_uid: str | None) -> list[str]:
    """从 Skill metadata 获取缓存失效组，失败时回退旧映射。"""
    try:
        tool_map = {
            tool.name: tool
            for tool in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
        }
        tool = tool_map.get(skill_name)
        if tool is not None:
            metadata = getattr(tool, "skill_metadata", None) or get_skill_metadata(tool)
            if metadata.cache_invalidation:
                return list(metadata.cache_invalidation)
    except Exception:
        logger.exception("读取 Skill metadata 缓存失效组失败")
    return get_cache_groups_for_skill(skill_name)
```

Change `_clear_write_skill_caches()` signature:

```python
def _clear_write_skill_caches(
    skill_name: str,
    farm_id: int,
    farm_uid: str | None = None,
) -> list[str]:
```

Replace the loop source:

```python
    for group in _get_cache_groups_from_metadata(skill_name, farm_id, farm_uid):
```

Change caller in `_confirm_pending()`:

```python
    cleared_groups = _clear_write_skill_caches(
        pending.skill_name,
        farm_id,
        farm_uid=farm_uid,
    )
```

- [ ] **Step 5: Update existing pending action cache test**

In `backend/tests/agent/test_pending_action_executor.py`, update `test_handle_pending_clears_cache_groups_for_write_skill()` patch block to include `get_langchain_tools` returning an empty list so fallback remains deterministic:

```python
    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute, patch(
        "app.agent.executor.pending_actions.get_langchain_tools",
        return_value=[],
    ), patch(
        "app.agent.executor.pending_actions.clear_skill_cache",
        return_value=2,
    ) as mock_clear:
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_tool_executor_metadata.py tests/agent/test_pending_action_executor.py -v
```

Expected: PASS。

Commit:

```bash
git add backend/app/agent/runtime/tool_executor.py backend/app/agent/executor/pending_actions.py backend/tests/agent/test_tool_executor_metadata.py backend/tests/agent/test_pending_action_executor.py
git commit -m "feat: drive tool execution from skill metadata"
```

---

### Task 3: Structured Pending Action Context

**Files:**
- Modify: `backend/app/infra/pending_actions.py`
- Test: `backend/tests/test_pending_actions.py`

- [ ] **Step 1: Write failing structured confirmation tests**

Append to `backend/tests/test_pending_actions.py`:

```python
from app.infra.pending_actions import build_confirm_message, build_confirmation_context


def test_build_confirmation_context_for_crop_cycle_update():
    context = build_confirmation_context(
        "update_crop_cycle",
        {
            "cycle_id": 9,
            "cycle_name": "夏季玉米",
            "start_date": "2026-09-01",
            "old_start_date": "2026-06-05",
            "crop_name": "玉米",
        },
        original_input="修改玉米茬口9月1开始",
    )

    assert context["target"]["name"] == "夏季玉米"
    assert context["changes"][0]["field"] == "start_date"
    assert context["changes"][0]["old"] == "2026-06-05"
    assert context["changes"][0]["new"] == "2026-09-01"
    assert "start_date" in context["editable_fields"]


def test_confirm_message_includes_crop_cycle_date_diff():
    message = build_confirm_message(
        "update_crop_cycle",
        {
            "cycle_id": 9,
            "cycle_name": "夏季玉米",
            "start_date": "2026-09-01",
            "old_start_date": "2026-06-05",
            "crop_name": "玉米",
        },
        original_input="修改玉米茬口9月1开始",
    )

    assert "夏季玉米" in message
    assert "2026-06-05" in message
    assert "2026-09-01" in message
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && poetry run pytest tests/test_pending_actions.py::test_build_confirmation_context_for_crop_cycle_update tests/test_pending_actions.py::test_confirm_message_includes_crop_cycle_date_diff -v
```

Expected: FAIL because `build_confirmation_context` does not exist。

- [ ] **Step 3: Add confirmation context to PendingAction**

In `backend/app/infra/pending_actions.py`, update `PendingAction`:

```python
    confirmation_context: dict | None = None
```

Update `store_pending()` signature:

```python
    confirmation_context: dict | None = None,
```

Set field when constructing `PendingAction`:

```python
        confirmation_context=confirmation_context,
```

- [ ] **Step 4: Implement confirmation context builder**

Add below `PENDING_MARKER`:

```python
def build_confirmation_context(
    skill_name: str,
    params: dict,
    original_input: str = "",
) -> dict:
    """构建结构化确认上下文。"""
    if skill_name == "update_crop_cycle":
        return {
            "skill_name": skill_name,
            "original_input": original_input,
            "target": {
                "type": "crop_cycle",
                "id": params.get("cycle_id"),
                "name": params.get("cycle_name") or params.get("crop_name") or "茬口",
            },
            "changes": [
                {
                    "field": "start_date",
                    "label": "开始日期",
                    "old": params.get("old_start_date"),
                    "new": params.get("start_date"),
                }
            ],
            "inferred_fields": {
                "crop_name": params.get("crop_name"),
                "start_date": params.get("start_date"),
            },
            "risk_notes": [],
            "editable_fields": ["start_date", "season", "batch_note"],
        }

    return {
        "skill_name": skill_name,
        "original_input": original_input,
        "target": {"type": skill_name, "name": _SKILL_DISPLAY.get(skill_name, skill_name)},
        "changes": [{"field": key, "old": None, "new": value} for key, value in params.items()],
        "inferred_fields": {},
        "risk_notes": [],
        "editable_fields": list(params.keys()),
    }
```

- [ ] **Step 5: Update confirm message to use context**

At the start of `build_confirm_message()`, add:

```python
    context = build_confirmation_context(skill_name, params, original_input)
    if skill_name == "update_crop_cycle":
        target = context["target"]["name"]
        change = context["changes"][0]
        lines = [
            f"🔄 确认修改茬口：{target}",
            f"{change['label']}：{change['old']} → {change['new']}",
        ]
        if original_input:
            lines.append(f"理解：您说的是「{original_input}」")
        lines.append("确认吗？")
        return "\n".join(lines)
```

Add `build_confirmation_context` to `__all__`。

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd backend && poetry run pytest tests/test_pending_actions.py -v
```

Expected: PASS。

Commit:

```bash
git add backend/app/infra/pending_actions.py backend/tests/test_pending_actions.py
git commit -m "feat: add structured pending action context"
```

---

### Task 4: update_crop_cycle Skill

**Files:**
- Create: `backend/app/agent/skills/update-crop-cycle/skill.md`
- Create: `backend/app/agent/skills/update-crop-cycle/__init__.py`
- Create: `backend/app/agent/skills/update-crop-cycle/scripts/main.py`
- Test: `backend/tests/skills/test_update_crop_cycle.py`

- [ ] **Step 1: Write failing Skill tests**

Create `backend/tests/skills/test_update_crop_cycle.py`:

```python
"""update_crop_cycle Skill tests。"""

import importlib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from skillify.core.context import SkillContext

_mod = importlib.import_module("app.agent.skills.update-crop-cycle.scripts.main")
UpdateCropCycleSkill = _mod.UpdateCropCycleSkill


def _cycle(cycle_id=9, name="夏季玉米", start_date=date(2026, 6, 5)):
    cycle = MagicMock()
    cycle.id = cycle_id
    cycle.name = name
    cycle.crop_template_id = 3
    cycle.start_date = start_date
    cycle.field_name = "东地"
    cycle.total_area_mu = None
    cycle.season = "夏季"
    cycle.batch_note = None
    cycle.status = "active"
    return cycle


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def test_metadata_declares_write_confirm():
    metadata = UpdateCropCycleSkill().metadata()

    assert metadata["permission_level"] == "write_confirm"
    assert "crop_cycle" in metadata["cache_invalidation"]
    assert "active_cycles" in metadata["context_dependencies"]


def test_parameters_schema_supports_start_date_and_crop_name():
    schema = UpdateCropCycleSkill().parameters_schema()

    assert "start_date" in schema["properties"]
    assert "crop_name" in schema["properties"]
    assert "cycle_id" in schema["properties"]
    assert "cycle_id" not in schema["required"]


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
async def test_update_by_cycle_id_recalculates_existing_cycle(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    existing = _cycle()
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    result = await UpdateCropCycleSkill().execute(
        {"cycle_id": 9, "start_date": "2026-09-01"},
        ctx,
    )

    assert result.status.value == "success"
    assert "2026-06-05" in result.reply
    assert "2026-09-01" in result.reply
    assert existing.start_date == date(2026, 9, 1)
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
async def test_update_by_unique_crop_name(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    query = mock_db.query.return_value.filter.return_value
    query.order_by.return_value.all.return_value = [_cycle()]

    result = await UpdateCropCycleSkill().execute(
        {"crop_name": "玉米", "start_date": "2026-09-01"},
        ctx,
    )

    assert result.status.value == "success"
    assert "夏季玉米" in result.reply


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
async def test_multiple_matches_need_clarify(mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    query = mock_db.query.return_value.filter.return_value
    query.order_by.return_value.all.return_value = [
        _cycle(1, "夏季玉米"),
        _cycle(2, "秋季玉米"),
    ]

    result = await UpdateCropCycleSkill().execute(
        {"crop_name": "玉米", "start_date": "2026-09-01"},
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "夏季玉米" in result.reply
    assert "秋季玉米" in result.reply
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && poetry run pytest tests/skills/test_update_crop_cycle.py -v
```

Expected: FAIL with import error for missing Skill package。

- [ ] **Step 3: Add Skill package files**

Create `backend/app/agent/skills/update-crop-cycle/__init__.py`:

```python
"""更新茬口 Skill package。"""
```

Create `backend/app/agent/skills/update-crop-cycle/skill.md`:

```markdown
---
name: update_crop_cycle
description: 修改已有种植茬口的开始日期、季节、名称、地块、面积或备注。用户明确说修改、调整、改成、推迟、提前、更正已有茬口时使用。
---

# 修改茬口

## 何时使用
- 用户说“修改玉米茬口9月1开始”
- 用户说“把夏季玉米开始日期改到9月1日”
- 用户说“秋季辣椒茬口面积改成3亩”

## 不要使用
- 用户明确要新建茬口时，应使用 `create_crop_cycle`。
- 用户只想推进生长阶段时，应使用 `update_crop_stage`。

## 参数推断
- `cycle_id` 优先使用上下文中明确选中的茬口。
- 没有 `cycle_id` 时用 `crop_name` 匹配活跃或计划中茬口。
- 日期表达如“9月1”按当前年份解析为 `YYYY-09-01`。

## 缺参策略
- 没有可修改字段时追问要改什么。
- 多个茬口匹配时列出候选项让用户选择。

## 确认行为
- 修改前必须展示目标茬口、修改前值、修改后值和推断依据。

## 缓存影响
- 成功后失效 `crop_cycle` 和 `get_farm_status`。

## 示例
- “修改玉米茬口9月1开始” -> `update_crop_cycle(crop_name="玉米", start_date="2026-09-01")`
```

- [ ] **Step 4: Implement Skill**

Create `backend/app/agent/skills/update-crop-cycle/scripts/main.py`:

```python
"""修改茬口 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.context.invalidation import invalidate_farm_context
from app.core.database import SessionLocal
from app.models.cycle import CropCycle
from app.services.cycle_service import _recalculate_stages


class UpdateCropCycleSkill(Skill):
    """修改已有种植茬口。"""

    def name(self) -> str:
        return "update_crop_cycle"

    def description(self) -> str:
        return "修改已有种植茬口的开始日期、季节、名称、地块、面积或备注。"

    def metadata(self) -> dict:
        return {
            "permission_level": "write_confirm",
            "risk_level": "medium",
            "context_dependencies": ["active_cycles"],
            "cache_invalidation": ["crop_cycle", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["cycle_id", "cycle_name"],
                "changed_fields": [
                    "start_date",
                    "season",
                    "name",
                    "field_name",
                    "total_area_mu",
                    "batch_note",
                    "status",
                ],
                "inferred_fields": ["crop_name"],
                "editable_fields": [
                    "start_date",
                    "season",
                    "name",
                    "field_name",
                    "total_area_mu",
                    "batch_note",
                    "status",
                ],
            },
            "evaluation_tags": ["planting", "write", "crop_cycle_update"],
        }

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "要修改的茬口 ID"},
                "crop_name": {"type": "string", "description": "作物名，如玉米"},
                "start_date": {
                    "type": "string",
                    "description": "新的开始日期，格式 YYYY-MM-DD",
                },
                "season": {"type": "string", "description": "新的季节，如秋季"},
                "name": {"type": "string", "description": "新的茬口名称"},
                "field_name": {"type": "string", "description": "新的地块或棚名"},
                "total_area_mu": {"type": "number", "description": "新的面积（亩）"},
                "batch_note": {"type": "string", "description": "批次备注"},
                "status": {"type": "string", "description": "状态，如 active/planned"},
            },
            "required": [],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "修改茬口")
        if context_error:
            return context_error

        updates = _extract_updates(params)
        if not updates:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="请说明要修改茬口的哪项信息，例如开始日期、季节、面积或备注。",
            )

        db = SessionLocal()
        try:
            cycle = _resolve_cycle(db, farm_id, params)
            if isinstance(cycle, SkillResult):
                return cycle

            old_values = {field: getattr(cycle, field) for field in updates}
            for field, value in updates.items():
                setattr(cycle, field, value)

            if "start_date" in updates:
                _recalculate_stages(db, cycle.id)

            db.commit()
            invalidate_farm_context(farm_id)
            db.refresh(cycle)
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=_format_reply(cycle, old_values, updates),
            )
        except Exception as exc:
            db.rollback()
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"修改茬口失败：{exc}",
            )
        finally:
            db.close()


def _extract_updates(params: dict) -> dict:
    updates = {}
    for field in ["season", "name", "field_name", "batch_note", "status"]:
        if params.get(field) not in (None, ""):
            updates[field] = str(params[field]).strip()
    if params.get("start_date"):
        updates["start_date"] = date.fromisoformat(str(params["start_date"]))
    if params.get("total_area_mu") not in (None, ""):
        try:
            updates["total_area_mu"] = Decimal(str(params["total_area_mu"]))
        except (InvalidOperation, ValueError):
            raise ValueError("面积必须是数字")
    return updates


def _resolve_cycle(db, farm_id: int, params: dict):
    cycle_id = params.get("cycle_id")
    if cycle_id:
        cycle = (
            db.query(CropCycle)
            .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
            .first()
        )
        if cycle:
            return cycle
        return SkillResult(status=ResultStatus.NEED_CLARIFY, reply="没有找到这个茬口。")

    crop_name = str(params.get("crop_name") or "").strip()
    if not crop_name:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="请说明要修改哪个作物或哪个茬口。",
        )

    matches = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.name.contains(crop_name))
        .order_by(CropCycle.status, CropCycle.start_date.desc(), CropCycle.id.desc())
        .all()
    )
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply=f"没有找到包含「{crop_name}」的茬口。",
        )
    names = "、".join(f"{item.id}:{item.name}" for item in matches[:5])
    return SkillResult(
        status=ResultStatus.NEED_CLARIFY,
        reply=f"找到多个可能的茬口，请确认要修改哪一个：{names}",
    )


def _format_reply(cycle: CropCycle, old_values: dict, updates: dict) -> str:
    parts = [f"已修改茬口：{cycle.name}"]
    for field, new_value in updates.items():
        old_value = old_values.get(field)
        parts.append(f"{_label(field)}：{old_value} → {new_value}")
    return "\n".join(parts)


def _label(field: str) -> str:
    return {
        "start_date": "开始日期",
        "season": "季节",
        "name": "名称",
        "field_name": "地块",
        "total_area_mu": "面积",
        "batch_note": "备注",
        "status": "状态",
    }.get(field, field)
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd backend && poetry run pytest tests/skills/test_update_crop_cycle.py -v
```

Expected: PASS。

Commit:

```bash
git add backend/app/agent/skills/update-crop-cycle backend/tests/skills/test_update_crop_cycle.py
git commit -m "feat: add crop cycle update skill"
```

---

### Task 5: End-to-End Pending Action Flow for Crop Cycle Update

**Files:**
- Modify: `backend/app/infra/pending_actions.py`
- Modify: `backend/app/agent/runtime/tool_executor.py`
- Test: `backend/tests/agent/test_update_crop_cycle_flow.py`

- [ ] **Step 1: Write failing flow test**

Create `backend/tests/agent/test_update_crop_cycle_flow.py`:

```python
"""update_crop_cycle pending action flow tests。"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_actions import get_pending, remove_pending


@pytest.fixture(autouse=True)
def clean_pending():
    remove_pending(1)
    yield
    remove_pending(1)


@pytest.mark.asyncio
async def test_update_crop_cycle_tool_call_stores_structured_pending_context():
    tool = MagicMock()
    tool.name = "update_crop_cycle"
    tool.args_schema = None
    tool.skill_metadata = SkillMetadata(
        permission_level=SkillPermissionLevel.WRITE_CONFIRM,
        cache_invalidation=["crop_cycle", "get_farm_status"],
    )

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ), patch("app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()):
        result = await _parallel_tool_node(
            {
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "messages": [
                    HumanMessage(content="修改玉米茬口9月1开始"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "update_crop_cycle",
                                "args": {
                                    "cycle_id": 9,
                                    "cycle_name": "夏季玉米",
                                    "crop_name": "玉米",
                                    "old_start_date": "2026-06-05",
                                    "start_date": "2026-09-01",
                                },
                                "id": "tc-1",
                            }
                        ],
                    ),
                ],
            }
        )

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "update_crop_cycle"
    assert pending.confirmation_context["target"]["name"] == "夏季玉米"
    assert pending.confirmation_context["changes"][0]["old"] == "2026-06-05"
    assert pending.confirmation_context["changes"][0]["new"] == "2026-09-01"
    assert "修改茬口" in result["messages"][0].content
```

- [ ] **Step 2: Run flow test to verify failure**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_update_crop_cycle_flow.py -v
```

Expected: FAIL because Tool Executor does not pass `confirmation_context` into `store_pending()`。

- [ ] **Step 3: Store confirmation context from Tool Executor**

Modify `backend/app/agent/runtime/tool_executor.py` imports:

```python
from app.infra.pending_actions import (
    PENDING_MARKER,
    build_confirm_message,
    build_confirmation_context,
    is_write_skill,
    store_pending,
)
```

Before `store_pending(...)`, add:

```python
            confirmation_context = build_confirmation_context(
                name,
                args,
                original_input=original_input,
            )
```

Update `store_pending()` call:

```python
            action_id = store_pending(
                farm_id,
                name,
                args,
                original_input=original_input,
                confirmation_context=confirmation_context,
            )
```

- [ ] **Step 4: Include confirmation context in trace**

In the pending `collector.record()`, update `output_data`:

```python
                output_data={
                    "status": "pending_action_created",
                    "permission_level": str(
                        getattr(
                            getattr(tool, "skill_metadata", None),
                            "permission_level",
                            "",
                        )
                    ),
                    "confirmation_context": confirmation_context,
                },
```

- [ ] **Step 5: Run flow tests and commit**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_update_crop_cycle_flow.py tests/agent/test_tool_executor_metadata.py tests/test_pending_actions.py -v
```

Expected: PASS。

Commit:

```bash
git add backend/app/agent/runtime/tool_executor.py backend/tests/agent/test_update_crop_cycle_flow.py
git commit -m "feat: store structured confirmation context"
```

---

### Task 6: ContextPolicy Dependency for Crop Cycle Update

**Files:**
- Modify: `backend/app/context/policy.py`
- Test: `backend/tests/context/test_policy.py`

- [ ] **Step 1: Write failing ContextPolicy test**

Append to `backend/tests/context/test_policy.py`:

```python
from app.context.policy import ContextBuildRequest, ContextPolicy
from app.context.selectors import CycleSelector


def test_policy_enables_cycle_context_for_update_crop_cycle():
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="agent",
            selected_tool_names=["update_crop_cycle"],
            farm_id=1,
        )
    )

    selector_types = {type(selector) for selector in result.selectors}
    assert CycleSelector in selector_types
    assert result.max_tokens >= 700
```

- [ ] **Step 2: Run test**

Run:

```bash
cd backend && poetry run pytest tests/context/test_policy.py::test_policy_enables_cycle_context_for_update_crop_cycle -v
```

Expected: FAIL if max token budget remains too small or dependency is not explicit。

- [ ] **Step 3: Update ContextPolicy**

Modify `backend/app/context/policy.py`:

```python
    CROP_CYCLE_TOOLS = frozenset({"update_crop_cycle", "create_crop_cycle", "update_crop_stage"})
```

Inside `resolve()` after `selected_tool_names`:

```python
        if selected_tool_names & self.CROP_CYCLE_TOOLS:
            max_tokens = max(max_tokens, 700)
```

If `CycleSelector()` is already in the default selectors list, do not append another. Keep this first phase minimal and let trace diagnostics come later.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
cd backend && poetry run pytest tests/context/test_policy.py -v
```

Expected: PASS。

Commit:

```bash
git add backend/app/context/policy.py backend/tests/context/test_policy.py
git commit -m "feat: reserve cycle context for crop updates"
```

---

### Task 7: Minimal Skill Regression Metrics

**Files:**
- Modify: `backend/app/evaluation/metrics/models.py`
- Modify: `backend/app/evaluation/metrics/skill_quality.py`
- Test: `backend/tests/evaluation/test_metrics.py`

- [ ] **Step 1: Inspect current metric model**

Run:

```bash
cd backend && sed -n '1,220p' app/evaluation/metrics/models.py
```

Expected: `SkillQualityMetrics` exists and currently lacks `unnecessary_clarification_rate` and `execution_consistency_rate`。

- [ ] **Step 2: Write failing metric tests**

Append to `backend/tests/evaluation/test_metrics.py`:

```python
from app.evaluation.cases.schemas import ExpectedSkillCall
from app.evaluation.metrics.skill_quality import compute_skill_quality
from app.evaluation.replay.models import ReplayResult


def test_skill_quality_tracks_unnecessary_clarification():
    result = ReplayResult(
        case_id="crop-update",
        passed=False,
        reply="请问您是想修改现有茬口，还是创建新茬口？",
        expected_skill_calls=[
            ExpectedSkillCall(
                name="update_crop_cycle",
                arguments={"start_date": "2026-09-01"},
            )
        ],
        actual_skill_calls=[],
        expected_writes=[],
        write_confirmations_hit=0,
        errors=["unnecessary_clarification"],
    )

    metrics = compute_skill_quality([result])

    assert metrics.unnecessary_clarification_rate == 1.0


def test_skill_quality_tracks_execution_consistency():
    result = ReplayResult(
        case_id="crop-update",
        passed=False,
        reply="已修改",
        expected_skill_calls=[],
        actual_skill_calls=[],
        expected_writes=[],
        write_confirmations_hit=0,
        errors=["execution_inconsistency"],
    )

    metrics = compute_skill_quality([result])

    assert metrics.execution_consistency_rate == 0.0
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
cd backend && poetry run pytest tests/evaluation/test_metrics.py -v
```

Expected: FAIL because model fields do not exist yet。

- [ ] **Step 4: Extend SkillQualityMetrics**

Modify `backend/app/evaluation/metrics/models.py` `SkillQualityMetrics`:

```python
    unnecessary_clarification_rate: float = 0.0
    execution_consistency_rate: float = 1.0
```

If `SkillQualityMetrics` is a dataclass instead of Pydantic model, add the same fields to the dataclass.

- [ ] **Step 5: Update metric computation**

Modify `backend/app/evaluation/metrics/skill_quality.py` in `compute_skill_quality()`:

```python
    unnecessary_clarification_total = 0
    execution_inconsistency_total = 0
```

Inside the result loop:

```python
        errors = getattr(result, "errors", []) or []
        if "unnecessary_clarification" in errors:
            unnecessary_clarification_total += 1
        if "execution_inconsistency" in errors:
            execution_inconsistency_total += 1
```

Before return:

```python
    result_total = len(results)
    unnecessary_clarification_rate = (
        unnecessary_clarification_total / result_total if result_total else 0.0
    )
    execution_consistency_rate = (
        1.0 - execution_inconsistency_total / result_total if result_total else 1.0
    )
```

Add fields to return:

```python
        unnecessary_clarification_rate=unnecessary_clarification_rate,
        execution_consistency_rate=execution_consistency_rate,
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd backend && poetry run pytest tests/evaluation/test_metrics.py -v
```

Expected: PASS。

Commit:

```bash
git add backend/app/evaluation/metrics/models.py backend/app/evaluation/metrics/skill_quality.py backend/tests/evaluation/test_metrics.py
git commit -m "feat: track skill regression failure modes"
```

---

### Task 8: Integration Verification for User Example

**Files:**
- Modify: `backend/tests/agent/test_update_crop_cycle_flow.py`
- Modify: `backend/tests/skills/test_skill_docs.py`
- No production code unless tests expose a missing registration issue.

- [ ] **Step 1: Add Skill registry test for update_crop_cycle**

Append to `backend/tests/agent/test_update_crop_cycle_flow.py`:

```python
def test_update_crop_cycle_is_registered_with_metadata():
    from app.agent.skills import get_skill_manager
    from app.agent.skills.metadata import get_skill_metadata, SkillPermissionLevel

    manager = get_skill_manager()
    skill = manager.get_skill("update_crop_cycle")

    assert skill is not None
    assert get_skill_metadata(skill).permission_level == SkillPermissionLevel.WRITE_CONFIRM
```

- [ ] **Step 2: Add doc validation expectation**

If `backend/tests/skills/test_skill_docs.py` has an explicit allowlist, add `update-crop-cycle` to the expected skill docs list. If it discovers skill folders dynamically, no change is needed.

- [ ] **Step 3: Run focused regression commands**

Run:

```bash
cd backend && poetry run pytest \
  tests/skills/test_skill_metadata.py \
  tests/skills/test_update_crop_cycle.py \
  tests/agent/test_tool_executor_metadata.py \
  tests/agent/test_update_crop_cycle_flow.py \
  tests/agent/test_pending_action_executor.py \
  tests/test_pending_actions.py \
  tests/context/test_policy.py \
  tests/evaluation/test_metrics.py \
  -v
```

Expected: PASS。

- [ ] **Step 4: Run architecture checks**

Run:

```bash
bash scripts/check-layer-deps.sh
bash scripts/check-guide-sensor-pairing.sh
bash scripts/harness-check.sh
```

Expected: PASS or only pre-existing unrelated failures. If there are failures caused by this change, fix them before committing.

- [ ] **Step 5: Commit verification adjustments**

Commit only if Step 1 or Step 2 changed files:

```bash
git add backend/tests/agent/test_update_crop_cycle_flow.py backend/tests/skills/test_skill_docs.py
git commit -m "test: cover crop cycle update skill registration"
```

---

## Deferred to Phase 2

The OpenSpec change also covers these capabilities, but they are deliberately deferred so Phase 1 remains deliverable:

- `get_operation_work_orders`
- `update_operation_work_order`
- `get_labor_payables`
- `settle_labor_payment`
- Full diagnostics service and admin UI drilldown
- Full database snapshot evaluation suite
- Metadata-driven context dependency tracing for every selector

Phase 2 should start after the Phase 1 focused regression command passes.

---

## Self-Review

Spec coverage:

- `skill-capability-governance`: covered by Tasks 1, 2, 3, 8.
- `planting-skill-operations`: Phase 1 covers `update_crop_cycle`; remaining work order and labor Skills are explicitly deferred.
- `skill-regression-evaluation`: covered minimally by Task 7 and the focused user-example tests; full suite deferred.
- `agent-skill-diagnostics`: trace metadata is improved in Tasks 2 and 5; full diagnostics service deferred.
- Modified `action-skills`: covered by Tasks 3, 4, 5.
- Modified `llm-tool-calling`: covered by Task 2.
- Modified `context-engineering`: covered by Task 6.
- Modified `agent-evaluation-foundation`: covered by Task 7.

Placeholder scan:

- No `TBD`, `TODO`, or “implement later” placeholders are used in task steps.
- Deferred scope is explicit and outside Phase 1.

Type consistency:

- `SkillMetadata.permission_level` uses `SkillPermissionLevel`.
- `store_pending(..., confirmation_context=...)` is introduced before Tool Executor uses it.
- `update_crop_cycle` parameters use `cycle_id`, `crop_name`, `start_date`, `old_start_date`, and `cycle_name` consistently across tests and confirmation context.
