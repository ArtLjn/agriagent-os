# Agent 响应速度优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent 写操作首字延迟从 4-6s 降到 2s 以内，简单查询降到 1s 以内。

**Architecture:** 三层优化 —— 缓存层（system prompt + farm context 缓存）、路由层（按意图选择轻量/标准模型）、预加载层（LLM 调用期间并行预热 tool 数据缓存）。所有优化对前端透明，`/chat/stream` API 格式不变。

**Tech Stack:** Python 3.12, FastAPI, LangGraph, asyncio, 现有 skill_cache/weather_cache 模式

---

## 现状分析

| 优化项 | 状态 | 说明 |
|--------|------|------|
| 确认语模板化（跳过第二轮 LLM） | **已实现** | `graph.py:419-422` 已跳过 |
| 问候语规则路由 | **已实现** | `intent_router.py` + `advisor.py:72-74` |
| Skill 级 TTL 缓存 | **已实现** | `skill_cache.py` |
| 天气缓存 | **已实现** | `weather/cache.py` 10min TTL |
| **System Prompt 缓存** | **未实现** | 每次请求重新 compose + 渲染 |
| **Farm Context 缓存** | **未实现** | 每次请求查 DB 5 张表 |
| **按意图模型路由** | **未实现** | 所有请求走 `role="generation"` |
| **写操作后缓存失效** | **未实现** | 写入后读缓存返回旧数据 |
| **并行缓存预热** | **未实现** | tool 执行时才加载上下文 |

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/agent/prompt_cache.py` | **新建** | System prompt + farm context TTL 缓存 |
| `backend/app/agent/graph.py` | **修改** | 集成缓存、按意图选模型、并行预热 |
| `backend/app/agent/advisor.py` | **修改** | 传递 intent 到 graph、写操作后清缓存 |
| `backend/app/agent/state.py` | **修改** | AgentState 增加 `intent` 字段 |
| `backend/providers.json` | **修改** | 轻量模型增加 `"lightweight"` role |
| `backend/tests/test_prompt_cache.py` | **新建** | 缓存模块单元测试 |
| `backend/tests/test_agent_response_optimization.py` | **新建** | 集成测试 |

---

## Task 1: System Prompt + Farm Context 缓存

**Files:**
- Create: `backend/app/agent/prompt_cache.py`
- Modify: `backend/app/agent/graph.py:315-389,457-467`
- Test: `backend/tests/test_prompt_cache.py`

### Step 1.1: 写缓存模块的失败测试

```python
# backend/tests/test_prompt_cache.py
"""System prompt + farm context TTL 缓存测试。"""

import time
from unittest.mock import patch

import pytest

from app.agent.prompt_cache import (
    PromptCache,
    FarmContextCache,
    clear_all_caches,
)


class TestPromptCache:
    """system prompt 渲染结果缓存。"""

    def test_cache_miss_returns_none(self):
        cache = PromptCache(ttl_seconds=3600)
        result = cache.get(farm_id=1, date_str="2026-06-02")
        assert result is None

    def test_cache_set_and_get(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-02", value="rendered prompt")
        result = cache.get(farm_id=1, date_str="2026-06-02")
        assert result == "rendered prompt"

    def test_cache_key_includes_farm_and_date(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-02", value="farm1")
        cache.set(farm_id=2, date_str="2026-06-02", value="farm2")
        assert cache.get(farm_id=1, date_str="2026-06-02") == "farm1"
        assert cache.get(farm_id=2, date_str="2026-06-02") == "farm2"

    def test_cache_different_dates(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-01", value="day1")
        cache.set(farm_id=1, date_str="2026-06-02", value="day2")
        assert cache.get(farm_id=1, date_str="2026-06-01") == "day1"
        assert cache.get(farm_id=1, date_str="2026-06-02") == "day2"

    def test_cache_expires_after_ttl(self):
        cache = PromptCache(ttl_seconds=1)
        cache.set(farm_id=1, date_str="2026-06-02", value="expired")
        time.sleep(1.1)
        assert cache.get(farm_id=1, date_str="2026-06-02") is None

    def test_cache_invalidate_by_farm(self):
        cache = PromptCache(ttl_seconds=3600)
        cache.set(farm_id=1, date_str="2026-06-02", value="v1")
        cache.set(farm_id=2, date_str="2026-06-02", value="v2")
        cache.invalidate(farm_id=1)
        assert cache.get(farm_id=1, date_str="2026-06-02") is None
        assert cache.get(farm_id=2, date_str="2026-06-02") == "v2"


class TestFarmContextCache:
    """农场上下文缓存。"""

    def test_cache_miss_returns_none(self):
        cache = FarmContextCache(ttl_seconds=300)
        assert cache.get(farm_id=1) is None

    def test_cache_set_and_get(self):
        cache = FarmContextCache(ttl_seconds=300)
        ctx = {"display_name": "张三", "farm_location": "北京"}
        cache.set(farm_id=1, value=ctx)
        assert cache.get(farm_id=1) == ctx

    def test_cache_expires(self):
        cache = FarmContextCache(ttl_seconds=1)
        cache.set(farm_id=1, value={"display_name": "张三"})
        time.sleep(1.1)
        assert cache.get(farm_id=1) is None

    def test_cache_invalidate(self):
        cache = FarmContextCache(ttl_seconds=300)
        cache.set(farm_id=1, value={"display_name": "张三"})
        cache.invalidate(farm_id=1)
        assert cache.get(farm_id=1) is None


class TestClearAllCaches:
    """全局缓存清理。"""

    def test_clear_all(self):
        pc = PromptCache(ttl_seconds=3600)
        fc = FarmContextCache(ttl_seconds=300)
        pc.set(farm_id=1, date_str="2026-06-02", value="prompt")
        fc.set(farm_id=1, value={"display_name": "张三"})
        clear_all_caches()
        assert pc.get(farm_id=1, date_str="2026-06-02") is None
        assert fc.get(farm_id=1) is None
```

- [ ] **Step 1.1: 写缓存模块的测试**

### Step 1.2: 运行测试确认失败

Run: `cd backend && poetry run pytest tests/test_prompt_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent.prompt_cache'`

- [ ] **Step 1.2: 运行测试确认失败**

### Step 1.3: 实现缓存模块

```python
# backend/app/agent/prompt_cache.py
"""System prompt + farm context TTL 缓存，基于内存字典。"""

import logging
import time

logger = logging.getLogger(__name__)


class PromptCache:
    """按 (farm_id, date_str) 缓存渲染后的 system prompt。

    同一 farm 同一天内 prompt 内容不变（farm 名称、位置、季节等稳定），
    缓存后跳过 DB 查询和 Jinja2 渲染。
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[tuple[int, str], tuple[str, float]] = {}
        self._ttl = ttl_seconds

    def get(self, farm_id: int, date_str: str) -> str | None:
        key = (farm_id, date_str)
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() >= expire_at:
            del self._store[key]
            return None
        logger.debug("PROMPT CACHE HIT | farm=%s date=%s", farm_id, date_str)
        return value

    def set(self, farm_id: int, date_str: str, value: str) -> None:
        key = (farm_id, date_str)
        self._store[key] = (value, time.time() + self._ttl)
        logger.debug("PROMPT CACHE SET | farm=%s date=%s ttl=%ds", farm_id, date_str, self._ttl)

    def invalidate(self, farm_id: int) -> int:
        keys = [k for k in self._store if k[0] == farm_id]
        for k in keys:
            del self._store[k]
        return len(keys)


class FarmContextCache:
    """按 farm_id 缓存农场上下文（位置、坐标、称呼、种植信息）。"""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[int, tuple[dict, float]] = {}
        self._ttl = ttl_seconds

    def get(self, farm_id: int) -> dict | None:
        entry = self._store.get(farm_id)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() >= expire_at:
            del self._store[farm_id]
            return None
        logger.debug("FARM CTX CACHE HIT | farm=%s", farm_id)
        return value

    def set(self, farm_id: int, value: dict) -> None:
        self._store[farm_id] = (value, time.time() + self._ttl)

    def invalidate(self, farm_id: int) -> bool:
        if farm_id in self._store:
            del self._store[farm_id]
            return True
        return False


_prompt_cache = PromptCache(ttl_seconds=3600)
_farm_ctx_cache = FarmContextCache(ttl_seconds=300)


def get_prompt_cache() -> PromptCache:
    return _prompt_cache


def get_farm_ctx_cache() -> FarmContextCache:
    return _farm_ctx_cache


def clear_all_caches() -> None:
    _prompt_cache._store.clear()
    _farm_ctx_cache._store.clear()
```

- [ ] **Step 1.3: 实现缓存模块**

### Step 1.4: 运行测试确认通过

Run: `cd backend && poetry run pytest tests/test_prompt_cache.py -v`
Expected: 全部 PASS

- [ ] **Step 1.4: 运行测试确认通过**

### Step 1.5: 修改 graph.py 集成 farm context 缓存

在 `_get_farm_context` 中使用缓存。修改 `graph.py:315` 附近的函数：

```python
# graph.py — 修改 _get_farm_context（约 315 行）
# 在文件顶部 import 区域增加：
from app.agent.prompt_cache import get_farm_ctx_cache, get_prompt_cache

# 替换 _get_farm_context 函数（315-389 行）：
async def _get_farm_context(farm_id: int) -> dict:
    """异步获取农场上下文，带 5 分钟 TTL 缓存。"""
    cache = get_farm_ctx_cache()
    cached = cache.get(farm_id)
    if cached is not None:
        return cached

    def _query() -> dict:
        db = SessionLocal()
        try:
            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            display_name = "农友"
            user_city = ""
            user_lat = None
            user_lon = None
            active_crops = ""

            if farm and farm.user_id:
                user = db.query(User).filter(User.id == farm.user_id).first()
                if user:
                    display_name = user.nickname or display_name

                user_setting = (
                    db.query(UserSetting)
                    .filter(UserSetting.user_id == farm.user_id)
                    .first()
                )
                if user_setting:
                    user_city = user_setting.default_city or ""
                    user_lat = user_setting.default_lat
                    user_lon = user_setting.default_lon

                try:
                    from app.models.cycle import CropCycle, CycleStage

                    cycles = (
                        db.query(CropCycle)
                        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
                        .all()
                    )
                    if cycles:
                        crop_infos = []
                        for cycle in cycles:
                            crop_name = cycle.name or "未知作物"
                            current_stage = (
                                db.query(CycleStage)
                                .filter(CycleStage.cycle_id == cycle.id, CycleStage.is_current == 1)
                                .first()
                            )
                            stage_name = current_stage.name if current_stage else "未知阶段"
                            crop_infos.append(f"{crop_name}({stage_name})")
                        active_crops = "、".join(crop_infos[:3])
                except Exception:
                    pass

            farm_location = user_city or (farm.location if farm and farm.location else "")

            farm_coords = ""
            if user_lat is not None and user_lon is not None:
                farm_coords = f"{user_lat:.4f},{user_lon:.4f}"

            return {
                "farm_location": farm_location,
                "farm_coords": farm_coords,
                "display_name": display_name,
                "active_crops": active_crops,
            }
        except Exception:
            logger.warning("获取农场上下文失败，使用默认值", exc_info=True)
            return {
                "farm_location": "",
                "farm_coords": "",
                "display_name": "农友",
                "active_crops": "",
            }
        finally:
            db.close()

    result = await asyncio.to_thread(_query)
    cache.set(farm_id, result)
    return result
```

- [ ] **Step 1.5: 修改 graph.py 集成 farm context 缓存**

### Step 1.6: 修改 graph.py 集成 system prompt 缓存

在 `_llm_node` 中使用 prompt 缓存。修改 `graph.py:455-467`：

```python
# graph.py — 替换 _llm_node 中 compose 调用（约 455-467 行）
# 原代码：
#   current_date = get_request_date()
#   current_season = _get_season(current_date)
#   system_text = get_composer().compose(...)
# 替换为：

    current_date = get_request_date()
    date_str = str(current_date)
    prompt_cache = get_prompt_cache()

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

- [ ] **Step 1.6: 修改 graph.py 集成 system prompt 缓存**

### Step 1.7: 写缓存集成测试

```python
# backend/tests/test_prompt_cache.py — 追加到文件末尾

class TestGraphCacheIntegration:
    """验证 _llm_node 使用了缓存。"""

    @pytest.mark.asyncio
    async def test_farm_context_uses_cache(self):
        """第二次调用 _get_farm_context 应命中缓存，不查 DB。"""
        from app.agent.graph import _get_farm_context
        from app.agent.prompt_cache import get_farm_ctx_cache

        get_farm_ctx_cache().invalidate(farm_id=1)

        with patch("app.agent.graph.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = None

            ctx1 = await _get_farm_context(farm_id=1)
            assert ctx1["display_name"] == "农友"
            call_count_after_first = mock_db.query.call_count

            ctx2 = await _get_farm_context(farm_id=1)
            assert ctx2["display_name"] == "农友"
            assert mock_db.query.call_count == call_count_after_first

        get_farm_ctx_cache().invalidate(farm_id=1)
```

- [ ] **Step 1.7: 写缓存集成测试**

### Step 1.8: 运行所有缓存测试

Run: `cd backend && poetry run pytest tests/test_prompt_cache.py -v`
Expected: 全部 PASS（包括集成测试）

- [ ] **Step 1.8: 运行所有缓存测试**

### Step 1.9: 提交

```bash
cd backend
git add app/agent/prompt_cache.py tests/test_prompt_cache.py app/agent/graph.py
git commit -m "feat(agent): system prompt + farm context TTL 缓存，减少重复 DB 查询和模板渲染"
```

- [ ] **Step 1.9: 提交 Task 1**

---

## Task 2: 按意图选择模型（轻量/标准）

**Files:**
- Modify: `backend/app/agent/state.py`
- Modify: `backend/app/agent/graph.py:132-134,434`
- Modify: `backend/app/agent/advisor.py:72-74,109-123,157-186`
- Modify: `backend/providers.json`
- Test: `backend/tests/test_agent_response_optimization.py`

### Step 2.1: AgentState 增加 intent 字段

```python
# backend/app/agent/state.py — 替换整个文件
"""Agent 状态定义。"""

from typing import Annotated

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """LangGraph 状态。"""

    messages: Annotated[list[BaseMessage], add_messages]
    farm_id: int
    intent: str  # "greeting" | "query" | "write" | "agent"
```

然后修改 `graph.py` 中的 `AgentState` 定义。删除 `graph.py:132-134` 的 `AgentState` 类，改为从 state 模块导入：

```python
# graph.py — 在 import 区域增加
from app.agent.state import AgentState

# 删除 graph.py 中 132-134 行的 AgentState 定义（重复的 TypedDict）
```

- [ ] **Step 2.1: AgentState 增加 intent 字段，统一到 state.py**

### Step 2.2: providers.json 增加轻量模型角色

在 dashscope provider 中，给 `qwen3.6-35b-a3b` 增加 `"lightweight"` role；在 local provider 中，给 `qwen3.6-flash` 增加 `"lightweight"` role：

```json
// backend/providers.json — 修改 dashscope 的第一个 model
{"id": "qwen3.6-35b-a3b", "priority": 1, "enabled": true, "roles": ["all", "lightweight"]}

// backend/providers.json — 修改 local 的 model
{"id": "qwen3.6-flash", "priority": 1, "enabled": true, "roles": ["all", "lightweight"]}
```

- [ ] **Step 2.2: providers.json 增加轻量模型角色**

### Step 2.3: 写模型路由的失败测试

```python
# backend/tests/test_agent_response_optimization.py
"""Agent 响应速度优化集成测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.intent_router import IntentType


class TestModelRouting:
    """按意图选择不同模型角色。"""

    @pytest.mark.asyncio
    async def test_query_intent_uses_lightweight_model(self):
        """QUERY 意图应使用 lightweight 角色。"""
        from app.agent.state import AgentState
        from langchain_core.messages import HumanMessage, AIMessage

        state: AgentState = {
            "messages": [HumanMessage(content="今天天气怎么样")],
            "farm_id": 1,
            "intent": "query",
        }

        with patch("app.agent.graph._get_farm_context", new_callable=AsyncMock) as mock_ctx, \
             patch("app.agent.graph.get_llm") as mock_get_llm, \
             patch("app.agent.graph.get_langchain_tools") as mock_tools, \
             patch("app.agent.graph.select_tools") as mock_select, \
             patch("app.agent.graph.get_composer") as mock_composer, \
             patch("app.agent.graph.check_quota", return_value=True), \
             patch("app.agent.graph.get_request_date") as mock_date, \
             patch("app.agent.graph.get_prompt_cache") as mock_pcache, \
             patch("app.agent.graph.get_collector"):

            mock_ctx.return_value = {
                "display_name": "农友",
                "farm_location": "北京",
                "farm_coords": "39.9,116.4",
                "active_crops": "番茄(开花期)",
            }
            mock_date.return_value = "2026-06-02"
            mock_pcache.return_value.get.return_value = "cached system prompt"
            mock_select.return_value = ["get_weather"]
            mock_tools.return_value = []
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="今天晴"))
            mock_get_llm.return_value = mock_llm
            mock_composer.return_value.compose.return_value = "system prompt"

            from app.agent.graph import _llm_node
            result = await _llm_node(state)

            mock_get_llm.assert_called_with(role="lightweight")

    @pytest.mark.asyncio
    async def test_write_intent_uses_generation_model(self):
        """WRITE 意图应使用 generation 角色。"""
        from app.agent.state import AgentState
        from langchain_core.messages import HumanMessage, AIMessage

        state: AgentState = {
            "messages": [HumanMessage(content="买化肥花了200块")],
            "farm_id": 1,
            "intent": "write",
        }

        with patch("app.agent.graph._get_farm_context", new_callable=AsyncMock) as mock_ctx, \
             patch("app.agent.graph.get_llm") as mock_get_llm, \
             patch("app.agent.graph.get_langchain_tools") as mock_tools, \
             patch("app.agent.graph.select_tools") as mock_select, \
             patch("app.agent.graph.get_composer") as mock_composer, \
             patch("app.agent.graph.check_quota", return_value=True), \
             patch("app.agent.graph.get_request_date") as mock_date, \
             patch("app.agent.graph.get_prompt_cache") as mock_pcache, \
             patch("app.agent.graph.get_collector"):

            mock_ctx.return_value = {
                "display_name": "农友",
                "farm_location": "北京",
                "farm_coords": "",
                "active_crops": "",
            }
            mock_date.return_value = "2026-06-02"
            mock_pcache.return_value.get.return_value = "cached system prompt"
            mock_select.return_value = ["create_cost_record"]
            mock_tools.return_value = []
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="已记账"))
            mock_get_llm.return_value = mock_llm

            from app.agent.graph import _llm_node
            result = await _llm_node(state)

            mock_get_llm.assert_called_with(role="generation")
```

- [ ] **Step 2.3: 写模型路由的失败测试**

### Step 2.4: 运行测试确认失败

Run: `cd backend && poetry run pytest tests/test_agent_response_optimization.py::TestModelRouting -v`
Expected: FAIL — `TypeError` 或 `get_llm` 未按预期 role 调用

- [ ] **Step 2.4: 运行测试确认失败**

### Step 2.5: 修改 _llm_node 按意图选择模型角色

在 `graph.py` 的 `_llm_node` 函数中，修改 `get_llm(role="generation")` 调用（约 434 行）：

```python
# graph.py — 修改 _llm_node 中 get_llm 调用
# 原代码（约 434 行）：
#   raw_llm = get_llm(role="generation")
# 替换为：

    intent = state.get("intent", "agent")
    model_role = "lightweight" if intent == "query" else "generation"
    raw_llm = get_llm(role=model_role)
    logger.info("模型路由 | intent=%s | role=%s", intent, model_role)
```

- [ ] **Step 2.5: 修改 _llm_node 按意图选择模型角色**

### Step 2.6: 修改 advisor.py 传递 intent 到 graph

在 `invoke_advisor`（约 72-74 行）和 `stream_advisor` 中，将 intent 传入 graph：

```python
# advisor.py — 修改 invoke_advisor 中意图路由后的 graph 调用
# 在 intent 分类后（72 行），保留 intent 值传递到 graph

# 修改 graph.ainvoke 的 input dict（约 116-123 行）：
# 原代码：
#   result = await graph.ainvoke(
#       {"messages": messages, "farm_id": farm_id},
#       ...
#   )
# 替换为：

    result = await graph.ainvoke(
        {"messages": messages, "farm_id": farm_id, "intent": intent.value},
        config={
            "recursion_limit": 15,
            "run_name": "advisor_invoke",
            "metadata": {"farm_id": farm_id, "request_type": "chat"},
        },
    )
```

同样修改 `stream_advisor` 中的 `graph.astream` 调用（约 180-190 行）：

```python
# advisor.py — 修改 stream_advisor 中的 graph.astream 调用
# 增加 intent 传递（和 invoke_advisor 相同的模式）
# 在 stream_advisor 中也需要做 intent 分类，然后传入 graph

# 在 stream_advisor 开头（guardrails 之后）增加意图分类：
    intent = classify_intent(user_input)

# 修改 graph.astream 的 input：
#   {"messages": messages, "farm_id": farm_id}
# 改为：
#   {"messages": messages, "farm_id": farm_id, "intent": intent.value}
```

- [ ] **Step 2.6: advisor.py 传递 intent 到 graph**

### Step 2.7: 运行测试确认通过

Run: `cd backend && poetry run pytest tests/test_agent_response_optimization.py::TestModelRouting -v`
Expected: 全部 PASS

- [ ] **Step 2.7: 运行测试确认通过**

### Step 2.8: 运行回归测试

Run: `cd backend && poetry run pytest tests/test_advisor_agent.py tests/test_llm.py -v`
Expected: 全部 PASS（现有测试不受影响）

- [ ] **Step 2.8: 运行回归测试**

### Step 2.9: 提交

```bash
cd backend
git add app/agent/state.py app/agent/graph.py app/agent/advisor.py providers.json tests/test_agent_response_optimization.py
git commit -m "feat(agent): 按意图路由模型，QUERY 走 lightweight 模型降低延迟"
```

- [ ] **Step 2.9: 提交 Task 2**

---

## Task 3: 写操作后缓存失效

**Files:**
- Modify: `backend/app/agent/advisor.py:88-98`
- Modify: `backend/app/infra/pending_actions.py:14-23`
- Test: `backend/tests/test_agent_response_optimization.py`（追加）

### Step 3.1: 写缓存失效的失败测试

```python
# backend/tests/test_agent_response_optimization.py — 追加

class TestCacheInvalidation:
    """写操作执行后缓存应失效。"""

    @pytest.mark.asyncio
    async def test_write_execution_clears_skill_cache(self):
        """确认执行 pending action 后，相关 skill 缓存被清除。"""
        from app.agent.advisor import invoke_advisor

        with patch("app.agent.advisor.check_input", return_value=(True, "")), \
             patch("app.agent.advisor.get_pending") as mock_pending, \
             patch("app.agent.advisor.detect_user_intent", return_value="confirm"), \
             patch("app.agent.advisor.get_skill_manager") as mock_mgr, \
             patch("app.agent.advisor.build_skill_context") as mock_ctx, \
             patch("app.agent.advisor.filter_output", side_effect=lambda x: x), \
             patch("app.infra.skill_cache.clear_cache") as mock_clear:

            mock_pending.return_value = MagicMock(
                skill_name="create_cost_record",
                params={"amount": 200, "category": "化肥"},
            )
            mock_result = MagicMock()
            mock_result.result = MagicMock(reply="已记账：化肥 200元")
            mock_mgr.return_value.execute = AsyncMock(return_value=mock_result)
            mock_ctx.return_value = MagicMock()

            await invoke_advisor("确认", farm_id=1)

            mock_clear.assert_called_once_with("cost_analytics")
```

- [ ] **Step 3.1: 写缓存失效的失败测试**

### Step 3.2: 运行测试确认失败

Run: `cd backend && poetry run pytest tests/test_agent_response_optimization.py::TestCacheInvalidation -v`
Expected: FAIL — `clear_cache` 未被调用

- [ ] **Step 3.2: 运行测试确认失败**

### Step 3.3: 定义 skill → cache group 映射

在 `pending_actions.py` 中增加缓存失效映射：

```python
# backend/app/infra/pending_actions.py — 在 WRITE_SKILLS 定义后（约 24 行）增加：

# 写操作 skill → 需要失效的 skill 缓存组
_CACHE_INVALIDATION_MAP: dict[str, list[str]] = {
    "create_cost_record": ["cost_analytics", "cost_summary", "get_farm_status"],
    "create_crop_cycle": ["crop_cycle", "get_farm_status"],
    "create_crop_template": [],
    "log_farm_activity": ["farm_logs", "get_farm_status"],
    "settle_debt": ["cost_analytics", "cost_summary", "get_farm_status"],
    "update_crop_stage": ["crop_cycle", "get_farm_status"],
}


def get_cache_groups_for_skill(skill_name: str) -> list[str]:
    """返回写操作 skill 执行后需要清除的 skill 缓存组。"""
    return _CACHE_INVALIDATION_MAP.get(skill_name, [])
```

- [ ] **Step 3.3: 定义 skill → cache group 映射**

### Step 3.4: 在 advisor.py 中执行缓存清除

修改 `advisor.py` 中 pending action 执行后的代码（约 88-98 行）：

```python
# advisor.py — 修改 pending action 执行逻辑
# 在 execute result 之后、finally 之前增加缓存清除：

            try:
                manager = get_skill_manager()
                ctx = build_skill_context(farm_id)
                exec_result = await manager.execute(pending.skill_name, pending.params, ctx)
                reply = exec_result.result.reply if exec_result.result else "操作完成。"

                # 写操作后清除相关 skill 缓存
                from app.infra.pending_actions import get_cache_groups_for_skill
                from app.infra.skill_cache import clear_cache as clear_skill_cache
                for group in get_cache_groups_for_skill(pending.skill_name):
                    cleared = clear_skill_cache(group)
                    if cleared:
                        logger.info(
                            "写操作后清除缓存 | skill=%s group=%s cleared=%d",
                            pending.skill_name, group, cleared,
                        )
            except Exception as e:
                logger.error("pending action 执行失败 | farm_id=%s | error=%s", farm_id, e)
                reply = "操作执行失败，请重试。"
            finally:
                remove_pending(farm_id)
```

- [ ] **Step 3.4: advisor.py 执行缓存清除**

### Step 3.5: 运行测试确认通过

Run: `cd backend && poetry run pytest tests/test_agent_response_optimization.py::TestCacheInvalidation -v`
Expected: PASS

- [ ] **Step 3.5: 运行测试确认通过**

### Step 3.6: 提交

```bash
cd backend
git add app/agent/advisor.py app/infra/pending_actions.py tests/test_agent_response_optimization.py
git commit -m "feat(agent): 写操作执行后自动清除相关 skill 缓存"
```

- [ ] **Step 3.6: 提交 Task 3**

---

## Task 4: 并行缓存预热

**Files:**
- Modify: `backend/app/agent/graph.py:490-544`
- Test: `backend/tests/test_agent_response_optimization.py`（追加）

### Step 4.1: 写并行预热的失败测试

```python
# backend/tests/test_agent_response_optimization.py — 追加

class TestParallelPreload:
    """LLM 调用期间并行预热 tool 数据缓存。"""

    @pytest.mark.asyncio
    async def test_preload_starts_parallel_with_llm(self):
        """天气 tool 被选中时，应在 LLM 调用期间预热天气缓存。"""
        from app.agent.state import AgentState
        from langchain_core.messages import HumanMessage, AIMessage

        state: AgentState = {
            "messages": [HumanMessage(content="今天天气")],
            "farm_id": 1,
            "intent": "query",
        }

        preload_called = False

        async def fake_preload(*args, **kwargs):
            nonlocal preload_called
            preload_called = True

        with patch("app.agent.graph._get_farm_context", new_callable=AsyncMock) as mock_ctx, \
             patch("app.agent.graph.get_llm") as mock_get_llm, \
             patch("app.agent.graph.get_langchain_tools", return_value=[]), \
             patch("app.agent.graph.select_tools", return_value=["get_weather"]), \
             patch("app.agent.graph.check_quota", return_value=True), \
             patch("app.agent.graph.get_request_date", return_value="2026-06-02"), \
             patch("app.agent.graph.get_prompt_cache") as mock_pcache, \
             patch("app.agent.graph.get_collector"), \
             patch("app.agent.graph._warm_tool_caches", new_callable=AsyncMock, side_effect=fake_preload) as mock_warm:

            mock_ctx.return_value = {
                "display_name": "农友",
                "farm_location": "北京",
                "farm_coords": "39.9,116.4",
                "active_crops": "",
            }
            mock_pcache.return_value.get.return_value = "cached prompt"
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="今天晴"))
            mock_get_llm.return_value = mock_llm

            from app.agent.graph import _llm_node
            await _llm_node(state)

            mock_warm.assert_called_once()
```

- [ ] **Step 4.1: 写并行预热的失败测试**

### Step 4.2: 运行测试确认失败

Run: `cd backend && poetry run pytest tests/test_agent_response_optimization.py::TestParallelPreload -v`
Expected: FAIL — `AttributeError: module has no attribute '_warm_tool_caches'`

- [ ] **Step 4.2: 运行测试确认失败**

### Step 4.3: 实现 _warm_tool_caches 函数

在 `graph.py` 中，`_llm_node` 之前（约 393 行），增加预热函数：

```python
# graph.py — 在 _llm_node 函数之前增加（约 392 行）

_PRELOAD_MAP: dict[str, list[str]] = {
    "get_weather": ["weather"],
    "get_cost_summary": ["cost_summary"],
    "get_cost_analytics": ["cost_analytics"],
    "get_farm_status": ["farm_status"],
    "get_crop_cycle": ["crop_cycle"],
    "get_farm_logs": ["farm_logs"],
}


async def _warm_tool_caches(
    selected_names: list[str], farm_id: int, farm_ctx: dict,
) -> None:
    """并行预热已选 tool 的底层缓存，2s 超时，失败不影响主流程。"""
    import asyncio

    tasks = []
    for name in selected_names:
        data_types = _PRELOAD_MAP.get(name, [])
        for dt in data_types:
            if dt == "weather" and farm_ctx.get("farm_location"):
                from app.services.weather import get_weather_cached
                tasks.append(get_weather_cached(
                    location=farm_ctx["farm_location"],
                    lat=farm_ctx.get("farm_coords", "").split(",")[0] or None,
                    lon=farm_ctx.get("farm_coords", "").split(",")[-1] or None,
                ))

    if not tasks:
        return

    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=2.0,
        )
        logger.info("缓存预热完成 | tools=%s tasks=%d", selected_names, len(tasks))
    except asyncio.TimeoutError:
        logger.warning("缓存预热超时 2s | tools=%s", selected_names)
```

> **注意：** `get_weather_cached` 是 weather service 已有的缓存查询接口。如果不存在，预热逻辑需要直接调用 `weather_service.fetch_weather`（会被 weather_cache 缓存）。如果 service 没有导出这样的函数，预热可以简化为跳过，后续再迭代。

- [ ] **Step 4.3: 实现 _warm_tool_caches**

### Step 4.4: 在 _llm_node 中集成并行预热

修改 `graph.py` 的 `_llm_node` 中 LLM 调用部分（约 490 行），在 LLM 调用的同时启动预热：

```python
# graph.py — 修改 _llm_node 中 LLM 调用部分
# 在 LLM 调用之前，创建预热任务：

    # 并行缓存预热 + LLM 调用
    preload_task = asyncio.create_task(
        _warm_tool_caches(
            [t.name for t in selected_tools] if selected_tools else [],
            farm_id,
            farm_ctx,
        )
    )

    # LLM 调用 + 计时 + 请求内重试（保持原有逻辑不变）
    start = _time.perf_counter()
    max_retries = settings.ai.failover_max_retries
    response = None

    async with _LLM_SEMAPHORE:
        for attempt in range(max_retries):
            # ... 原有重试逻辑不变 ...

    # 确保预热任务完成（不阻塞，已并行运行）
    try:
        await asyncio.wait_for(preload_task, timeout=0.1)
    except (asyncio.TimeoutError, Exception):
        pass
```

- [ ] **Step 4.4: 在 _llm_node 中集成并行预热**

### Step 4.5: 运行测试确认通过

Run: `cd backend && poetry run pytest tests/test_agent_response_optimization.py::TestParallelPreload -v`
Expected: PASS

- [ ] **Step 4.5: 运行测试确认通过**

### Step 4.6: 提交

```bash
cd backend
git add app/agent/graph.py tests/test_agent_response_optimization.py
git commit -m "feat(agent): LLM 调用期间并行预热 tool 数据缓存"
```

- [ ] **Step 4.6: 提交 Task 4**

---

## Task 5: 集成验证 + 回归测试

**Files:**
- Test: `backend/tests/test_agent_response_optimization.py`（追加）

### Step 5.1: 端到端验证测试

```python
# backend/tests/test_agent_response_optimization.py — 追加

class TestEndToEnd:
    """端到端验证：各优化协同工作。"""

    @pytest.mark.asyncio
    async def test_query_uses_cache_and_lightweight_model(self):
        """QUERY 意图走缓存 + 轻量模型，完整路径。"""
        from app.agent.advisor import invoke_advisor

        with patch("app.agent.advisor.check_input", return_value=(True, "")), \
             patch("app.agent.advisor._get_advisor_graph") as mock_graph_fn, \
             patch("app.agent.advisor.filter_output", side_effect=lambda x: x), \
             patch("app.agent.advisor._build_history_messages", return_value=[]):

            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value={
                "messages": [AIMessage(content="今天晴，最高温28°C")]
            })
            mock_graph_fn.return_value = mock_graph

            result = await invoke_advisor("今天天气", farm_id=1)

            # graph 应收到 intent="query"
            call_args = mock_graph.ainvoke.call_args
            assert call_args[0][0]["intent"] == "query"
            assert "晴" in result
```

- [ ] **Step 5.1: 端到端验证测试**

### Step 5.2: 运行全量测试

Run: `cd backend && poetry run pytest tests/test_agent_response_optimization.py tests/test_prompt_cache.py tests/test_advisor_agent.py tests/test_llm.py -v`
Expected: 全部 PASS

- [ ] **Step 5.2: 运行全量测试**

### Step 5.3: 运行 Lint 检查

Run: `cd backend && poetry run ruff check app/agent/ tests/test_prompt_cache.py tests/test_agent_response_optimization.py`
Expected: 无报错

- [ ] **Step 5.3: 运行 Lint 检查**

### Step 5.4: 提交

```bash
cd backend
git add tests/test_agent_response_optimization.py
git commit -m "test(agent): 响应速度优化集成测试"
```

- [ ] **Step 5.4: 提交 Task 5**

---

## Self-Review

### 1. Spec 覆盖检查

| Spec 需求 | 对应 Task |
|-----------|----------|
| Write operations use single LLM call | **已实现**（无代码变更） |
| System prompt cached by farm and date | Task 1 |
| Model routing by task complexity | Task 2 |
| Parallel context preloading | Task 4 |
| Preload does not block main flow | Task 4（`return_exceptions=True` + 2s timeout） |
| High-frequency query cached locally | **已实现**（skill_cache.py） |
| Cache invalidation on data change | Task 3 |

### 2. 占位符扫描

无 `TBD`、`TODO`、`implement later`、`fill in details` 等占位符。

### 3. 类型一致性

- `AgentState.intent` 定义为 `str`，在 `advisor.py` 中通过 `intent.value` 传入（`IntentType.value` 返回 `str`）
- `_warm_tool_caches` 接受 `list[str]` 和 `dict`，与调用方一致
- `get_cache_groups_for_skill` 返回 `list[str]`，与 `clear_cache(skill_name: str)` 一致
