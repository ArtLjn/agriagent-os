# Context Engineering Optimization 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent 上下文注入从"全量塞入 prompt"改为"按需加载 + 筛选保持 + 历史压缩"，降低 50-67% token 消耗。

**Architecture:** 三步改造：(1) farm_context_summary 从 system prompt 移到 get_farm_status Skill，Agent 按需调用；(2) 工具第二轮回退改为 TOOL_CHAIN_MAP 关联扩展；(3) micro_compact 升级为 sliding window 规则压缩。

**Tech Stack:** Python 3.11, LangChain/LangGraph, skillify-sdk, pytest

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `app/agent/skills/farm-status/__init__.py` | 包标记 |
| Create | `app/agent/skills/farm-status/scripts/__init__.py` | 包标记 |
| Create | `app/agent/skills/farm-status/scripts/main.py` | get_farm_status Skill 实现 |
| Create | `app/agent/skills/farm-status/skill.md` | Skill 元信息 |
| Create | `tests/test_farm_status_skill.py` | Skill 单元测试 |
| Create | `tests/test_sliding_window.py` | sliding window 单元测试 |
| Create | `tests/test_tool_chain_map.py` | TOOL_CHAIN_MAP 单元测试 |
| Modify | `prompts/base.j2` | 移除 farm_context_summary 注入段 |
| Modify | `app/agent/graph.py` | 移除 farm_context_service 调用、改第二轮工具绑定、升级 micro_compact |
| Modify | `app/agent/tool_selector.py` | 新增 TOOL_CHAIN_MAP + expand_by_chain() |
| Modify | `app/agent/skills/__init__.py` | 无改动（skillify 自动发现新 Skill） |

---

### Task 1: 创建 get_farm_status Skill

**Files:**
- Create: `app/agent/skills/farm-status/__init__.py`
- Create: `app/agent/skills/farm-status/scripts/__init__.py`
- Create: `app/agent/skills/farm-status/scripts/main.py`
- Create: `app/agent/skills/farm-status/skill.md`
- Test: `tests/test_farm_status_skill.py`

- [ ] **Step 1: 写 Skill 包标记文件**

创建 `app/agent/skills/farm-status/__init__.py`（空文件）和 `app/agent/skills/farm-status/scripts/__init__.py`（空文件）。

- [ ] **Step 2: 写 skill.md**

创建 `app/agent/skills/farm-status/skill.md`：

```markdown
---
name: get_farm_status
description: 获取当前农场综合状态，包括茬口、农事、花费、天气。触发词: 农场、茬口、农事、花费、建议
cache_ttl: 300
parameters:
  type: object
  properties: {}
---

# 农场状态查询

## 功能
获取当前农场综合状态摘要（≤300字），包括活跃茬口、近期农事、欠账、月度花费、天气。

## 示例
用户：「我的辣椒长得怎么样了」
→ get_farm_status()
```

- [ ] **Step 3: 写失败的测试**

创建 `tests/test_farm_status_skill.py`：

```python
"""get_farm_status Skill 单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from skillify.models.schemas import ResultStatus


class TestFarmStatusMeta:
    """Skill 元信息测试。"""

    def test_name(self):
        from app.agent.skills.farm_status.scripts.main import FarmStatusSkill

        skill = FarmStatusSkill()
        assert skill.name() == "get_farm_status"

    def test_description_contains_trigger_words(self):
        from app.agent.skills.farm_status.scripts.main import FarmStatusSkill

        skill = FarmStatusSkill()
        desc = skill.description()
        assert "农场" in desc or "茬口" in desc

    def test_parameters_schema_no_required(self):
        from app.agent.skills.farm_status.scripts.main import FarmStatusSkill

        skill = FarmStatusSkill()
        schema = skill.parameters_schema()
        assert schema["required"] == []


class TestFarmStatusExecution:
    """Skill 执行测试。"""

    @patch("app.agent.skills.farm_status.scripts.main.farm_context_service")
    @patch("app.agent.skills.farm_status.scripts.main.SessionLocal")
    def test_returns_farm_summary(self, mock_session_local, mock_fcs):
        from app.agent.skills.farm_status.scripts.main import FarmStatusSkill

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_fcs.build_summary.return_value = "【农场现状】\n茬口：辣椒(开花期)\n本月花费：1250元"

        skill = FarmStatusSkill()
        context = MagicMock(farm_id=1)
        result = skill.execute({}, context)
        # execute is async
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(result)

        assert result.status == ResultStatus.SUCCESS
        assert "辣椒" in result.reply
        assert "1250" in result.reply
        mock_fcs.build_summary.assert_called_once_with(mock_db, farm_id=1)
        mock_db.close.assert_called_once()

    @patch("app.agent.skills.farm_status.scripts.main.farm_context_service")
    @patch("app.agent.skills.farm_status.scripts.main.SessionLocal")
    def test_handles_db_error(self, mock_session_local, mock_fcs):
        from app.agent.skills.farm_status.scripts.main import FarmStatusSkill

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_fcs.build_summary.side_effect = Exception("DB error")

        skill = FarmStatusSkill()
        context = MagicMock(farm_id=1)
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(skill.execute({}, context))
        assert result.status == ResultStatus.FAILED
        mock_db.close.assert_called_once()
```

- [ ] **Step 4: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/test_farm_status_skill.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent.skills.farm_status'`

- [ ] **Step 5: 实现 Skill**

创建 `app/agent/skills/farm-status/scripts/main.py`：

```python
"""农场状态查询 Skill — 封装 farm_context_service 供 Agent 按需调用。"""

import logging

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.services import farm_context_service

logger = logging.getLogger(__name__)


class FarmStatusSkill(Skill):
    def name(self) -> str:
        return "get_farm_status"

    def description(self) -> str:
        return (
            "获取当前农场综合状态（茬口、近期农事、花费、天气）。"
            "当用户问到种植情况、农事进展、花费账目、需要整体建议时，"
            "调用此工具获取真实农场数据。"
        )

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    @cached(ttl_seconds=300, key_fn=lambda p: "farm_status")
    async def execute(self, params: dict, context) -> SkillResult:
        farm_id = getattr(context, "farm_id", 1) or 1
        db = SessionLocal()
        try:
            summary = farm_context_service.build_summary(db, farm_id=farm_id)
            return SkillResult(status=ResultStatus.SUCCESS, reply=summary)
        except Exception as e:
            logger.error("get_farm_status 失败 | farm_id=%d | error=%s", farm_id, e)
            return SkillResult(status=ResultStatus.FAILED, reply="获取农场状态失败，请稍后再试。")
        finally:
            db.close()
```

- [ ] **Step 6: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/test_farm_status_skill.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add app/agent/skills/farm-status/ tests/test_farm_status_skill.py
git commit -m "feat(skill): 新增 get_farm_status 只读 Skill，封装农场上下文供 Agent 按需调用"
```

---

### Task 2: 从 system prompt 移除 farm_context_summary 注入

**Files:**
- Modify: `prompts/base.j2`
- Modify: `app/agent/graph.py`
- Test: `tests/test_graph_user_setting.py` (已有，验证不回归)

- [ ] **Step 1: 修改 base.j2，移除 farm_context_summary 段**

删除 `prompts/base.j2` 末尾的：

```jinja2
{% if farm_context_summary %}
【农场现状】
{{ farm_context_summary }}
{% endif %}
```

替换为：

```jinja2
【农场状态查询】
- 用户问茬口、农事、花费、天气等实时数据时，先调用 get_farm_status 获取最新农场状态，再回答。
```

同时删除文件头部 `【能力范围】` 段中 `查看种植周期和当前阶段` 和 `了解近期农事记录` 和 `统计成本收支` 这三行（这些信息已由 get_farm_status 覆盖），保留：

```jinja2
【能力范围】
你具备以下工具调用能力：
- 查询天气预报和灾害预警
- 获取当前农场综合状态（茬口、农事、花费、天气）
```

- [ ] **Step 2: 修改 graph.py，移除 farm_context_service 调用**

在 `app/agent/graph.py` 的 `_llm_node` 函数中：

(a) 删除第 35 行的 import：
```python
from app.services import farm_context_service
```

(b) 删除 `_llm_node` 中获取 farm_context_summary 的整个 try/except 块（约第 182-206 行），简化为只获取 display_name 和 farm_location：

```python
farm_id = state.get("farm_id", 1)

db = SessionLocal()
try:
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    display_name = "农友"
    user_city = ""
    if farm and farm.user_id:
        user = db.query(User).filter(User.id == farm.user_id).first()
        if user:
            display_name = user.nickname
        user_setting = (
            db.query(UserSetting)
            .filter(UserSetting.user_id == farm.user_id)
            .first()
        )
        if user_setting and user_setting.default_city:
            user_city = user_setting.default_city
    farm_location = user_city or (farm.location if farm and farm.location else "")
except Exception:
    logger.warning("获取用户信息失败，使用默认值", exc_info=True)
    display_name = "农友"
    farm_location = ""
finally:
    db.close()
```

(c) 删除 `render_prompt` 调用中的 `"farm_context_summary": farm_context_summary,` 变量。

(d) 删除 except 块中的 `farm_context_summary = ""` 赋值。

- [ ] **Step 3: 运行已有测试验证不回归**

Run: `cd backend && python -m pytest tests/test_graph_user_setting.py -v`
Expected: PASS（如果因 CycleParseRequest import 失败，先跳过，在 Task 4 集成验证）

- [ ] **Step 4: 提交**

```bash
git add prompts/base.j2 app/agent/graph.py
git commit -m "refactor(agent): farm_context_summary 从 system prompt 移到 Skill 按需调用"
```

---

### Task 3: 新增 TOOL_CHAIN_MAP + 工具链扩展

**Files:**
- Modify: `app/agent/tool_selector.py`
- Create: `tests/test_tool_chain_map.py`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_tool_chain_map.py`：

```python
"""TOOL_CHAIN_MAP + expand_by_chain 单元测试。"""

from app.agent.tool_selector import TOOL_CHAIN_MAP, expand_by_chain


class TestToolChainMap:
    """工具链关联映射测试。"""

    def test_weather_chain(self):
        result = expand_by_chain({"weather"})
        assert "get_farm_status" in result

    def test_cost_chain(self):
        result = expand_by_chain({"get_cost_summary"})
        assert "get_farm_status" in result

    def test_crop_chain(self):
        result = expand_by_chain({"get_crop_cycle_info"})
        assert "get_farm_status" in result

    def test_write_skill_no_chain(self):
        result = expand_by_chain({"create_cost_record"})
        assert result == {"create_cost_record"}

    def test_empty_input(self):
        result = expand_by_chain(set())
        assert result == set()

    def test_multiple_inputs(self):
        result = expand_by_chain({"weather", "get_cost_summary"})
        assert "get_farm_status" in result
        assert "weather" in result
        assert "get_cost_summary" in result

    def test_max_tools_capped(self):
        result = expand_by_chain({"weather"}, max_tools=1)
        assert len(result) <= 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/test_tool_chain_map.py -v`
Expected: FAIL — `ImportError: cannot import name 'TOOL_CHAIN_MAP'`

- [ ] **Step 3: 实现 TOOL_CHAIN_MAP 和 expand_by_chain**

在 `app/agent/tool_selector.py` 末尾追加：

```python
TOOL_CHAIN_MAP: dict[str, list[str]] = {
    "weather": ["get_farm_status"],
    "get_cost_summary": ["get_farm_status"],
    "get_cost_analytics": ["get_farm_status"],
    "get_crop_cycle_info": ["get_farm_status"],
    "get_recent_farm_logs": ["get_farm_status"],
    "create_cost_record": [],
    "create_crop_cycle": [],
    "create_crop_template": [],
    "log_farm_activity": [],
    "update_crop_stage": [],
    "settle_debt": [],
    "get_farm_status": [],
}


def expand_by_chain(selected: set[str], max_tools: int = 5) -> set[str]:
    """根据工具链关联扩展选中工具集。

    当查询类工具被选中时，自动关联 get_farm_status，
    因为查询结果通常需要农场整体上下文来解读。
    """
    expanded = set(selected)
    for tool_name in list(selected):
        for related in TOOL_CHAIN_MAP.get(tool_name, []):
            expanded.add(related)
            if len(expanded) >= max_tools:
                return expanded
    return expanded
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/test_tool_chain_map.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/agent/tool_selector.py tests/test_tool_chain_map.py
git commit -m "feat(tool-selector): 新增 TOOL_CHAIN_MAP 工具链关联扩展"
```

---

### Task 4: 修改 graph.py 第二轮工具绑定逻辑

**Files:**
- Modify: `app/agent/graph.py`

- [ ] **Step 1: 修改第二轮工具绑定**

在 `app/agent/graph.py` 中，将：

```python
has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
if has_tool_results:
    selected_tools = tools
else:
    user_msg = _find_last_human_message(messages)
    selected_names = select_tools(
        user_msg, tools, intent_classifier=_get_classifier()
    )
    selected_tools = [t for t in tools if t.name in selected_names]
```

改为：

```python
from app.agent.tool_selector import expand_by_chain

has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
if has_tool_results:
    user_msg = _find_last_human_message(messages)
    selected_names = select_tools(
        user_msg, tools, intent_classifier=_get_classifier()
    )
    selected_names_set = expand_by_chain(set(selected_names))
    selected_tools = [t for t in tools if t.name in selected_names_set]
else:
    user_msg = _find_last_human_message(messages)
    selected_names = select_tools(
        user_msg, tools, intent_classifier=_get_classifier()
    )
    selected_tools = [t for t in tools if t.name in selected_names]
```

注意：将 `from app.agent.tool_selector import expand_by_chain` 添加到文件顶部的 import 区域（约第 38 行），不要放在函数内部。

- [ ] **Step 2: 运行 LLM 相关测试验证**

Run: `cd backend && python -m pytest tests/test_llm_load_balance.py tests/test_tool_chain_map.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add app/agent/graph.py
git commit -m "fix(agent): 第二轮工具绑定改用 TOOL_CHAIN_MAP 扩展，不再全量回退"
```

---

### Task 5: 升级 micro_compact 为 sliding window

**Files:**
- Modify: `app/agent/graph.py`（`micro_compact` 函数）
- Create: `tests/test_sliding_window.py`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_sliding_window.py`：

```python
"""Sliding Window 消息压缩单元测试。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.graph import sliding_window_compact


def _make_messages(rounds: int) -> list:
    """构建 N 轮对话消息列表。每轮 = Human + AI(tool_call) + Tool(result) + AI(reply)。"""
    messages = []
    for i in range(rounds):
        messages.append(HumanMessage(content=f"第{i+1}轮问题"))
        messages.append(AIMessage(content="", tool_calls=[{"id": f"tc{i}", "type": "function", "function": {"name": f"tool_{i}", "arguments": "{}"}}]))
        content = f"工具返回结果第{i+1}轮，包含很长的数据内容" * 10
        messages.append(ToolMessage(content=content, tool_call_id=f"tc{i}"))
        messages.append(AIMessage(content=f"第{i+1}轮回答"))
    return messages


class TestSlidingWindow:
    def test_short_history_unchanged(self):
        """少于 keep_rounds 的对话不做压缩。"""
        msgs = _make_messages(3)
        result = sliding_window_compact(msgs, keep_rounds=5)
        assert len(result) == len(msgs)

    def test_long_history_compressed(self):
        """超过 keep_rounds 的对话压缩旧消息。"""
        msgs = _make_messages(8)
        result = sliding_window_compact(msgs, keep_rounds=5)
        # 旧轮次应被压缩（ToolMessage 内容被截断）
        assert len(result) == len(msgs)
        # 最早的 ToolMessage 应被压缩
        old_tool_msgs = [
            m for m in result[:8]  # 前 8 条 = 前 2 轮
            if isinstance(m, ToolMessage)
        ]
        for m in old_tool_msgs:
            assert len(m.content) < 50  # 压缩后应该很短

    def test_recent_rounds_preserved(self):
        """最近 keep_rounds 轮完整保留。"""
        msgs = _make_messages(8)
        result = sliding_window_compact(msgs, keep_rounds=5)
        # 最后 5 轮的 ToolMessage 应完整
        recent_tool_msgs = [
            m for m in result[-20:]  # 最后 5 轮
            if isinstance(m, ToolMessage)
        ]
        for m in recent_tool_msgs:
            assert "很长的数据内容" in m.content

    def test_empty_messages(self):
        result = sliding_window_compact([], keep_rounds=5)
        assert result == []

    def test_human_messages_never_compressed(self):
        """HumanMessage 永远不压缩。"""
        msgs = _make_messages(8)
        result = sliding_window_compact(msgs, keep_rounds=5)
        for m in result:
            if isinstance(m, HumanMessage):
                assert len(m.content) > 0
                assert not m.content.startswith("[历史]")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/test_sliding_window.py -v`
Expected: FAIL — `ImportError: cannot import name 'sliding_window_compact'`

- [ ] **Step 3: 实现 sliding_window_compact**

在 `app/agent/graph.py` 中，将 `micro_compact` 函数（约第 97-113 行）替换为 `sliding_window_compact`：

```python
def sliding_window_compact(
    messages: list, keep_rounds: int = 5
) -> list:
    """Sliding window 消息压缩：最近 N 轮完整保留，旧 ToolMessage 截断。

    一轮 = 从 HumanMessage 到下一个 HumanMessage 之前的所有消息。
    """
    if not messages:
        return messages

    # 找到所有 HumanMessage 的位置（轮次分隔符）
    round_starts = []
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            round_starts.append(i)

    if len(round_starts) <= keep_rounds:
        return messages

    # 要压缩的轮次的截止位置
    compress_up_to = round_starts[-keep_rounds]

    result = list(messages)
    for i, msg in enumerate(result):
        if i >= compress_up_to:
            break
        if isinstance(msg, ToolMessage):
            content = msg.content or ""
            if len(content) > 50:
                tool_name = getattr(msg, "name", "unknown")
                result[i] = ToolMessage(
                    content=f"[已执行 {tool_name}]",
                    tool_call_id=msg.tool_call_id,
                )

    return result
```

同时将 `micro_compact` 的所有调用点（约第 231 行）替换：

```python
# 原: messages = micro_compact(state["messages"])
messages = sliding_window_compact(state["messages"])
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/test_sliding_window.py -v`
Expected: PASS

- [ ] **Step 5: 删除旧的 micro_compact 函数**

从 `app/agent/graph.py` 中删除 `micro_compact` 函数定义（已被 `sliding_window_compact` 替代）。同时删除模块级常量 `_KEEP_RECENT = 3`（不再需要）。

- [ ] **Step 6: 运行全部相关测试**

Run: `cd backend && python -m pytest tests/test_sliding_window.py tests/test_tool_chain_map.py tests/test_farm_status_skill.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add app/agent/graph.py tests/test_sliding_window.py
git commit -m "refactor(agent): micro_compact 升级为 sliding_window_compact，保留最近5轮完整对话"
```

---

### Task 6: 更新 tool_selector 的 SELECT_TOOLS 集成

**Files:**
- Modify: `app/agent/tool_selector.py` — 确保 `get_farm_status` 加入 `QUERY_TRIGGERS`

- [ ] **Step 1: 在 QUERY_TRIGGERS 中新增 get_farm_status 触发词**

在 `app/agent/tool_selector.py` 的 `QUERY_TRIGGERS` 字典中新增：

```python
"get_farm_status": {
    "农场", "茬口状态", "种植情况", "农事", "综合状态", "整体情况",
},
```

这样当用户说"我的农场怎么样"之类的话时，tool_selector 会选中 get_farm_status。

- [ ] **Step 2: 验证 tool_selector 选中 get_farm_status**

Run: `cd backend && python -c "
from app.agent.tool_selector import select_tools
# 模拟工具列表
tools = []
for name in ['get_farm_status', 'weather', 'get_cost_summary', 'create_cost_record']:
    from langchain_core.tools import BaseTool
    t = BaseTool(name=name, description='test')
    tools.append(t)
result = select_tools('我的辣椒长得怎么样了', tools)
print('Selected:', result)
assert 'get_farm_status' in result, f'Expected get_farm_status in {result}'
print('OK')
"`
Expected: `Selected: ['get_farm_status']` + `OK`

- [ ] **Step 3: 提交**

```bash
git add app/agent/tool_selector.py
git commit -m "feat(tool-selector): get_farm_status 加入 QUERY_TRIGGERS 触发词"
```

---

### Task 7: 集成验证 + 端到端测试

**Files:**
- Create: `tests/test_context_engineering_e2e.py`

- [ ] **Step 1: 写端到端验证测试**

创建 `tests/test_context_engineering_e2e.py`：

```python
"""上下文工程集成验证测试。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


class TestContextEngineeringIntegration:
    """验证三步改造的整体效果。"""

    def test_get_farm_status_skill_registered(self):
        """get_farm_status Skill 被 skillify 自动发现。"""
        from app.agent.skills import get_skill_manager

        manager = get_skill_manager()
        names = [s.name for s in manager.list_skills()]
        assert "get_farm_status" in names

    def test_base_prompt_no_farm_context(self):
        """base.j2 不再包含 farm_context_summary 变量。"""
        from app.agent.prompt_renderer import render_prompt
        from app.agent.prompt_registry import get_registry
        from datetime import date

        text = render_prompt(
            "system_base",
            variables={
                "display_name": "农友",
                "farm_location": "苏州",
                "current_season": "夏季",
            },
            registry=get_registry(),
            current_date=date(2026, 5, 29),
        )
        # 不应包含农场现状摘要
        assert "farm_context_summary" not in text
        # 应包含 get_farm_status 引导
        assert "get_farm_status" in text

    def test_sliding_window_function_exists(self):
        """sliding_window_compact 函数存在且可调用。"""
        from app.agent.graph import sliding_window_compact

        msgs = [
            HumanMessage(content="问题1"),
            AIMessage(content=""),
            ToolMessage(content="结果1" * 100, tool_call_id="tc1"),
            AIMessage(content="回答1"),
            HumanMessage(content="问题2"),
            AIMessage(content="回答2"),
        ]
        result = sliding_window_compact(msgs, keep_rounds=1)
        assert len(result) == len(msgs)

    def test_tool_chain_expansion(self):
        """TOOL_CHAIN_MAP 正确扩展工具链。"""
        from app.agent.tool_selector import expand_by_chain

        result = expand_by_chain({"weather"})
        assert "get_farm_status" in result
```

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && python -m pytest tests/test_context_engineering_e2e.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_context_engineering_e2e.py
git commit -m "test: 上下文工程三步改造集成验证"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Context as Tool → Task 1 (Skill) + Task 2 (prompt 移除)
- ✅ 工具筛选一致性 → Task 3 (TOOL_CHAIN_MAP) + Task 4 (graph.py 绑定)
- ✅ Sliding Window → Task 5 (sliding_window_compact)
- ✅ tool_selector 触发词 → Task 6
- ✅ 集成验证 → Task 7

**2. Placeholder scan:** 无 TBD/TODO/handle edge cases。

**3. Type consistency:**
- `sliding_window_compact(messages, keep_rounds=5)` → 测试中调用签名一致
- `expand_by_chain(selected: set[str], max_tools: int = 5)` → 测试和实现一致
- `FarmStatusSkill` 的 name/description/parameters_schema/execute → 测试和实现一致
