# Function Calling Migration 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 skillify 预路由快通道，所有对话请求统一走 LangGraph Function Calling 路由，消除回答风格割裂。

**Architecture:** 当前 `agent_service.py` 中 `chat_with_agent()` 和 `stream_chat_with_agent()` 先尝试 skillify 预路由（关键词匹配 + LLM 意图分类），命中后直接执行 skill 返回原始工具输出；未命中才走 LangGraph。迁移后删除预路由分支，所有请求统一进入 LangGraph 的 `llm → tools → llm` 循环，由 LLM 通过 Function Calling 自主决定是否调用 tool，所有回答经 LLM 组织自然语言。

**Tech Stack:** Python 3.11, LangGraph, LangChain, FastAPI, pytest, ruff

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/services/agent_service.py` | **大幅修改** | 移除 `_try_skillify_route()`、快通道分支、`_execute_skill()`、相关导入 |
| `backend/app/api/agent.py` | **小改** | `event_generator` 中移除 `node_type="routing"` filter |
| `backend/tests/test_agent_service_fc.py` | **新建** | agent_service 移除预路由后的单元测试 |
| `backend/tests/test_agent_api.py` | **修改** | 更新已有 API 测试，确保不受迁移影响 |

**不改动的文件：**
- `app/agent/graph.py` — LangGraph 图定义不变，`_llm_node` 的 `bind_tools()` 和 `_parallel_tool_node` 已就绪
- `app/agent/advisor.py` — `invoke_advisor` / `stream_advisor` 不变
- `app/agent/skills/__init__.py` — `get_langchain_tools()` 仍被 graph.py 和 pending action 使用
- `app/agent/guardrails.py` — 不变
- `app/infra/pending_actions.py` — 写操作拦截机制不变
- `app/api/admin_config.py` — admin 管理接口仍使用 `get_skill_manager()` 列出 skills，不受影响

---

### Task 1: 写 agent_service 移除预路由的单元测试

**Files:**
- Create: `backend/tests/test_agent_service_fc.py`

- [ ] **Step 1: 编写测试文件**

测试覆盖以下场景：
1. `chat_with_agent` 不再调用 `_try_skillify_route`
2. 只读请求统一走 `invoke_advisor`（LangGraph）
3. 流式请求统一走 `stream_advisor`（LangGraph）
4. pending action 确认/取消流程不受影响
5. `_try_skillify_route` 函数不存在
6. `_execute_skill` 函数不存在（仅被 `_execute_pending_action` 内联）

```python
"""agent_service FC 迁移后的单元测试。"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.agent import ChatResponse


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.add = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


class TestSkillifyRouteRemoved:
    """验证 skillify 预路由代码已完全移除。"""

    def test_try_skillify_route_not_exists(self):
        """_try_skillify_route 函数应不存在。"""
        from app.services import agent_service
        assert not hasattr(agent_service, "_try_skillify_route")

    def test_execute_skill_not_exists(self):
        """_execute_skill 函数应不存在。"""
        from app.services import agent_service
        assert not hasattr(agent_service, "_execute_skill")

    def test_no_build_skill_context_import(self):
        """agent_service 不应导入 build_skill_context。"""
        import inspect
        from app.services import agent_service
        source = inspect.getsource(agent_service)
        assert "build_skill_context" not in source

    def test_no_get_skill_manager_import(self):
        """agent_service 不应导入 get_skill_manager。"""
        import inspect
        from app.services import agent_service
        source = inspect.getsource(agent_service)
        assert "get_skill_manager" not in source


class TestChatWithAgentFCRouting:
    """验证 chat_with_agent 所有请求统一走 LangGraph。"""

    @pytest.mark.asyncio
    async def test_chat_goes_to_langgraph(self, mock_db):
        """只读请求应直接走 invoke_advisor，不走预路由。"""
        with patch(
            "app.services.agent_service.invoke_advisor",
            new_callable=AsyncMock,
            return_value="今天晴天，25度。",
        ) as mock_invoke, patch(
            "app.services.agent_service.get_pending", return_value=None
        ), patch(
            "app.services.agent_service.get_or_create_conversation"
        ) as mock_conv:
            mock_conv.return_value = MagicMock(id=1)
            result = await asyncio.to_thread(
                lambda: asyncio.run(
                    __import__("app.services.agent_service", fromlist=["chat_with_agent"])
                    .chat_with_agent(
                        mock_db, "今天天气咋样", farm_id=1, session_id="s1"
                    )
                )
            )
        mock_invoke.assert_called_once()
        assert isinstance(result, ChatResponse)
        assert "晴天" in result.reply

    @pytest.mark.asyncio
    async def test_chat_no_session_still_works(self, mock_db):
        """无 session_id 时也走 LangGraph。"""
        with patch(
            "app.services.agent_service.invoke_advisor",
            new_callable=AsyncMock,
            return_value="你好！",
        ) as mock_invoke, patch(
            "app.services.agent_service.get_pending", return_value=None
        ):
            result = await chat_with_agent_sync(mock_db, "你好", farm_id=1)
        mock_invoke.assert_called_once()
        assert result.reply == "你好！"

    @pytest.mark.asyncio
    async def test_pending_confirm_flow_intact(self, mock_db):
        """pending action 确认流程应不受影响。"""
        pending = MagicMock()
        pending.skill_name = "create_cost_record"
        pending.params = {"category": "化肥", "amount": 200}
        with patch(
            "app.services.agent_service.get_pending", return_value=pending
        ), patch(
            "app.services.agent_service.detect_user_intent",
            return_value="confirm"
        ), patch(
            "app.services.agent_service._execute_pending_action",
            new_callable=AsyncMock,
            return_value="已记录：化肥 200 元",
        ) as mock_exec, patch(
            "app.services.agent_service.remove_pending"
        ) as mock_remove:
            result = await chat_with_agent_sync(mock_db, "确认", farm_id=1)
        mock_exec.assert_called_once_with(1, "create_cost_record", {"category": "化肥", "amount": 200})
        mock_remove.assert_called_once_with(1)
        assert "已记录" in result.reply

    @pytest.mark.asyncio
    async def test_pending_cancel_flow_intact(self, mock_db):
        """pending action 取消流程应不受影响。"""
        pending = MagicMock()
        pending.skill_name = "create_cost_record"
        pending.params = {"category": "化肥", "amount": 200}
        with patch(
            "app.services.agent_service.get_pending", return_value=pending
        ), patch(
            "app.services.agent_service.detect_user_intent",
            return_value="cancel"
        ), patch(
            "app.services.agent_service.remove_pending"
        ) as mock_remove:
            result = await chat_with_agent_sync(mock_db, "算了", farm_id=1)
        mock_remove.assert_called_once_with(1)
        assert "取消" in result.reply


class TestStreamChatWithAgentFCRouting:
    """验证 stream_chat_with_agent 所有请求统一走 LangGraph。"""

    @pytest.mark.asyncio
    async def test_stream_goes_to_langgraph(self, mock_db):
        """流式请求应直接走 stream_advisor，不走预路由。"""
        async def fake_stream(*args, **kwargs):
            yield "今天"
            yield "晴天。"

        with patch(
            "app.services.agent_service.stream_advisor",
            new_callable=AsyncMock,
            side_effect=fake_stream,
        ) as mock_stream, patch(
            "app.services.agent_service.get_pending", return_value=None
        ), patch(
            "app.services.agent_service.get_or_create_conversation"
        ) as mock_conv:
            mock_conv.return_value = MagicMock(id=1)
            chunks = []
            async for chunk in await _stream_chat("今天天气", farm_id=1, db=mock_db, session_id="s1"):
                chunks.append(chunk)
        mock_stream.assert_called_once()
        assert "今天" in "".join(chunks)


async def chat_with_agent_sync(db, message, **kwargs):
    from app.services.agent_service import chat_with_agent
    return await chat_with_agent(db, message, **kwargs)


async def _stream_chat(message, **kwargs):
    from app.services.agent_service import stream_chat_with_agent
    return stream_chat_with_agent(message, **kwargs)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_agent_service_fc.py -v`
Expected: `TestSkillifyRouteRemoved` 中的测试 FAIL（因为 `_try_skillify_route` 和 `_execute_skill` 还存在），其他测试可能因 mock 路径问题也 FAIL

---

### Task 2: 移除 `_try_skillify_route()` 和 `_execute_skill()`

**Files:**
- Modify: `backend/app/services/agent_service.py`

- [ ] **Step 1: 删除 `_try_skillify_route` 函数**

删除 `agent_service.py` 第 38-67 行的 `_try_skillify_route()` 函数整体。

- [ ] **Step 2: 删除 `_execute_skill` 函数**

删除 `agent_service.py` 第 149-174 行的 `_execute_skill()` 函数整体。

注意：`_execute_pending_action()` 保留不动，它被 pending action 确认流程使用。

- [ ] **Step 3: 清理导入**

将第 29 行：
```python
from app.agent.skills import build_skill_context, get_langchain_tools
```
改为：
```python
from app.agent.skills import get_langchain_tools
```

同时删除 `_try_skillify_route` 内部的延迟导入（第 45-46 行已随函数删除）。

- [ ] **Step 4: 运行 ruff 检查**

Run: `cd backend && ruff check app/services/agent_service.py`
Expected: 无 error（可能有 unused import 警告，继续清理）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_service.py
git commit -m "refactor: 移除 _try_skillify_route 和 _execute_skill 函数"
```

---

### Task 3: 简化 `chat_with_agent()` — 移除 skillify 预路由分支

**Files:**
- Modify: `backend/app/services/agent_service.py`

当前 `chat_with_agent()` 逻辑（第 192-344 行）：

```
1. pending action 检查 → 确认/取消/修正
2. skillify 预路由 → 命中只读 skill → 直接执行 → 返回
3. 未命中 → 走 LangGraph
```

迁移后：

```
1. pending action 检查 → 确认/取消/修正（不变）
2. 走 LangGraph（统一）
```

- [ ] **Step 1: 替换 `chat_with_agent` 预路由分支**

将第 270-316 行的 skillify 预路由分支（从 `skillify_match = await _try_skillify_route(...)` 到 `return ChatResponse(reply=reply)` 的整个 else 块）替换为直接走 LangGraph。

替换前（第 270-316 行）：
```python
    # 无 pending action 或用户修正参数 → 先尝试 skillify 预路由
    skillify_match = await _try_skillify_route(message, farm_id=farm_id)
    if skillify_match:
        skill_name, skill_params, route_source = skillify_match
        if is_write_skill(skill_name):
            ...
        else:
            ...
            return ChatResponse(reply=reply)

    # 预路由未命中（或写操作需要参数提取）→ 走 LangGraph
```

替换后：
```python
    # 统一走 LangGraph Function Calling 路由
```

保留第 318-344 行的 LangGraph 调用和记录保存代码不变。

- [ ] **Step 2: 确认最终 `chat_with_agent` 结构**

迁移后的 `chat_with_agent` 应为：

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
    """与用户进行 Agent 对话，支持写操作确认流程。"""
    logger.info(
        "开始对话 | farm=%s cycle=%s | input: %s", farm_id, cycle_id, message[:100]
    )

    # 如果有 session_id，获取或创建会话并保存用户消息
    conversation = None
    if session_id:
        conversation = get_or_create_conversation(db, farm_id, session_id, user_id=user_id)
        save_message(db, conversation.id, "user", message)

    # 检查是否有 pending action
    pending = get_pending(farm_id)
    if pending is not None:
        intent = detect_user_intent(message)

        if intent == "confirm":
            # ... 确认流程不变 ...

        if intent == "cancel":
            # ... 取消流程不变 ...

        # intent == "modify"：用户修正参数，交给 LLM 处理

    # 统一走 LangGraph Function Calling 路由
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    reply = await invoke_advisor(
        full_input,
        farm_id=farm_id,
        db=db,
        conversation_id=conversation.id if conversation else None,
        session_id=session_id or "",
        request_id=request_id,
    )

    record = AgentRecord(
        cycle_id=cycle_id, record_type="chat", content=reply, farm_id=farm_id
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("对话记录已保存 | record_id=%s", record.id)

    if conversation:
        save_message(db, conversation.id, "assistant", reply)

    return ChatResponse(reply=reply)
```

- [ ] **Step 3: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_agent_service_fc.py::TestSkillifyRouteRemoved -v`
Expected: 4 个 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/agent_service.py
git commit -m "refactor: chat_with_agent 移除 skillify 预路由，统一走 LangGraph FC"
```

---

### Task 4: 简化 `stream_chat_with_agent()` — 移除 skillify 预路由分支

**Files:**
- Modify: `backend/app/services/agent_service.py`

当前 `stream_chat_with_agent()` 逻辑（第 347-406 行）：

```
1. skillify 预路由 → 命中只读 skill → 直接执行 → yield 结果 → return
2. 未命中 → 走 LangGraph 流式
```

迁移后：

```
1. 走 LangGraph 流式（统一）
```

- [ ] **Step 1: 替换 `stream_chat_with_agent` 预路由分支**

删除第 365-388 行的 skillify 预路由分支：
```python
    # skillify 预路由（只读 skill 直接执行，写操作和未命中走 LangGraph）
    skillify_match = await _try_skillify_route(message, farm_id=farm_id)
    if skillify_match:
        skill_name, skill_params, route_source = skillify_match
        if not is_write_skill(skill_name):
            ...
            try:
                result = await _execute_skill(skill_name, skill_params)
                yield filter_output(result)
                return
            except Exception as exc:
                ...
            finally:
                clear_trace()
```

替换为：
```python
    # 统一走 LangGraph Function Calling 流式路由
```

保留第 390-405 行的 LangGraph 流式调用不变。

- [ ] **Step 2: 清理不再使用的导入**

移除 `filter_output` 的导入（第 357-358 行的 `from app.agent.guardrails import filter_output`），因为流式回复的过滤已在 `stream_advisor` 内部处理（`advisor.py` 第 150 行 `yield filter_output(msg.content)`）。

- [ ] **Step 3: 确认最终 `stream_chat_with_agent` 结构**

```python
async def stream_chat_with_agent(
    message: str,
    farm_id: int,
    cycle_id: int | None = None,
    db: Session | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    request_id: str = "",
) -> AsyncGenerator[str, None]:
    """流式与 Agent 对话，逐 token 返回。"""
    # 如果有 session_id 和 db，获取或创建会话并保存用户消息
    conversation = None
    if db and session_id:
        conversation = get_or_create_conversation(db, farm_id, session_id, user_id=user_id)
        save_message(db, conversation.id, "user", message)

    # 统一走 LangGraph Function Calling 流式路由
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    async for chunk in stream_advisor(
        full_input,
        farm_id=farm_id,
        db=db,
        conversation_id=conversation.id if conversation else None,
        session_id=session_id or "",
        request_id=request_id,
    ):
        yield chunk
```

- [ ] **Step 4: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_agent_service_fc.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_service.py
git commit -m "refactor: stream_chat_with_agent 移除 skillify 预路由，统一走 LangGraph FC 流式"
```

---

### Task 5: 清理 `agent_service.py` 中不再使用的导入

**Files:**
- Modify: `backend/app/services/agent_service.py`

- [ ] **Step 1: 移除不再使用的导入**

移除以下不再被使用的导入：

1. `from app.infra.pending_actions import is_write_skill` — 只在已删除的 skillify 预路由分支中使用
2. `from app.infra.trace_context import init_trace, clear_trace` — 只在已删除的 skillify 预路由分支中使用
3. `from app.infra.trace_collector import get_collector` — 只在已删除的 `_try_skillify_route`、`_execute_skill` 和预路由分支中使用

**注意：** 检查 `_execute_pending_action` 是否仍使用这些导入。当前 `_execute_pending_action`（第 121-146 行）确实使用了 `get_collector` 和 `get_langchain_tools`，所以 `get_collector` 和 `get_langchain_tools` 必须保留。

最终导入列表应为：

```python
import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.advisor import invoke_advisor, stream_advisor
from app.agent.report import generate_cycle_report
from app.agent.skills import get_langchain_tools
from app.core.json_repair import safe_parse_json
from app.infra.pending_actions import (
    detect_user_intent,
    get_pending,
    remove_pending,
)
from app.infra.trace_collector import get_collector
from app.models.agent_record import AgentRecord
from app.schemas.agent import (
    AdviceItem,
    ChatResponse,
    DailyAdviceResponse,
    ReportResponse,
)
from app.services.conversation_service import (
    get_or_create_conversation,
    save_message,
)
```

移除项：
- `from app.infra.pending_actions import is_write_skill`
- `from app.infra.pending_actions import store_pending`（如果存在的话）
- `from app.infra.trace_context import init_trace, clear_trace`

- [ ] **Step 2: 运行 ruff 检查**

Run: `cd backend && ruff check app/services/agent_service.py`
Expected: 无 error

- [ ] **Step 3: 运行全量测试确保无回归**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/agent_service.py
git commit -m "refactor: 清理 agent_service 中不再使用的导入"
```

---

### Task 6: 更新 `agent.py` 中 trace 查询 filter

**Files:**
- Modify: `backend/app/api/agent.py`

当前 `agent.py` 第 142 行查询 skill 列表时使用了：
```python
.filter(TraceRecord.node_type.in_(["skill_call", "routing"]))
```

迁移后不再有 `node_type="routing"` 的记录，应简化为：
```python
.filter(TraceRecord.node_type.in_(["skill_call"]))
```

等价于：
```python
.filter(TraceRecord.node_type == "skill_call")
```

- [ ] **Step 1: 修改 trace 查询 filter**

将 `backend/app/api/agent.py` 第 142 行：
```python
                .filter(TraceRecord.node_type.in_(["skill_call", "routing"]))
```
改为：
```python
                .filter(TraceRecord.node_type == "skill_call")
```

- [ ] **Step 2: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_agent_api.py -v`
Expected: 全部 PASS（已有测试 mock 了 `chat_with_agent`，不涉及 trace 查询）

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/agent.py
git commit -m "refactor: trace 查询移除 routing 类型 filter"
```

---

### Task 7: 更新 API 测试覆盖 FC 迁移场景

**Files:**
- Modify: `backend/tests/test_agent_api.py`

- [ ] **Step 1: 添加测试验证 skills 查询只查 skill_call**

在 `test_agent_api.py` 中添加测试确保 trace 查询 filter 正确：

```python
class TestAgentTraceFilter:
    """验证 trace 查询只查 skill_call 类型。"""

    def test_stream_trace_query_no_routing(self, client, auth_headers) -> None:
        """验证 event_generator 查询 skills 时不含 routing。"""
        import inspect
        from app.api import agent as agent_module
        source = inspect.getsource(agent_module)
        assert 'node_type="routing"' not in source
        assert '"routing"' not in source
```

- [ ] **Step 2: 运行全部测试**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_agent_api.py tests/test_agent_service_fc.py
git commit -m "test: 添加 FC 迁移后的 agent_service 和 trace 测试"
```

---

### Task 8: 最终验证

- [ ] **Step 1: ruff 全量检查**

Run: `cd backend && ruff check app/ tests/`
Expected: 无 error

- [ ] **Step 2: 全量测试**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 3: 导入验证**

Run: `cd backend && python -c "from app.services.agent_service import chat_with_agent, stream_chat_with_agent; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 4: 确认 `agent_service.py` 中不含 skillify 预路由残留**

Run: `cd backend && grep -n "skillify\|_try_skillify_route\|_execute_skill\b\|build_skill_context\|node_type.*routing" app/services/agent_service.py`
Expected: 无匹配（空输出）

- [ ] **Step 5: 确认 pending action 流程引用完整**

Run: `cd backend && grep -n "_execute_pending_action\|get_pending\|remove_pending\|detect_user_intent" app/services/agent_service.py`
Expected: 这些函数仍有引用（在 pending action 确认/取消分支中）

- [ ] **Step 6: 最终 commit**

```bash
git add -A
git commit -m "chore: FC migration 最终验证通过"
```
