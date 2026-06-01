# Agent Parallel Tool Calling 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 LLM 一次返回多个 tool_calls，触发已有的 `_parallel_tool_node` 并行执行，并通过配置开关支持旧模型回退串行。

**Architecture:** 在 `bind_tools()` 层传入 `parallel_tool_calls=True`（配置控制），system prompt 增加 snippet 引导并行调用，`_parallel_tool_node` 增加聚合 trace 日志记录并行效果。

**Tech Stack:** Python 3.11, LangChain `ChatOpenAI.bind_tools()`, Jinja2 snippet, pytest + pytest-asyncio

---

## 文件变更清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `backend/app/core/config.py` | `AIConfig` 新增 `parallel_tool_calls` 字段 |
| 修改 | `backend/config.yaml` | 新增 `parallel_tool_calls: true` 配置项 |
| 修改 | `backend/app/agent/graph.py:296-297` | `bind_tools()` 条件传入 `parallel_tool_calls` |
| 修改 | `backend/app/agent/graph.py:478-483` | `_parallel_tool_node` 增加聚合 trace |
| 新建 | `backend/prompts/snippets/p1-parallel-tool.j2` | 并行调用引导 snippet |
| 修改 | `backend/prompts/config.yaml` | `system_base` composition 添加 `p1-parallel-tool` snippet |
| 新建 | `backend/tests/test_parallel_tool_calls.py` | 全部测试 |

---

### Task 1: AIConfig 新增 parallel_tool_calls 配置字段

**Files:**
- 修改: `backend/app/core/config.py:48-52` (AIConfig class)
- 修改: `backend/config.yaml:12-16` (ai section)
- 测试: `backend/tests/test_parallel_tool_calls.py`

- [ ] **Step 1: 写测试 — AIConfig 默认值为 True**

```python
# backend/tests/test_parallel_tool_calls.py
"""并行 tool calling 配置与 bind_tools 行为测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.core.config import AIConfig


class TestAIConfigParallel:
    """AIConfig.parallel_tool_calls 默认值与配置。"""

    def test_default_is_true(self):
        config = AIConfig()
        assert config.parallel_tool_calls is True

    def test_can_set_false(self):
        config = AIConfig(parallel_tool_calls=False)
        assert config.parallel_tool_calls is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py::TestAIConfigParallel -v`
Expected: FAIL — `AIConfig` has no field `parallel_tool_calls`

- [ ] **Step 3: 修改 AIConfig 添加字段**

在 `backend/app/core/config.py` 的 `AIConfig` 类（第 48-52 行）中添加字段：

```python
class AIConfig(BaseModel):
    model: str = "qwen3.6-flash-2026-04-16"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    enable_thinking: bool = False
    parallel_tool_calls: bool = True
```

在 `backend/config.yaml` 的 `ai:` section 中添加配置项：

```yaml
ai:
  model: "qwen3.6-35b-a3b"
  api_key: "sk-test-placeholder"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  enable_thinking: false
  parallel_tool_calls: true   # 启用 LLM 并行 tool calling（旧模型不支持时可关闭）
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py::TestAIConfigParallel -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/ljn/Documents/demo/explore/backend
git add app/core/config.py config.yaml tests/test_parallel_tool_calls.py
git commit -m "feat(config): 添加 AIConfig.parallel_tool_calls 配置字段"
```

---

### Task 2: bind_tools() 条件传入 parallel_tool_calls

**Files:**
- 修改: `backend/app/agent/graph.py:296-297` (`_llm_node` 中的 `bind_tools` 调用)
- 测试: `backend/tests/test_parallel_tool_calls.py` (追加)

- [ ] **Step 1: 写测试 — bind_tools 传入 parallel_tool_calls=True**

在 `backend/tests/test_parallel_tool_calls.py` 末尾追加：

```python
class TestBindToolsParallel:
    """bind_tools 根据 parallel_tool_calls 配置传入参数。"""

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.SessionLocal")
    @pytest.mark.asyncio
    async def test_bind_tools_passes_parallel_true_by_default(
        self, mock_session, mock_get_llm, mock_get_tools
    ):
        """parallel_tool_calls=True 时 bind_tools 传入该参数。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_db

        mock_tool = MagicMock()
        mock_tool.name = "get_weather_forecast"
        mock_get_tools.return_value = [mock_tool]

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="明天晴"))
        mock_get_llm.return_value = mock_llm

        from app.agent.graph import compile_advisor_graph

        graph = compile_advisor_graph()
        await graph.ainvoke(
            {"messages": [HumanMessage(content="明天天气")]}
        )

        mock_llm.bind_tools.assert_called_once()
        call_kwargs = mock_llm.bind_tools.call_args[1]
        assert call_kwargs.get("parallel_tool_calls") is True

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.SessionLocal")
    @pytest.mark.asyncio
    async def test_bind_tools_omits_parallel_when_disabled(
        self, mock_session, mock_get_llm, mock_get_tools
    ):
        """parallel_tool_calls=False 时不传入该参数。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_db

        mock_tool = MagicMock()
        mock_tool.name = "get_weather_forecast"
        mock_get_tools.return_value = [mock_tool]

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="明天晴"))
        mock_get_llm.return_value = mock_llm

        with patch("app.agent.graph.settings") as mock_settings:
            mock_settings.ai.parallel_tool_calls = False
            mock_settings.ai.enable_thinking = False
            mock_settings.token_quota.over_quota_action = "warn"
            from app.agent.graph import compile_advisor_graph

            graph = compile_advisor_graph()
            await graph.ainvoke(
                {"messages": [HumanMessage(content="明天天气")]}
            )

        mock_llm.bind_tools.assert_called_once()
        call_kwargs = mock_llm.bind_tools.call_args[1]
        assert "parallel_tool_calls" not in call_kwargs or call_kwargs.get("parallel_tool_calls") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py::TestBindToolsParallel::test_bind_tools_passes_parallel_true_by_default -v`
Expected: FAIL — `bind_tools` not called with `parallel_tool_calls=True`

- [ ] **Step 3: 修改 graph.py 的 bind_tools 调用**

将 `backend/app/agent/graph.py` 第 296-297 行：

```python
    if selected_tools:
        llm = raw_llm.bind_tools(selected_tools)
```

改为：

```python
    if selected_tools:
        bind_kwargs = {}
        if settings.ai.parallel_tool_calls:
            bind_kwargs["parallel_tool_calls"] = True
        llm = raw_llm.bind_tools(selected_tools, **bind_kwargs)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py::TestBindToolsParallel -v`
Expected: 2 passed

- [ ] **Step 5: 运行既有测试确认无回归**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_function_calling_e2e.py -v`
Expected: ALL passed（既有测试 mock 了 `bind_tools` 返回自身，不受新参数影响）

- [ ] **Step 6: 提交**

```bash
cd /Users/ljn/Documents/demo/explore/backend
git add app/agent/graph.py tests/test_parallel_tool_calls.py
git commit -m "feat(agent): bind_tools 条件传入 parallel_tool_calls 参数"
```

---

### Task 3: System prompt 添加并行调用引导 snippet

**Files:**
- 新建: `backend/prompts/snippets/p1-parallel-tool.j2`
- 修改: `backend/prompts/config.yaml:20-30` (`system_base` composition)
- 测试: `backend/tests/test_parallel_tool_calls.py` (追加)

- [ ] **Step 1: 创建 snippet 文件**

创建 `backend/prompts/snippets/p1-parallel-tool.j2`：

```jinja2
【并行工具调用】
当用户的问题需要调用多个工具时，你应该在一次回复中同时返回所有需要的工具调用，而不是逐个调用。例如用户同时问天气和成本，你应该同时调用天气和成本查询工具。
```

- [ ] **Step 2: 在 config.yaml 的 system_base composition 中添加 snippet**

修改 `backend/prompts/config.yaml` 的 `system_base` composition，在 `snippets` 列表的 `p1-tool-guardrails` 之后添加 `p1-parallel-tool`：

```yaml
  system_base:
    snippets:
      - p1-language
      - p1-tool-guardrails
      - p1-parallel-tool
      - p2-role
      - p2-capability
      - p3-format
      - p3-style
      - p4-context
    separator: "\n\n"
```

- [ ] **Step 3: 写测试验证 snippet 被渲染**

在 `backend/tests/test_parallel_tool_calls.py` 末尾追加：

```python
class TestParallelToolSnippet:
    """并行调用引导 snippet 加载与渲染。"""

    def test_snippet_loaded(self):
        from app.agent.prompt_composer import get_composer

        composer = get_composer()
        assert "p1-parallel-tool" in composer.list_snippets()

    def test_system_base_contains_parallel_guidance(self):
        from app.agent.prompt_composer import get_composer

        composer = get_composer()
        rendered = composer.compose(
            "system_base",
            variables={
                "display_name": "农友",
                "farm_location": "徐州",
                "current_season": "夏季",
            },
        )
        assert "并行工具调用" in rendered
        assert "同时返回所有需要的工具调用" in rendered
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py::TestParallelToolSnippet -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/ljn/Documents/demo/explore/backend
git add prompts/snippets/p1-parallel-tool.j2 prompts/config.yaml tests/test_parallel_tool_calls.py
git commit -m "feat(prompt): 添加并行工具调用引导 snippet"
```

---

### Task 4: _parallel_tool_node 增加聚合 trace 日志

**Files:**
- 修改: `backend/app/agent/graph.py:478-484` (`_parallel_tool_node` 末尾)
- 测试: `backend/tests/test_parallel_tool_calls.py` (追加)

- [ ] **Step 1: 写测试 — 并行执行时记录 parallel_batch trace**

在 `backend/tests/test_parallel_tool_calls.py` 末尾追加：

```python
class TestParallelBatchTrace:
    """并行执行聚合 trace 日志测试。"""

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.get_collector")
    @pytest.mark.asyncio
    async def test_parallel_batch_trace_recorded(
        self, mock_get_collector, mock_get_llm, mock_get_tools
    ):
        """并行执行 2 个 Skill 时记录 parallel_batch 聚合 trace。"""
        mock_collector = MagicMock()
        mock_get_collector.return_value = mock_collector

        weather_tool = MagicMock()
        weather_tool.name = "get_weather_forecast"
        weather_tool.ainvoke = AsyncMock(return_value="晴天 25度")

        cost_tool = MagicMock()
        cost_tool.name = "get_cost_summary"
        cost_tool.ainvoke = AsyncMock(return_value="本月花费 500 元")

        mock_get_tools.return_value = [weather_tool, cost_tool]

        from app.agent.graph import _parallel_tool_node, AgentState

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "get_weather_forecast", "args": {"city": "徐州"}, "id": "tc1"},
                        {"name": "get_cost_summary", "args": {}, "id": "tc2"},
                    ],
                )
            ],
            "farm_id": 1,
        }

        result = await _parallel_tool_node(state)
        assert len(result["messages"]) == 2

        # 验证 parallel_batch trace 被记录
        batch_calls = [
            c for c in mock_collector.record.call_args_list
            if c[1].get("node_type") == "parallel_batch"
        ]
        assert len(batch_calls) == 1
        batch_data = batch_calls[0][1]
        assert batch_data["output_data"]["parallel_count"] == 2
        assert len(batch_data["output_data"]["skills"]) == 2

    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_collector")
    @pytest.mark.asyncio
    async def test_single_skill_no_batch_trace(
        self, mock_get_collector, mock_get_tools
    ):
        """单 Skill 执行时不记录 parallel_batch trace。"""
        mock_collector = MagicMock()
        mock_get_collector.return_value = mock_collector

        weather_tool = MagicMock()
        weather_tool.name = "get_weather_forecast"
        weather_tool.ainvoke = AsyncMock(return_value="晴天 25度")
        mock_get_tools.return_value = [weather_tool]

        from app.agent.graph import _parallel_tool_node, AgentState

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "get_weather_forecast", "args": {"city": "徐州"}, "id": "tc1"},
                    ],
                )
            ],
            "farm_id": 1,
        }

        result = await _parallel_tool_node(state)
        assert len(result["messages"]) == 1

        # 验证没有 parallel_batch trace
        batch_calls = [
            c for c in mock_collector.record.call_args_list
            if c[1].get("node_type") == "parallel_batch"
        ]
        assert len(batch_calls) == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py::TestParallelBatchTrace::test_parallel_batch_trace_recorded -v`
Expected: FAIL — `parallel_batch` trace not recorded

- [ ] **Step 3: 修改 _parallel_tool_node 增加聚合 trace**

将 `backend/app/agent/graph.py` 第 478-484 行：

```python
    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("并行执行 %d 个 Skill", len(last.tool_calls))
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])

    return {"messages": results}
```

改为：

```python
    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("并行执行 %d 个 Skill", len(last.tool_calls))
        batch_start = _time.perf_counter()
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])
        batch_duration = int((_time.perf_counter() - batch_start) * 1000)
        skill_timings = []
        for tc, msg in zip(last.tool_calls, results):
            duration = None
            for call_record in collector._records if hasattr(collector, "_records") else []:
                if call_record.get("node_name") == tc["name"]:
                    duration = call_record.get("duration_ms", 0)
                    break
            skill_timings.append({
                "name": tc["name"],
                "duration_ms": duration,
            })
        collector.record(
            node_type="parallel_batch",
            node_name=f"parallel_{len(results)}_skills",
            output_data={
                "parallel_count": len(results),
                "skills": [{"name": tc["name"]} for tc in last.tool_calls],
            },
            duration_ms=batch_duration,
        )

    return {"messages": results}
```

注意：聚合 trace 的 `skills` 列表只记录 Skill 名称（不依赖 collector 内部状态获取各 Skill 耗时，因为各 Skill 的 trace 已独立记录）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py::TestParallelBatchTrace -v`
Expected: 2 passed

- [ ] **Step 5: 运行全部新测试确认无回归**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_parallel_tool_calls.py -v`
Expected: ALL passed (8 tests)

- [ ] **Step 6: 运行既有测试确认无回归**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/test_function_calling_e2e.py -v`
Expected: ALL passed

- [ ] **Step 7: 提交**

```bash
cd /Users/ljn/Documents/demo/explore/backend
git add app/agent/graph.py tests/test_parallel_tool_calls.py
git commit -m "feat(agent): _parallel_tool_node 增加并行执行聚合 trace 日志"
```

---

### Task 5: 全量回归测试与 lint 检查

**Files:** 无新增修改，仅验证

- [ ] **Step 1: 运行后端全量测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest -v --timeout=60`
Expected: ALL passed

- [ ] **Step 2: 运行 lint 检查**

Run: `cd /Users/ljn/Documents/demo/explore/backend && ruff check . && ruff format .`
Expected: 无错误（如有格式问题，ruff format 会自动修复，重新运行确认通过）

- [ ] **Step 3: 最终提交（如有 lint 修复）**

```bash
cd /Users/ljn/Documents/demo/explore/backend
git add -A
git commit -m "chore: lint 修复"
```
