# Multi-Intent Mixed Results 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 多意图消息（query + write 混合 tool call）时，query 结果和 write 确认提示都展示给用户，不丢失数据。

**Architecture:** `_llm_node` 开头的 pending 检测从二元判断改为三路分支：全 pending → 仅确认文案（不变）；全 normal → 正常调 LLM（不变）；混合 → 拼接 normal 摘要 + pending 确认文案，不调 LLM。

**Tech Stack:** Python 3.12, LangGraph, LangChain Core (AIMessage/ToolMessage), pytest + pytest-asyncio

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/agent/graph.py:163-171` | 修改 | `_llm_node` 三路分支：混合 ToolMessage 合并逻辑 |
| `backend/tests/test_mixed_tool_results.py` | 新建 | 混合/纯 pending/纯 normal 三路分支测试 |

> 注：`pending_actions.py` 的 `build_confirm_message` 已有完整的参数可读性格式化（`_SKILL_PARAM_FORMAT` + `_SKILL_EMOJI` + `_SKILL_DISPLAY`），无需改动。

---

### Task 1: 新建测试文件，编写混合 ToolMessage 的失败测试

**Files:**
- Create: `backend/tests/test_mixed_tool_results.py`

- [ ] **Step 1: 创建测试文件骨架和第一个失败测试**

```python
"""测试 _llm_node 混合 ToolMessage 三路分支处理。"""

from unittest.mock import MagicMock

import pytest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.graph import _llm_node
from app.infra.pending_actions import PENDING_MARKER


class TestMixedToolMessages:
    """测试混合 pending + normal ToolMessage 的合并逻辑。"""

    @pytest.mark.asyncio
    async def test_mixed_returns_combined_content(self):
        """pending + normal 混合时，返回包含两部分内容的 AIMessage。"""
        normal_msg = ToolMessage(
            content="今天天气：晴，25°C，湿度60%，东南风3级。",
            tool_call_id="tc_weather",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 🌱 确认创建茬口：玉米 春季，确认吗？",
            tool_call_id="tc_crop",
        )
        state = {
            "messages": [normal_msg, pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        assert isinstance(ai_msg, AIMessage)
        # query 结果应包含在回复中
        assert "晴" in ai_msg.content
        assert "25°C" in ai_msg.content
        # confirm 提示应包含在回复中
        assert "确认" in ai_msg.content
        assert "玉米" in ai_msg.content

    @pytest.mark.asyncio
    async def test_mixed_does_not_call_llm(self):
        """混合场景下不应调用 LLM。"""
        normal_msg = ToolMessage(
            content="本月支出：2000元",
            tool_call_id="tc_summary",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [normal_msg, pending_msg],
            "farm_id": 1,
        }

        with pytest.raises(Exception):
            # 如果调了 LLM，会因为未 mock 而抛异常
            # 但混合场景不应走到 LLM，所以不应抛异常
            pass

        # 直接调用，应不抛异常（因为不调 LLM）
        result = await _llm_node(state)
        assert isinstance(result["messages"][0], AIMessage)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && poetry run pytest tests/test_mixed_tool_results.py::TestMixedToolMessages::test_mixed_returns_combined_content -v`
Expected: FAIL — 当前 `_llm_node` 只返回 pending 确认文案，不含 normal ToolMessage 内容（天气数据丢失）

---

### Task 2: 实现 `_llm_node` 三路分支

**Files:**
- Modify: `backend/app/agent/graph.py:163-171`

- [ ] **Step 1: 替换 `_llm_node` 开头的 pending 检测为三路分支**

将 `backend/app/agent/graph.py` 第 167-171 行：

```python
    pending_msgs = [m for m in messages if is_pending_tool_message(m)]
    if pending_msgs:
        confirm = pending_msgs[-1].content.replace(PENDING_MARKER, "").strip()
        logger.info("检测到 pending ToolMessage，跳过 LLM 直接确认 | text=%s", confirm)
        return {"messages": [AIMessage(content=confirm)]}
```

替换为：

```python
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    pending_msgs = [m for m in tool_msgs if is_pending_tool_message(m)]
    normal_msgs = [m for m in tool_msgs if not is_pending_tool_message(m)]

    if pending_msgs and normal_msgs:
        summaries = []
        for m in normal_msgs:
            content = str(m.content or "")
            if content:
                summaries.append(content[:200])
        confirm_parts = []
        for m in pending_msgs:
            confirm = m.content.replace(PENDING_MARKER, "").strip()
            confirm_parts.append(confirm)
        combined = "\n\n".join(summaries) + "\n\n" + "\n\n".join(confirm_parts)
        logger.info(
            "混合 ToolMessage | pending=%d normal=%d | 跳过 LLM 合并回复",
            len(pending_msgs),
            len(normal_msgs),
        )
        return {"messages": [AIMessage(content=combined)]}

    if pending_msgs:
        confirm = pending_msgs[-1].content.replace(PENDING_MARKER, "").strip()
        logger.info("检测到 pending ToolMessage，跳过 LLM 直接确认 | text=%s", confirm)
        return {"messages": [AIMessage(content=confirm)]}
```

- [ ] **Step 2: 运行混合测试验证通过**

Run: `cd backend && poetry run pytest tests/test_mixed_tool_results.py::TestMixedToolMessages::test_mixed_returns_combined_content -v`
Expected: PASS

- [ ] **Step 3: 运行混合 LLM 未调用测试验证通过**

Run: `cd backend && poetry run pytest tests/test_mixed_tool_results.py::TestMixedToolMessages::test_mixed_does_not_call_llm -v`
Expected: PASS

---

### Task 3: 补充纯 pending 和纯 normal 路径的回归测试

**Files:**
- Modify: `backend/tests/test_mixed_tool_results.py`

- [ ] **Step 1: 在 `TestMixedToolMessages` 类之后添加两个测试类**

```python
class TestPurePendingPath:
    """测试纯 pending ToolMessage 路径不变。"""

    @pytest.mark.asyncio
    async def test_pure_pending_returns_confirm_only(self):
        """只有 pending ToolMessage 时，仅返回确认文案（不变）。"""
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 200元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        assert isinstance(ai_msg, AIMessage)
        assert "确认记账" in ai_msg.content
        assert "化肥" in ai_msg.content
        assert PENDING_MARKER not in ai_msg.content

    @pytest.mark.asyncio
    async def test_multiple_pending_returns_last(self):
        """多个 pending ToolMessage 时，返回最后一个的确认文案（不变）。"""
        pending1 = ToolMessage(
            content=f"{PENDING_MARKER} 🌱 确认创建茬口：玉米，确认吗？",
            tool_call_id="tc1",
        )
        pending2 = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc2",
        )
        state = {
            "messages": [pending1, pending2],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        # 纯 pending 路径取最后一个
        assert "确认记账" in ai_msg.content


class TestPureNormalPath:
    """测试纯 normal ToolMessage 路径不变（正常走 LLM）。"""

    @pytest.mark.asyncio
    async def test_pure_normal_does_not_early_return(self):
        """只有 normal ToolMessage 时，不提前返回（走 LLM 流程）。"""
        from unittest.mock import AsyncMock, patch

        normal_msg = ToolMessage(
            content="本月支出：2000元",
            tool_call_id="tc_summary",
        )
        state = {
            "messages": [normal_msg],
            "farm_id": 1,
        }

        # 需要完整 mock 因为会走 LLM
        with (
            patch("app.agent.graph.get_llm") as mock_get_llm,
            patch("app.agent.graph.get_langchain_tools", return_value=[]),
            patch("app.agent.graph.get_composer") as mock_get_composer,
            patch("app.agent.graph.get_request_date") as mock_get_date,
            patch("app.agent.graph.get_collector") as mock_collector,
            patch("app.agent.graph.check_quota", return_value=True),
            patch("app.agent.graph.select_tools", return_value=[]),
            patch("app.agent.graph._get_classifier", return_value=None),
            patch("app.agent.graph.SessionLocal") as mock_session,
        ):
            mock_get_date.return_value = __import__("datetime").date(2026, 5, 30)
            mock_composer = MagicMock()
            mock_composer.compose.return_value = "system prompt"
            mock_get_composer.return_value = mock_composer
            mock_collector.return_value = MagicMock()

            # mock db query chain
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_db

            # mock LLM
            llm = MagicMock()
            llm.model_name = "test-model"
            llm.ainvoke = AsyncMock(
                return_value=MagicMock(
                    content="LLM 回复",
                    tool_calls=[],
                    response_metadata={"token_usage": {"total_tokens": 10}},
                ),
            )
            mock_get_llm.return_value = llm

            result = await _llm_node(state)
            ai_msg = result["messages"][0]

            assert isinstance(ai_msg, AIMessage)
            assert ai_msg.content == "LLM 回复"
            # 验证 LLM 确实被调用了
            llm.ainvoke.assert_called_once()
```

- [ ] **Step 2: 运行所有新增测试**

Run: `cd backend && poetry run pytest tests/test_mixed_tool_results.py -v`
Expected: 5 tests PASS

---

### Task 4: 补充边界情况测试

**Files:**
- Modify: `backend/tests/test_mixed_tool_results.py`

- [ ] **Step 1: 在文件末尾添加边界测试类**

```python
class TestMixedEdgeCases:
    """混合场景边界情况。"""

    @pytest.mark.asyncio
    async def test_normal_content_truncated_at_200(self):
        """normal ToolMessage 内容超 200 字符时截断。"""
        long_content = "天气详情：" + "晴，" * 200  # 远超 200 字符
        normal_msg = ToolMessage(
            content=long_content,
            tool_call_id="tc_weather",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [normal_msg, pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        # normal 内容应被截断，不应包含完整的 1000+ 字符
        assert len([line for line in ai_msg.content.split("\n") if "天气" in line and "晴" in line][0]) <= 250

    @pytest.mark.asyncio
    async def test_error_normal_tool_still_included(self):
        """normal ToolMessage 内容是错误信息时仍然包含。"""
        error_msg = ToolMessage(
            content="工具调用失败: 天气服务不可用",
            tool_call_id="tc_weather",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [error_msg, pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        assert "工具调用失败" in ai_msg.content
        assert "确认记账" in ai_msg.content

    @pytest.mark.asyncio
    async def test_empty_messages_returns_normally(self):
        """空消息列表不应在 pending 分支报错。"""
        state = {"messages": [], "farm_id": 1}

        # 空 messages 没有 ToolMessage，不应触发任何 pending 分支
        # 应走 LLM 流程（需要 mock）
        from unittest.mock import AsyncMock, patch

        with (
            patch("app.agent.graph.get_llm") as mock_get_llm,
            patch("app.agent.graph.get_langchain_tools", return_value=[]),
            patch("app.agent.graph.get_composer") as mock_get_composer,
            patch("app.agent.graph.get_request_date") as mock_get_date,
            patch("app.agent.graph.get_collector") as mock_collector,
            patch("app.agent.graph.check_quota", return_value=True),
            patch("app.agent.graph.select_tools", return_value=[]),
            patch("app.agent.graph._get_classifier", return_value=None),
            patch("app.agent.graph.SessionLocal") as mock_session,
        ):
            mock_get_date.return_value = __import__("datetime").date(2026, 5, 30)
            mock_composer = MagicMock()
            mock_composer.compose.return_value = "system prompt"
            mock_get_composer.return_value = mock_composer
            mock_collector.return_value = MagicMock()

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_db

            llm = MagicMock()
            llm.model_name = "test-model"
            llm.ainvoke = AsyncMock(
                return_value=MagicMock(
                    content="你好",
                    tool_calls=[],
                    response_metadata={"token_usage": {"total_tokens": 5}},
                ),
            )
            mock_get_llm.return_value = llm

            result = await _llm_node(state)
            assert isinstance(result["messages"][0], AIMessage)
```

- [ ] **Step 2: 运行全部测试**

Run: `cd backend && poetry run pytest tests/test_mixed_tool_results.py -v`
Expected: 8 tests PASS

---

### Task 5: 运行现有测试确认无回归

- [ ] **Step 1: 运行 pending_actions 相关测试**

Run: `cd backend && poetry run pytest tests/test_pending_actions.py -v`
Expected: ALL PASS

- [ ] **Step 2: 运行 graph 相关测试**

Run: `cd backend && poetry run pytest tests/test_graph_user_setting.py -v`
Expected: ALL PASS

- [ ] **Step 3: 运行 function calling e2e 测试**

Run: `cd backend && poetry run pytest tests/test_function_calling_e2e.py -v`
Expected: ALL PASS

---

### Task 6: 提交

- [ ] **Step 1: 暂存并提交**

```bash
git add backend/app/agent/graph.py backend/tests/test_mixed_tool_results.py
git commit -m "feat(agent): 多意图混合 ToolMessage 三路分支合并

_llm_node 将 ToolMessage 分为 pending/normal 两组：
- 全 pending: 仅确认文案（不变）
- 全 normal: 走 LLM（不变）
- 混合: 拼接 normal 摘要(200字截断) + pending 确认文案，不调 LLM

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 2: 确认提交成功**

Run: `git status`
Expected: clean working tree for the changed files
