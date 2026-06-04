# Refactor Agent Execution Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 Agent 写操作确认执行入口，让 `agent/application` 成为聊天生命周期所有者，并为后续 Runtime 瘦身与外部 RAG 预留稳定边界。

**Architecture:** 本计划先用测试锁定当前记账 pending action 行为，再把确认/取消/链式执行/缓存失效/trace 统一迁入 `agent/executor`。随后让 `agent/application` 接管聊天编排，旧 `services.agent_service` 只保留兼容委托；Runtime 只做轻量边界准备，不引入长期记忆或 RAG 实现。

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph, LangChain `StructuredTool`, Skillify, pytest, ruff, shell architecture checks.

---

## 文件结构

- 创建 `backend/app/agent/executor/pending_actions.py`：唯一 pending action 执行服务，负责确认、取消、修改、链式动作、缓存失效、trace。
- 修改 `backend/app/agent/executor/models.py`：新增 pending action 结果模型。
- 修改 `backend/app/agent/executor/__init__.py`：导出 pending action 服务。
- 修改 `backend/app/services/agent_service.py`：删除重复 pending action 私有执行逻辑，改为委托 executor；后续作为兼容入口。
- 修改 `backend/app/agent/advisor.py`：删除 Advisor 内重复 pending action 执行逻辑，改为委托 executor。
- 修改 `backend/app/agent/application/chat_use_case.py`：逐步接管非流式与流式聊天生命周期。
- 修改 `backend/app/agent/runtime/tool_executor.py`：保持写操作拦截，确保只创建 pending，不执行确认。
- 修改 `backend/app/agent/runtime/state.py`：如需要，新增可选预构建 runtime 输入字段。
- 修改 `backend/app/agent/runtime/llm_support.py`、`backend/app/agent/runtime/nodes.py`：只做兼容性瘦身入口，不做大规模改写。
- 修改 `backend/app/memory/service.py` 或新增测试：明确长期记忆和检索未配置时为空结果。
- 修改 `scripts/check-layer-deps.sh`：新增 Agent 边界传感器。
- 创建 `backend/tests/agent/test_pending_action_executor.py`：executor 级单元测试。
- 修改 `backend/tests/test_agent_service.py`：兼容入口行为测试改为验证委托。
- 修改 `backend/tests/test_agent_runtime_architecture.py`：新增边界传感器/导入契约测试。
- 创建或修改 `backend/tests/memory/test_memory_service.py`：验证无 RAG 时继续返回空长期记忆/检索。
- 更新 `openspec/changes/refactor-agent-execution-boundaries/tasks.md`：实现过程中逐项勾选。

## Task 1: 建立 Pending Action Executor 结果模型

**Files:**
- Modify: `backend/app/agent/executor/models.py`
- Modify: `backend/app/agent/executor/__init__.py`
- Test: `backend/tests/agent/test_pending_action_executor.py`

- [ ] **Step 1: 写失败测试，验证结果模型可表达 handled/unhandled/confirm/cancel/fail**

在 `backend/tests/agent/test_pending_action_executor.py` 创建文件：

```python
from app.agent.executor import PendingActionDecision


def test_pending_action_decision_factories():
    unhandled = PendingActionDecision.unhandled()
    confirmed = PendingActionDecision.confirmed("已执行：已记账")
    canceled = PendingActionDecision.canceled("已取消操作。")
    failed = PendingActionDecision.failed("执行失败：数据库错误")

    assert unhandled.handled is False
    assert unhandled.status == "unhandled"
    assert confirmed.handled is True
    assert confirmed.status == "confirmed"
    assert confirmed.reply == "已执行：已记账"
    assert canceled.status == "canceled"
    assert failed.status == "failed"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_pending_action_executor.py::test_pending_action_decision_factories -v
```

Expected: FAIL，错误包含 `cannot import name 'PendingActionDecision'`。

- [ ] **Step 3: 实现最小结果模型**

在 `backend/app/agent/executor/models.py` 追加：

```python

PendingActionStatus = Literal[
    "unhandled",
    "confirmed",
    "canceled",
    "modified",
    "failed",
]


@dataclass(frozen=True)
class PendingActionDecision:
    """pending action 处理结果。"""

    handled: bool
    status: PendingActionStatus
    reply: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def unhandled(cls) -> "PendingActionDecision":
        return cls(handled=False, status="unhandled")

    @classmethod
    def confirmed(
        cls, reply: str, metadata: dict[str, Any] | None = None
    ) -> "PendingActionDecision":
        return cls(
            handled=True,
            status="confirmed",
            reply=reply,
            metadata=metadata or {},
        )

    @classmethod
    def canceled(cls, reply: str = "已取消操作。") -> "PendingActionDecision":
        return cls(handled=True, status="canceled", reply=reply)

    @classmethod
    def modified(cls) -> "PendingActionDecision":
        return cls(handled=False, status="modified")

    @classmethod
    def failed(cls, reply: str) -> "PendingActionDecision":
        return cls(handled=True, status="failed", reply=reply)
```

在 `backend/app/agent/executor/__init__.py` 导出：

```python
from app.agent.executor.models import (
    PendingActionDecision,
    ToolExecutionPlan,
    ToolExecutionResult,
)

__all__ = [
    "PendingActionDecision",
    "ToolExecutionPlan",
    "ToolExecutionResult",
    "build_tool_execution_plan",
    "execute_tool_calls",
]
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_pending_action_executor.py::test_pending_action_decision_factories -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/executor/models.py backend/app/agent/executor/__init__.py backend/tests/agent/test_pending_action_executor.py
git commit -m "feat: add pending action decision model"
```

## Task 2: 实现 Executor 级 pending action 统一服务

**Files:**
- Create: `backend/app/agent/executor/pending_actions.py`
- Modify: `backend/app/agent/executor/__init__.py`
- Test: `backend/tests/agent/test_pending_action_executor.py`

- [ ] **Step 1: 写失败测试，验证确认执行 create_cost_record 走统一服务**

在 `backend/tests/agent/test_pending_action_executor.py` 追加：

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.executor.pending_actions import handle_pending_action
from app.infra.pending_actions import get_pending, remove_pending, store_pending


@pytest.mark.asyncio
async def test_handle_pending_confirm_executes_skill_and_removes_pending():
    remove_pending(1)
    store_pending(
        1,
        "create_cost_record",
        {"amount": 100, "category": "化肥", "record_type": "cost"},
        original_input="买了100块化肥",
    )

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.return_value = "已记账：化肥 100元"
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
        )

    assert decision.handled is True
    assert decision.status == "confirmed"
    assert decision.reply == "已执行：已记账：化肥 100元"
    assert get_pending(1) is None
    mock_execute.assert_awaited_once_with(
        farm_id=1,
        skill_name="create_cost_record",
        params={"amount": 100, "category": "化肥", "record_type": "cost"},
        farm_uid="farm-uid-1",
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_pending_action_executor.py::test_handle_pending_confirm_executes_skill_and_removes_pending -v
```

Expected: FAIL，错误包含 `No module named 'app.agent.executor.pending_actions'`。

- [ ] **Step 3: 实现统一服务初版**

创建 `backend/app/agent/executor/pending_actions.py`：

```python
"""Agent Executor pending action 统一执行入口。"""

import logging
import time

from app.agent.executor.models import PendingActionDecision
from app.agent.skills import get_langchain_tools
from app.infra.pending_actions import (
    PendingAction,
    build_confirm_message,
    detect_user_intent,
    get_cache_groups_for_skill,
    get_pending,
    remove_pending,
    store_pending,
)
from app.infra.skill_cache import clear_cache as clear_skill_cache
from app.infra.trace_collector import get_collector

logger = logging.getLogger(__name__)


async def _execute_write_skill(
    farm_id: int,
    skill_name: str,
    params: dict,
    farm_uid: str | None = None,
) -> str:
    """执行已确认的写操作 Skill。"""
    start = time.time()
    error_msg = None
    result_str = ""
    try:
        tool_map = {
            tool.name: tool
            for tool in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
        }
        tool = tool_map.get(skill_name)
        if tool is None:
            return f"未知工具: {skill_name}"
        result = await tool.ainvoke(params)
        result_str = str(result)
        return result_str
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        get_collector().record(
            node_type="skill_call",
            node_name=skill_name,
            input_data=params,
            output_data=result_str or None,
            start_time=start,
            end_time=time.time(),
            error_message=error_msg,
        )


def _clear_write_skill_caches(skill_name: str) -> list[str]:
    """清理写操作影响的只读 Skill 缓存组。"""
    cleared_groups: list[str] = []
    for group in get_cache_groups_for_skill(skill_name):
        cleared = clear_skill_cache(group)
        if cleared:
            logger.info(
                "写操作后清除缓存 | skill=%s group=%s cleared=%d",
                skill_name,
                group,
                cleared,
            )
        cleared_groups.append(group)
    return cleared_groups


def _format_follow_up_intro(skill_name: str, params: dict) -> str:
    if skill_name == "create_crop_cycle":
        crop_name = str(params.get("crop_name") or "").strip()
        return f"现在可以继续创建{crop_name}茬口。" if crop_name else "现在可以继续创建茬口。"
    return "下一步需要继续确认。"


def _extract_missing_template_crop(pending: PendingAction, reply: str) -> str:
    crop_name = str(pending.params.get("crop_name") or "").strip()
    if crop_name:
        return crop_name
    marker = "系统还没有"
    suffix = "模板"
    if marker not in reply or suffix not in reply:
        return ""
    return reply.split(marker, 1)[1].split(suffix, 1)[0].strip()


async def _confirm_pending(
    farm_id: int,
    pending: PendingAction,
    farm_uid: str | None = None,
) -> PendingActionDecision:
    result = await _execute_write_skill(
        farm_id=farm_id,
        skill_name=pending.skill_name,
        params=pending.params,
        farm_uid=farm_uid,
    )
    cleared_groups = _clear_write_skill_caches(pending.skill_name)
    remove_pending(farm_id)

    if (
        pending.skill_name == "create_crop_cycle"
        and "系统还没有" in result
        and "模板" in result
    ):
        crop_name = _extract_missing_template_crop(pending, result)
        if crop_name:
            store_pending(
                farm_id,
                "create_crop_template",
                {"crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
                follow_up_skill_name="create_crop_cycle",
                follow_up_params=dict(pending.params),
                follow_up_original_input=pending.original_input,
            )
            confirm = build_confirm_message(
                "create_crop_template",
                {"crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
            )
            return PendingActionDecision.confirmed(
                f"系统还没有{crop_name}作物模板。创建茬口前需要先创建模板。\n{confirm}",
                metadata={"cache_groups_cleared": cleared_groups},
            )

    if pending.follow_up_skill_name and pending.follow_up_params is not None:
        store_pending(
            farm_id,
            pending.follow_up_skill_name,
            dict(pending.follow_up_params),
            original_input=pending.follow_up_original_input,
        )
        confirm = build_confirm_message(
            pending.follow_up_skill_name,
            pending.follow_up_params,
            original_input=pending.follow_up_original_input,
        )
        intro = _format_follow_up_intro(
            pending.follow_up_skill_name,
            pending.follow_up_params,
        )
        return PendingActionDecision.confirmed(
            f"已执行：{result}\n\n{intro}\n{confirm}",
            metadata={"cache_groups_cleared": cleared_groups},
        )

    return PendingActionDecision.confirmed(
        f"已执行：{result}",
        metadata={"cache_groups_cleared": cleared_groups},
    )


async def handle_pending_action(
    *,
    farm_id: int,
    message: str,
    farm_uid: str | None = None,
) -> PendingActionDecision:
    """处理已有 pending action；无可处理动作时返回 unhandled。"""
    pending = get_pending(farm_id)
    if pending is None:
        return PendingActionDecision.unhandled()

    intent = detect_user_intent(message)
    if intent == "confirm":
        try:
            return await _confirm_pending(farm_id, pending, farm_uid=farm_uid)
        except Exception as exc:
            logger.error(
                "pending action 执行失败 | farm_id=%s | skill=%s | error=%s",
                farm_id,
                pending.skill_name,
                exc,
            )
            remove_pending(farm_id)
            return PendingActionDecision.failed(f"执行失败：{exc}")

    if intent == "cancel":
        remove_pending(farm_id)
        return PendingActionDecision.canceled()

    return PendingActionDecision.modified()


__all__ = ["handle_pending_action"]
```

在 `backend/app/agent/executor/__init__.py` 导出：

```python
from app.agent.executor.pending_actions import handle_pending_action

__all__ = [
    "PendingActionDecision",
    "ToolExecutionPlan",
    "ToolExecutionResult",
    "build_tool_execution_plan",
    "execute_tool_calls",
    "handle_pending_action",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_pending_action_executor.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/executor backend/tests/agent/test_pending_action_executor.py
git commit -m "feat: centralize pending action execution"
```

## Task 3: 补齐 Executor 链式动作、取消、修改和缓存测试

**Files:**
- Modify: `backend/tests/agent/test_pending_action_executor.py`
- Modify: `backend/app/agent/executor/pending_actions.py`

- [ ] **Step 1: 写链式动作、取消、修改、缓存失效测试**

在 `backend/tests/agent/test_pending_action_executor.py` 追加：

```python

@pytest.mark.asyncio
async def test_handle_pending_cancel_removes_pending():
    remove_pending(1)
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    decision = await handle_pending_action(farm_id=1, message="取消")

    assert decision.handled is True
    assert decision.status == "canceled"
    assert decision.reply == "已取消操作。"
    assert get_pending(1) is None


@pytest.mark.asyncio
async def test_handle_pending_modify_leaves_pending_for_llm_replanning():
    remove_pending(1)
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    decision = await handle_pending_action(farm_id=1, message="改成200块")

    assert decision.handled is False
    assert decision.status == "modified"
    assert get_pending(1) is not None
    remove_pending(1)


@pytest.mark.asyncio
async def test_handle_pending_missing_template_creates_template_pending():
    remove_pending(1)
    store_pending(
        1,
        "create_crop_cycle",
        {"crop_name": "小麦"},
        original_input="我想种小麦",
    )

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.return_value = "系统还没有小麦模板，要帮你创建一个吗？"
        decision = await handle_pending_action(farm_id=1, message="确认")

    pending = get_pending(1)
    assert decision.status == "confirmed"
    assert pending is not None
    assert pending.skill_name == "create_crop_template"
    assert pending.follow_up_skill_name == "create_crop_cycle"
    assert "确认创建作物模板" in decision.reply
    remove_pending(1)


@pytest.mark.asyncio
async def test_handle_pending_clears_cache_groups_for_write_skill():
    remove_pending(1)
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute, patch(
        "app.agent.executor.pending_actions.clear_skill_cache",
        return_value=2,
    ) as mock_clear:
        mock_execute.return_value = "已记账"
        decision = await handle_pending_action(farm_id=1, message="确认")

    assert decision.metadata["cache_groups_cleared"] == [
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ]
    assert mock_clear.call_count == 3
```

- [ ] **Step 2: 运行测试确认失败或暴露缺口**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_pending_action_executor.py -v
```

Expected: 如果 Task 2 实现完整则 PASS；如果失败，应只失败在缓存 patch 名称或回复文案不一致。

- [ ] **Step 3: 修正实现到测试通过**

如果缓存 patch 名称失败，确保 `backend/app/agent/executor/pending_actions.py` 使用如下导入：

```python
from app.infra.skill_cache import clear_cache as clear_skill_cache
```

如果需要让测试 patch 更稳定，把测试里的 patch 保持为：

```python
patch("app.agent.executor.pending_actions.clear_skill_cache", return_value=2)
```

并确认 `_clear_write_skill_caches()` 调用的是本模块变量 `clear_skill_cache(group)`。

- [ ] **Step 4: 跑测试**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_pending_action_executor.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/executor/pending_actions.py backend/tests/agent/test_pending_action_executor.py
git commit -m "test: cover pending action executor flows"
```

## Task 4: 让 services.agent_service 委托 Executor pending 服务

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/tests/test_agent_service.py`

- [ ] **Step 1: 修改测试 patch 点，验证兼容入口调用 executor**

在 `backend/tests/test_agent_service.py` 中，把 pending 确认路径的 patch 从：

```python
with patch(
    "app.services.agent_service._execute_pending_action",
    new_callable=AsyncMock,
) as mock_exec:
    mock_exec.return_value = "已记账"
```

改为：

```python
with patch(
    "app.services.agent_service.handle_pending_action",
    new_callable=AsyncMock,
) as mock_pending:
    from app.agent.executor.models import PendingActionDecision

    mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")
```

并在断言中加入：

```python
mock_pending.assert_awaited_once()
```

- [ ] **Step 2: 运行相关测试确认失败**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_service.py::TestChatWithAgent::test_chat_pending_confirm_saves_to_conversation -v
```

Expected: FAIL，因为 `app.services.agent_service.handle_pending_action` 尚未导入或未调用。

- [ ] **Step 3: 修改 service 使用统一 pending executor**

在 `backend/app/services/agent_service.py` 导入：

```python
from app.agent.executor.pending_actions import handle_pending_action
```

在 `chat_with_agent()` 的 pending 分支替换为：

```python
    pending_decision = await handle_pending_action(
        farm_id=farm_id,
        message=message,
    )
    if pending_decision.handled:
        reply = pending_decision.reply
        record = AgentRecord(
            cycle_id=cycle_id,
            record_type="chat",
            content=reply,
            farm_id=farm_id,
        )
        db.add(record)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        if conversation:
            save_message(db, conversation.id, "assistant", reply)
        return ChatResponse(reply=reply)
```

在 `stream_chat_with_agent()` 的 pending 分支替换为：

```python
    pending_decision = await handle_pending_action(
        farm_id=farm_id,
        message=message,
    )
    if pending_decision.handled:
        yield pending_decision.reply
        return
```

删除 `agent_service.py` 中不再使用的 `_execute_pending_action`、`_confirm_pending_action`、`_extract_missing_template_crop`、`_format_follow_up_intro` 以及相关 import。

- [ ] **Step 4: 跑 service 测试**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_service.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/agent_service.py backend/tests/test_agent_service.py
git commit -m "refactor: delegate service pending actions to executor"
```

## Task 5: 让 agent.advisor 委托 Executor pending 服务

**Files:**
- Modify: `backend/app/agent/advisor.py`
- Test: `backend/tests/test_agent_api.py` 或 `backend/tests/agent/test_advisor_pending.py`

- [ ] **Step 1: 写 Advisor 委托测试**

创建 `backend/tests/agent/test_advisor_pending.py`：

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.executor.models import PendingActionDecision
from app.agent.advisor import invoke_advisor
from app.infra.pending_actions import remove_pending, store_pending


@pytest.mark.asyncio
async def test_advisor_delegates_pending_confirm_to_executor():
    remove_pending(1)
    store_pending(1, "create_cost_record", {"amount": 100, "category": "化肥"})

    with patch(
        "app.agent.advisor.handle_pending_action",
        new_callable=AsyncMock,
    ) as mock_pending:
        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")
        reply = await invoke_advisor("确认", farm_id=1)

    assert reply == "已执行：已记账"
    mock_pending.assert_awaited_once_with(
        farm_id=1,
        message="确认",
        farm_uid=None,
    )
    remove_pending(1)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_advisor_pending.py -v
```

Expected: FAIL，因为 `advisor.py` 尚未导入或调用 `handle_pending_action`。

- [ ] **Step 3: 修改 Advisor pending 分支**

在 `backend/app/agent/advisor.py` 导入：

```python
from app.agent.executor.pending_actions import handle_pending_action
```

在 `invoke_advisor()` 中 `farm_uid = _resolve_farm_uid(...)` 后替换 pending 处理为：

```python
    pending_decision = await handle_pending_action(
        farm_id=farm_id,
        message=user_input,
        farm_uid=farm_uid,
    )
    if pending_decision.handled:
        return filter_output(pending_decision.reply)
```

在 `stream_advisor()` 中同样替换为：

```python
    pending_decision = await handle_pending_action(
        farm_id=farm_id,
        message=user_input,
        farm_uid=farm_uid,
    )
    if pending_decision.handled:
        yield filter_output(pending_decision.reply)
        return
```

删除 `advisor.py` 中 `_execute_advisor_pending_action`、`_extract_missing_template_crop`、`_format_follow_up_intro` 以及不再使用的 pending imports。

- [ ] **Step 4: 跑 Advisor 和 service 相关测试**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_advisor_pending.py tests/test_agent_service.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/advisor.py backend/tests/agent/test_advisor_pending.py
git commit -m "refactor: delegate advisor pending actions to executor"
```

## Task 6: 将非流式聊天生命周期迁入 Agent Application

**Files:**
- Modify: `backend/app/agent/application/chat_use_case.py`
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/tests/test_agent_service.py`
- Test: `backend/tests/agent/test_chat_use_case.py`

- [ ] **Step 1: 写 Application use case 测试**

创建 `backend/tests/agent/test_chat_use_case.py`：

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.application.chat_use_case import chat
from app.schemas.agent import ChatRequest


@pytest.mark.asyncio
async def test_chat_use_case_owns_non_streaming_lifecycle():
    db = MagicMock()
    farm = MagicMock()
    farm.id = 1
    farm.user_id = "user-1"

    with patch(
        "app.agent.application.chat_use_case.invoke_advisor",
        new_callable=AsyncMock,
    ) as mock_advisor, patch(
        "app.agent.application.chat_use_case.handle_pending_action",
        new_callable=AsyncMock,
    ) as mock_pending, patch(
        "app.agent.application.chat_use_case._observe_chat_completion",
        new_callable=AsyncMock,
    ) as mock_observe:
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_advisor.return_value = "建议回复"

        result = await chat(
            db,
            ChatRequest(message="今天做什么", session_id=None),
            farm,
            request_id="req-1",
        )

    assert result.reply == "建议回复"
    mock_pending.assert_awaited_once()
    mock_advisor.assert_awaited_once()
    mock_observe.assert_awaited_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_chat_use_case.py::test_chat_use_case_owns_non_streaming_lifecycle -v
```

Expected: FAIL，因为当前 `chat()` 仍调用 `chat_with_agent`，测试 patch 的 `invoke_advisor` 不会被调用。

- [ ] **Step 3: 在 Application 中实现非流式生命周期**

在 `backend/app/agent/application/chat_use_case.py` 增加 imports：

```python
from app.agent.advisor import invoke_advisor
from app.agent.executor.pending_actions import handle_pending_action
from app.services.conversation_service import get_or_create_conversation
```

将 `chat()` 的主体改为直接编排：

```python
    conversation = None
    if chat_request.session_id:
        conversation = get_or_create_conversation(
            db,
            farm.id,
            chat_request.session_id,
            user_id=farm.user_id,
        )
        save_message(db, conversation.id, "user", chat_request.message)

    pending_decision = await handle_pending_action(
        farm_id=farm.id,
        message=chat_request.message,
    )
    if pending_decision.handled:
        reply = pending_decision.reply
    else:
        context = (
            f"【关联周期 ID: {chat_request.cycle_id}】\n"
            if chat_request.cycle_id
            else ""
        )
        reply = await invoke_advisor(
            context + chat_request.message,
            farm_id=farm.id,
            db=db,
            conversation_id=conversation.id if conversation else None,
            session_id=chat_request.session_id or "",
            request_id=request_id,
            user_id=farm.user_id,
        )

    record = AgentRecord(
        cycle_id=chat_request.cycle_id,
        record_type="chat",
        content=reply,
        farm_id=farm.id,
        user_id=farm.user_id,
        conversation_id=conversation.id if conversation else None,
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    if conversation:
        save_message(db, conversation.id, "assistant", reply)

    result = ChatResponse(reply=reply)
    pending_action = build_pending_action_response(farm.id)
    if pending_action:
        result.pending_action = pending_action

    await _observe_chat_completion(
        user_id=farm.user_id or "",
        farm_id=farm.id,
        session_id=chat_request.session_id,
        user_input=chat_request.message,
        assistant_reply=result.reply,
        skills_called=[],
        request_id=request_id,
    )
    return result
```

保留 `services.agent_service.chat_with_agent` 暂时不动，避免同一任务改太多。

- [ ] **Step 4: 跑 Application 测试和 API 聊天测试**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_chat_use_case.py tests/test_agent_api.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/application/chat_use_case.py backend/tests/agent/test_chat_use_case.py
git commit -m "refactor: move non-stream chat lifecycle to application"
```

## Task 7: 将 service 聊天函数改为兼容委托

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/tests/test_agent_service.py`

- [ ] **Step 1: 写兼容委托测试**

在 `backend/tests/test_agent_service.py` 新增测试：

```python
@pytest.mark.asyncio
async def test_chat_with_agent_delegates_to_application_use_case():
    from app.services.agent_service import chat_with_agent

    mock_db = _make_mock_db()
    farm = MagicMock()
    farm.id = 1
    farm.user_id = "user-1"

    with patch(
        "app.services.agent_service._load_farm_for_application",
        return_value=farm,
    ), patch(
        "app.services.agent_service.application_chat",
        new_callable=AsyncMock,
    ) as mock_chat:
        mock_chat.return_value = MagicMock(reply="应用层回复")
        result = await chat_with_agent(
            mock_db,
            "你好",
            farm_id=1,
            session_id="sess-1",
            user_id="user-1",
            request_id="req-1",
        )

    assert result.reply == "应用层回复"
    mock_chat.assert_awaited_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_service.py::test_chat_with_agent_delegates_to_application_use_case -v
```

Expected: FAIL，因为兼容委托函数还不存在。

- [ ] **Step 3: 改造 service 兼容函数**

在 `backend/app/services/agent_service.py` 导入：

```python
from app.agent.application.chat_use_case import chat as application_chat
from app.schemas.agent import ChatRequest
```

新增：

```python
def _load_farm_for_application(db: Session, farm_id: int) -> Farm:
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if farm is None:
        raise ValueError(f"未找到农场: {farm_id}")
    return farm
```

将 `chat_with_agent()` 改为兼容委托：

```python
async def chat_with_agent(
    db: Session,
    message: str,
    farm_id: int,
    cycle_id: int | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    request_id: str = "",
) -> ChatResponse:
    farm = _load_farm_for_application(db, farm_id)
    if user_id and not farm.user_id:
        farm.user_id = user_id
    return await application_chat(
        db,
        ChatRequest(
            message=message,
            cycle_id=cycle_id,
            session_id=session_id,
        ),
        farm,
        request_id=request_id,
    )
```

如果旧测试依赖 `MagicMock.query` 链，先只让新增委托测试通过；旧 service 内部细节测试应逐步迁到 Application 测试。

- [ ] **Step 4: 跑测试并修正旧测试**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_service.py tests/agent/test_chat_use_case.py -v
```

Expected: PASS。若旧测试仍断言 `invoke_advisor` 在 service 内被调用，将其迁移到 `tests/agent/test_chat_use_case.py`，断言 Application 调用 `invoke_advisor`。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/agent_service.py backend/tests/test_agent_service.py backend/tests/agent/test_chat_use_case.py
git commit -m "refactor: make agent service chat a compatibility wrapper"
```

## Task 8: 迁移流式聊天生命周期到 Application

**Files:**
- Modify: `backend/app/agent/application/chat_use_case.py`
- Modify: `backend/app/agent/application/stream_chat_use_case.py`
- Modify: `backend/app/services/agent_service.py`
- Test: `backend/tests/agent/test_chat_use_case.py`

- [ ] **Step 1: 写流式 Application 测试**

在 `backend/tests/agent/test_chat_use_case.py` 追加：

```python

@pytest.mark.asyncio
async def test_stream_chat_events_uses_application_pending_decision():
    from app.agent.application.chat_use_case import stream_chat_events
    from app.agent.executor.models import PendingActionDecision
    from app.models.user import User
    from app.schemas.agent import ChatRequest

    db = MagicMock()
    user = User(id="user-1", phone="1", password_hash="h", status="active")
    farm = MagicMock()
    farm.id = 1
    farm.user_id = "user-1"

    with patch(
        "app.agent.application.chat_use_case.handle_pending_action",
        new_callable=AsyncMock,
    ) as mock_pending, patch(
        "app.agent.application.chat_use_case._observe_chat_completion",
        new_callable=AsyncMock,
    ):
        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")
        events = [
            event
            async for event in stream_chat_events(
                db,
                ChatRequest(message="确认", session_id=None),
                user,
                farm,
                request_id="req-stream",
            )
        ]

    assert any("已执行：已记账" in event for event in events)
    assert events[-1] == "data: [DONE]\n\n"
```

- [ ] **Step 2: 运行测试确认当前行为**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_chat_use_case.py::test_stream_chat_events_uses_application_pending_decision -v
```

Expected: PASS 或 FAIL。如果 PASS，说明已有 `stream_chat_events` 已在 Application 中但仍委托 service；继续 Step 3 收拢 service 依赖。

- [ ] **Step 3: 让 `stream_chat_events` 不再调用 `stream_chat_with_agent`**

在 `backend/app/agent/application/chat_use_case.py` 中，删除 `stream_chat_with_agent` import，并在 `stream_chat_events()` 内使用：

```python
        pending_decision = await handle_pending_action(
            farm_id=farm.id,
            message=chat_request.message,
        )
        if pending_decision.handled:
            full_reply = pending_decision.reply
            data = json.dumps({"content": full_reply}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        else:
            context = (
                f"【关联周期 ID: {chat_request.cycle_id}】\n"
                if chat_request.cycle_id
                else ""
            )
            async for chunk in stream_advisor(
                context + chat_request.message,
                farm_id=farm.id,
                db=db,
                conversation_id=None,
                session_id=chat_request.session_id or "",
                request_id=request_id,
                user_id=user.id,
                call_type="stream_chat",
            ):
                full_reply += chunk
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"
```

保留后续 `_flush_trace_queue()`、`_save_stream_reply()`、`_observe_chat_completion()` 和 pending_action SSE 逻辑。

- [ ] **Step 4: 跑流式测试**

Run:

```bash
cd backend && poetry run pytest tests/agent/test_chat_use_case.py tests/test_agent_api.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/application/chat_use_case.py backend/app/agent/application/stream_chat_use_case.py backend/app/services/agent_service.py backend/tests/agent/test_chat_use_case.py
git commit -m "refactor: move stream chat lifecycle to application"
```

## Task 9: Runtime 边界轻量瘦身，不做大重写

**Files:**
- Modify: `backend/app/agent/runtime/state.py`
- Modify: `backend/app/agent/runtime/nodes.py`
- Test: `backend/tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: 写 Runtime prepared input 架构测试**

在 `backend/tests/test_agent_runtime_architecture.py` 追加：

```python

def test_agent_state_accepts_prepared_runtime_inputs():
    from app.agent.runtime.state import AgentState

    annotations = AgentState.__annotations__

    assert "system_prompt" in annotations
    assert "context_bundle" in annotations
    assert "selected_tool_names" in annotations
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_runtime_architecture.py::test_agent_state_accepts_prepared_runtime_inputs -v
```

Expected: FAIL，缺少字段。

- [ ] **Step 3: 增加可选 prepared runtime 字段**

在 `backend/app/agent/runtime/state.py` 的 `AgentState` 中加入：

```python
    system_prompt: str | None
    context_bundle: object | None
    selected_tool_names: list[str] | None
```

如果 `AgentState` 当前来自 `backend/app/agent/state.py`，则在实际定义文件中加入这些字段，并保持 `runtime/state.py` 兼容导出。

- [ ] **Step 4: 在 nodes 中优先读取 prepared 字段**

在 `backend/app/agent/runtime/nodes.py` 中构建 `system_text` 前加入：

```python
    prepared_system_prompt = state.get("system_prompt")
    prepared_context_bundle = state.get("context_bundle")
    prepared_selected_tool_names = state.get("selected_tool_names")
```

在 selected tools 计算后，允许 prepared tool names 覆盖：

```python
    if prepared_selected_tool_names is not None:
        selected_names = list(prepared_selected_tool_names)
```

在 context 构建处优先使用 prepared bundle：

```python
    if prepared_context_bundle is not None:
        context_bundle = prepared_context_bundle
        farm_ctx = await _get_farm_context(farm_id)
    else:
        context_bundle, farm_ctx = await _get_runtime_context_bundle(
            farm_id=farm_id,
            intent=intent,
            selected_tool_names=selected_tool_names,
            user_id=state.get("user_id"),
            session_id=state.get("session_id"),
        )
```

在 system prompt 处优先使用 prepared prompt：

```python
    if prepared_system_prompt:
        system_text = prepared_system_prompt
    else:
        cached_prompt = prompt_cache.get(farm_id=farm_id, date_str=date_str)
        if cached_prompt is not None:
            system_text = cached_prompt
        else:
            current_season = _get_season(current_date)
            system_text = get_composer().compose(
                "system_base",
                variables={
                    "display_name": display_name,
                    "farm_location": farm_location,
                    "farm_coords": farm_ctx["farm_coords"],
                    "current_season": current_season,
                    "active_crops": farm_ctx["active_crops"],
                },
                current_date=current_date,
            )
            prompt_cache.set(farm_id=farm_id, date_str=date_str, value=system_text)
```

- [ ] **Step 5: 跑 Runtime 测试**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_runtime_architecture.py tests/test_llm_node_dual_phase_retry.py tests/test_tool_selector.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/agent/runtime backend/app/agent/state.py backend/tests/test_agent_runtime_architecture.py
git commit -m "refactor: add prepared runtime inputs"
```

## Task 10: 明确 Memory 不启用 RAG 时的行为

**Files:**
- Modify: `backend/tests/memory/test_memory_service.py`
- Modify: `backend/app/memory/service.py`
- Modify: `docs/architecture/overview.md` 或 `docs/architecture/backend-architecture.md`

- [ ] **Step 1: 写无 RAG 测试**

在 `backend/tests/memory/test_memory_service.py` 追加：

```python
import pytest

from app.memory.schemas import MemorySearchQuery
from app.memory.service import InMemoryMemoryService


@pytest.mark.asyncio
async def test_memory_service_returns_empty_long_term_and_search_without_rag():
    service = InMemoryMemoryService()

    context = await service.build_context(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
    )
    hits = await service.search(
        MemorySearchQuery(
            user_id="user-1",
            farm_id=1,
            query="用户偏好",
            limit=5,
        )
    )

    assert context.long_term.facts == []
    assert context.long_term.preferences == []
    assert hits == []
```

- [ ] **Step 2: 运行测试**

Run:

```bash
cd backend && poetry run pytest tests/memory/test_memory_service.py -v
```

Expected: PASS。如果字段名不匹配，打开 `backend/app/memory/models.py`，把断言改成模型真实字段，但必须继续验证“空长期记忆”和“空检索”。

- [ ] **Step 3: 文档补充外部 RAG 接入点**

在 `docs/architecture/overview.md` 的 Memory 相关段落补充：

```markdown
当前部署不内置 RAG、向量数据库、embedding 模型或重排服务。长期记忆和检索通过 `MemoryService` 端口预留；未配置外部 RAG 服务时返回空上下文或空检索结果，Agent 请求继续执行。后续独立 RAG/memory 服务应通过 `MemoryService.search()` 和 `MemoryService.build_context()` 接入。
```

- [ ] **Step 4: 跑测试**

Run:

```bash
cd backend && poetry run pytest tests/memory/test_memory_service.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/tests/memory/test_memory_service.py docs/architecture/overview.md
git commit -m "docs: clarify memory rag boundary"
```

## Task 11: 增强架构传感器

**Files:**
- Modify: `scripts/check-layer-deps.sh`
- Modify: `backend/tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: 写架构测试，防止重复 pending 执行入口**

在 `backend/tests/test_agent_runtime_architecture.py` 追加：

```python

def test_pending_action_execution_owned_by_executor():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    forbidden_files = [
        app_dir / "services" / "agent_service.py",
        app_dir / "agent" / "advisor.py",
    ]

    forbidden_patterns = [
        "_execute_pending_action",
        "_execute_advisor_pending_action",
        "manager.execute(pending.skill_name",
        "get_langchain_tools(farm_id=farm_id",
    ]

    for file_path in forbidden_files:
        text = file_path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern not in text, f"{file_path} still contains {pattern}"
```

- [ ] **Step 2: 运行测试确认当前状态**

Run:

```bash
cd backend && poetry run pytest tests/test_agent_runtime_architecture.py::test_pending_action_execution_owned_by_executor -v
```

Expected: PASS，如果前面任务已清理旧路径；否则 FAIL，按提示删除重复逻辑。

- [ ] **Step 3: 在 shell 检查中增加同等规则**

在 `scripts/check-layer-deps.sh` 的 Agent 平台边界检查后增加：

```bash
  PENDING_DUP_MATCHES=$(rg -n \
    "_execute_pending_action|_execute_advisor_pending_action|manager\\.execute\\(pending\\.skill_name|get_langchain_tools\\(farm_id=farm_id" \
    "$BACKEND/services/agent_service.py" "$BACKEND/agent/advisor.py" 2>/dev/null || true)
  if [ -n "$PENDING_DUP_MATCHES" ]; then
    echo "$PENDING_DUP_MATCHES"
    echo "❌ ERROR: pending action 执行逻辑只能位于 Agent Executor"
    echo "✅ FIX: 使用 app.agent.executor.pending_actions.handle_pending_action"
    echo "📖 See: openspec/changes/refactor-agent-execution-boundaries/design.md"
    ERRORS=$((ERRORS + 1))
  fi

  APPLICATION_LEGACY_MATCHES=$(rg -n \
    "from app\\.services\\.agent_service import .*chat_with_agent|from app\\.services\\.agent_service import .*stream_chat_with_agent" \
    "$BACKEND/agent/application" 2>/dev/null || true)
  if [ -n "$APPLICATION_LEGACY_MATCHES" ]; then
    echo "$APPLICATION_LEGACY_MATCHES"
    echo "❌ ERROR: Agent Application 不得依赖 services.agent_service 聊天编排"
    echo "✅ FIX: 将生命周期编排保留在 app.agent.application"
    ERRORS=$((ERRORS + 1))
  fi
```

- [ ] **Step 4: 跑架构检查**

Run:

```bash
bash scripts/check-layer-deps.sh
```

Expected: PASS。如果仍因 `backend/app/core/llm_client_manager.py` 超 500 行失败，记录为已有技术债；本 change 必须至少确保 `backend/app/services/agent_service.py` 不再超 500 行。

- [ ] **Step 5: 提交**

```bash
git add scripts/check-layer-deps.sh backend/tests/test_agent_runtime_architecture.py
git commit -m "test: enforce agent execution boundaries"
```

## Task 12: 最终回归和 OpenSpec 勾选

**Files:**
- Modify: `openspec/changes/refactor-agent-execution-boundaries/tasks.md`

- [ ] **Step 1: 跑格式和 lint**

Run:

```bash
cd backend && poetry run ruff check . && poetry run ruff format .
```

Expected: PASS，或 format 修改文件后重新运行 `poetry run ruff check .` PASS。

- [ ] **Step 2: 跑重点测试**

Run:

```bash
cd backend && poetry run pytest \
  tests/agent/test_pending_action_executor.py \
  tests/agent/test_advisor_pending.py \
  tests/agent/test_chat_use_case.py \
  tests/test_agent_service.py \
  tests/test_agent_runtime_architecture.py \
  tests/memory/test_memory_service.py \
  -v
```

Expected: PASS。

- [ ] **Step 3: 跑架构检查**

Run:

```bash
bash scripts/check-layer-deps.sh
```

Expected: PASS。如果只剩 `llm_client_manager.py` 507 行历史问题，先不要在本 change 里重构它；在最终说明中列为现存阻塞或单独 change。

- [ ] **Step 4: 更新 OpenSpec tasks**

将 `openspec/changes/refactor-agent-execution-boundaries/tasks.md` 中已完成项从 `- [ ]` 改为 `- [x]`。只勾选实际完成的任务。

- [ ] **Step 5: 查看工作树**

Run:

```bash
git status --short
```

Expected: 只包含本 change 相关文件。

- [ ] **Step 6: 最终提交**

```bash
git add backend/app/agent backend/app/services/agent_service.py backend/tests scripts/check-layer-deps.sh docs/architecture/overview.md openspec/changes/refactor-agent-execution-boundaries/tasks.md
git commit -m "refactor: align agent execution boundaries"
```

## 自检结果

- Spec 覆盖：`llm-tool-calling` 的单一 pending 入口、缓存失效、trace 由 Tasks 1-5 和 11 覆盖；`agent-platform-architecture` 的 Application 生命周期、兼容委托、Runtime prepared inputs、传感器由 Tasks 6-9 和 11 覆盖；`agent-memory-foundation` 的无 RAG 空实现和未来端口由 Task 10 覆盖。
- 占位符扫描：计划中没有要求实现者自行补全未定义逻辑；每个代码变更步骤都给出具体代码块或具体替换方式。
- 类型一致性：核心新增类型为 `PendingActionDecision`，核心入口为 `handle_pending_action(farm_id, message, farm_uid=None)`，后续任务均使用同一名称和签名。
