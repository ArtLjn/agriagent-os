# Tool Pre-Filter 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `bind_tools()` 前用两层规则匹配（写操作 regex + 查询操作 keyword）将 10 个 Tool 缩减到 1-3 个候选，提升弱模型 tool selection 准确率到 95%+。

**Architecture:** 新增 `agent/tool_selector.py` 独立模块，`select_tools()` 被 `_llm_node` 调用。Layer 1 用 regex 确定性匹配写操作 Tool（记账/还账/建茬口/记农事/更新阶段），Layer 2 用策划触发词表匹配查询 Tool（天气/余额/趋势/日志/茬口详情）。无命中时 fallback 全量注入。Spike 验证：34 用例 100% 召回。

**Tech Stack:** Python 3.11, re（标准库 regex）, LangChain StructuredTool, LangGraph StateGraph, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/agent/tool_selector.py` | **创建** | 两层预筛：WRITE_PATTERNS（regex）+ QUERY_TRIGGERS（keyword）+ select_tools() |
| `backend/app/agent/graph.py` | **修改** | `_llm_node` 第 104-106 行：加 select_tools() 调用 |
| `backend/tests/test_tool_selector.py` | **创建** | 3 个测试类：写操作 regex / 查询 keyword / fallback |
| `backend/tests/test_function_calling_e2e.py` | **修改** | 新增 test_pre_filter_reduces_tools 测试 |

**不改动的文件：**
- `app/agent/skills/` — Tool 定义不变
- `prompts/base.j2` — System prompt 不变
- `app/agent/graph.py` 的图结构（节点/边）不变

---

### Task 1: 创建 tool_selector.py — 写操作 Regex 模式

**Files:**
- Create: `backend/app/agent/tool_selector.py`
- Test: `backend/tests/test_tool_selector.py`

- [ ] **Step 1: 写 test_tool_selector.py — TestWritePatternMatching**

创建 `backend/tests/test_tool_selector.py`：

```python
"""Tool 预筛选模块单元测试。"""

import pytest

from app.agent.tool_selector import select_tools


def _all_tool_names():
    return [
        "weather",
        "get_cost_summary",
        "get_cost_analytics",
        "create_cost_record",
        "settle_debt",
        "create_crop_cycle",
        "get_crop_cycle_info",
        "get_recent_farm_logs",
        "log_farm_activity",
        "update_crop_stage",
    ]


class TestWritePatternMatching:
    """写操作 Tool 通过 regex 确定性匹配。"""

    @pytest.mark.parametrize(
        "user_msg,expected_tool",
        [
            ("卖了西瓜5000块", "create_cost_record"),
            ("记一笔，买了化肥", "create_cost_record"),
            ("花了3000买农药", "create_cost_record"),
            ("今天收入了2万", "create_cost_record"),
            ("昨天支出500块人工费", "create_cost_record"),
            ("赊账买了2000的化肥", "create_cost_record"),
            ("昨天买了10w的设备", "create_cost_record"),
            ("卖西瓜收入5w", "create_cost_record"),
            ("付了老李2000人工费", "create_cost_record"),
            ("还了老王500", "settle_debt"),
            ("把欠老王的账结了", "settle_debt"),
            ("还款1000给张三", "settle_debt"),
            ("清账，不欠了", "settle_debt"),
            ("帮我创建春茬种植西瓜", "create_crop_cycle"),
            ("建茬口，种辣椒", "create_crop_cycle"),
            ("秋茬种番茄", "create_crop_cycle"),
            ("今天浇了水", "log_farm_activity"),
            ("施了肥", "log_farm_activity"),
            ("打了药", "log_farm_activity"),
            ("西瓜进苗期了", "update_crop_stage"),
            ("到开花期了", "update_crop_stage"),
            ("阶段更新到结果期", "update_crop_stage"),
        ],
    )
    def test_write_tool_matched(self, user_msg, expected_tool):
        result = select_tools(user_msg, _all_tool_names())
        assert expected_tool in result, (
            f"Expected {expected_tool} in result for '{user_msg}', got {result}"
        )

    def test_ambiguous_input_no_false_positive_write(self):
        result = select_tools("买化肥", _all_tool_names())
        all_tools = _all_tool_names()
        assert result == all_tools
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_tool_selector.py::TestWritePatternMatching -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.agent.tool_selector'`）

- [ ] **Step 3: 创建 tool_selector.py**

创建 `backend/app/agent/tool_selector.py`：

```python
"""Tool 预筛选模块 — 两层规则匹配减少 LLM 候选 Tool 数量。

Layer 1: 写操作 Regex 模式匹配（deterministic）
Layer 2: 查询操作触发词匹配（keyword）
Fallback: 无命中时返回全量 Tool
"""

import logging
import re

logger = logging.getLogger(__name__)

WRITE_PATTERNS: dict[str, list[re.Pattern]] = {
    "create_cost_record": [
        re.compile(r"(买了|卖了|花了|收入|支出|赊账|记账|记一笔|付了|收了)"),
        re.compile(r"\d+\s*(元|块|万|w|W|千|百)"),
    ],
    "settle_debt": [
        re.compile(r"(还[了钱账给]|清账|结清|欠款|还款)"),
        re.compile(r"(账[结清]|结了.*账|欠.*结)"),
    ],
    "create_crop_cycle": [
        re.compile(r"(创建|建|开)\s*.*茬口"),
        re.compile(r"(种植|种[了上下]?)\s*(西瓜|番茄|辣椒|豆角|黄瓜|玉米|棉花|花生|白菜|草莓)"),
        re.compile(r"(春茬|秋茬|夏茬|冬茬)"),
    ],
    "log_farm_activity": [
        re.compile(r"(浇[了水]|施[了肥]|打[了药]|除[了草]|翻[了地]|播[了种])"),
        re.compile(r"(记录|记下)\s*(农事|操作|浇水|施肥)"),
    ],
    "update_crop_stage": [
        re.compile(r"(进[了入]?).*(期|阶段)"),
        re.compile(r"(到[了]?|进入)\s*(苗期|开花期|结果期|采收期|伸蔓期|定植期)"),
    ],
}

QUERY_TRIGGERS: dict[str, set[str]] = {
    "weather": {"天气", "预报", "降雨", "温度", "极端天气", "雨"},
    "get_cost_summary": {
        "余额",
        "收支",
        "成本",
        "利润",
        "花了多少",
        "赚了多少",
        "账单",
        "月额",
    },
    "get_cost_analytics": {"趋势", "对比", "比去年", "比上月", "收支分析", "同比", "环比"},
    "get_crop_cycle_info": {"茬口状态", "当前阶段", "周期进度", "茬口详情", "长到哪了"},
    "get_recent_farm_logs": {"农事记录", "最近操作", "日志", "干了啥", "农活"},
}

_WRITE_TOOL_NAMES = set(WRITE_PATTERNS.keys())
_QUERY_TOOL_NAMES = set(QUERY_TRIGGERS.keys())


def _match_write_tools(user_message: str) -> set[str]:
    """Layer 1: 写操作 Regex 模式匹配。"""
    matched = set()
    for tool_name, patterns in WRITE_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(user_message):
                matched.add(tool_name)
                break
    return matched


def _match_query_tools(user_message: str) -> set[str]:
    """Layer 2: 查询操作触发词匹配。"""
    matched = set()
    for tool_name, triggers in QUERY_TRIGGERS.items():
        for word in triggers:
            if word in user_message:
                matched.add(tool_name)
                break
    return matched


def select_tools(user_message: str, all_tool_names: list[str]) -> list[str]:
    """根据用户消息预筛选候选 Tool。

    Args:
        user_message: 用户最新一条消息。
        all_tool_names: 全量 Tool 名称列表。

    Returns:
        候选 Tool 名称列表。无命中时返回全量（fallback）。
    """
    write_matched = _match_write_tools(user_message)
    query_matched = _match_query_tools(user_message)
    candidates = write_matched | query_matched

    if not candidates:
        logger.info(
            "tool_pre_filter | input=%s | candidates=ALL(fallback) | total=%d",
            user_message[:50],
            len(all_tool_names),
        )
        return all_tool_names

    candidate_names = [t for t in all_tool_names if t in candidates]

    logger.info(
        "tool_pre_filter | input=%s | candidates=%s | total=%d",
        user_message[:50],
        candidate_names,
        len(all_tool_names),
    )
    return candidate_names
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_tool_selector.py::TestWritePatternMatching -v`
Expected: 23 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ljn/Documents/demo/explore/backend && git add app/agent/tool_selector.py tests/test_tool_selector.py && git commit -m "feat: tool_selector 两层预筛 — 写操作 regex + 查询 keyword"
```

---

### Task 2: 测试 — 查询操作 Keyword 匹配 + Fallback

**Files:**
- Modify: `backend/tests/test_tool_selector.py`

- [ ] **Step 1: 追加 TestQueryKeywordMatching 和 TestFallback 测试类**

在 `backend/tests/test_tool_selector.py` 末尾追加：

```python
class TestQueryKeywordMatching:
    """查询操作 Tool 通过策划触发词表匹配。"""

    @pytest.mark.parametrize(
        "user_msg,expected_tool",
        [
            ("今天天气", "weather"),
            ("我的余额", "get_cost_summary"),
            ("我的月额", "get_cost_summary"),
            ("最近有雨吗", "weather"),
            ("利润怎么样", "get_cost_summary"),
            ("最近干了啥", "get_recent_farm_logs"),
            ("茬口状态怎么样", "get_crop_cycle_info"),
            ("比上月花了多少", "get_cost_analytics"),
        ],
    )
    def test_query_tool_matched(self, user_msg, expected_tool):
        result = select_tools(user_msg, _all_tool_names())
        assert expected_tool in result, (
            f"Expected {expected_tool} in result for '{user_msg}', got {result}"
        )

    def test_multi_intent_matches_both(self):
        result = select_tools("看看天气和成本", _all_tool_names())
        assert "weather" in result
        assert "get_cost_summary" in result


class TestFallback:
    """无命中时返回全量 Tool。"""

    @pytest.mark.parametrize(
        "user_msg",
        ["你好", "西瓜怎么种", "早上好", "谢谢"],
    )
    def test_fallback_returns_all(self, user_msg):
        all_tools = _all_tool_names()
        result = select_tools(user_msg, all_tools)
        assert result == all_tools

    def test_fallback_preserves_order(self):
        all_tools = _all_tool_names()
        result = select_tools("你好", all_tools)
        assert result == all_tools
```

- [ ] **Step 2: 运行全部测试确认通过**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_tool_selector.py -v`
Expected: 全部 PASS（23 write + 9 query + 1 multi-intent + 4 fallback = 37）

- [ ] **Step 3: Commit**

```bash
cd /Users/ljn/Documents/demo/explore/backend && git add tests/test_tool_selector.py && git commit -m "test: tool_selector 查询 keyword + fallback 测试"
```

---

### Task 3: graph.py 集成 — _llm_node 加预筛

**Files:**
- Modify: `backend/app/agent/graph.py` (lines 104-106)
- Modify: `backend/tests/test_function_calling_e2e.py`

- [ ] **Step 1: 追加 e2e 测试验证预筛**

在 `backend/tests/test_function_calling_e2e.py` 末尾追加：

```python
    @patch("app.agent.graph.get_langchain_tools")
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.farm_context_service.build_summary")
    @patch("app.agent.graph.SessionLocal")
    def test_pre_filter_reduces_tools(
        self, mock_session, mock_summary, mock_get_llm, mock_get_tools
    ):
        """预筛后 bind_tools 应只注入匹配的 Tool。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            display_name="老李"
        )
        mock_session.return_value = mock_db
        mock_summary.return_value = ""

        weather_tool = MagicMock()
        weather_tool.name = "weather"
        cost_tool = MagicMock()
        cost_tool.name = "get_cost_summary"
        mock_get_tools.return_value = [weather_tool, cost_tool]

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = AIMessage(content="明天晴")
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        asyncio.run(
            graph.ainvoke({"messages": [HumanMessage(content="今天天气")]})
        )

        bound_tools = mock_llm.bind_tools.call_args[0][0]
        tool_names = [t.name for t in bound_tools]
        assert "weather" in tool_names
        assert "get_cost_summary" not in tool_names
```

- [ ] **Step 2: 运行测试确认失败**（预筛尚未集成）

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_function_calling_e2e.py::TestFunctionCallingE2E::test_pre_filter_reduces_tools -v`
Expected: FAIL（assert "get_cost_summary" not in tool_names — 当前全量注入）

- [ ] **Step 3: 修改 graph.py — _llm_node 加预筛**

在 `backend/app/agent/graph.py` 第 29 行 import 区域添加：

```python
from app.agent.tool_selector import select_tools
```

将第 104-106 行从：

```python
    tools = get_langchain_tools()
    raw_llm = get_llm()
    llm = raw_llm.bind_tools(tools)
```

改为：

```python
    tools = get_langchain_tools()
    user_msg = _find_last_human_message(state["messages"])
    selected_names = select_tools(user_msg, [t.name for t in tools])
    tools = [t for t in tools if t.name in selected_names]
    raw_llm = get_llm()
    llm = raw_llm.bind_tools(tools)
```

- [ ] **Step 4: 运行全部 e2e 测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_function_calling_e2e.py -v`
Expected: 3 PASS（weather_query + chat_no_tool + pre_filter_reduces）

- [ ] **Step 5: Commit**

```bash
cd /Users/ljn/Documents/demo/explore/backend && git add app/agent/graph.py tests/test_function_calling_e2e.py && git commit -m "feat: _llm_node 集成 tool_selector 预筛"
```

---

### Task 4: 最终验证

**Files:** 无新文件

- [ ] **Step 1: ruff 检查**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && ruff check app/agent/tool_selector.py app/agent/graph.py tests/test_tool_selector.py`
Expected: 无 error

- [ ] **Step 2: 全量测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 3: 验证 tool_selector 独立模块被正确 import**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -c "from app.agent.tool_selector import select_tools; print(select_tools('今天天气', ['weather', 'get_cost_summary']))"`
Expected: `['weather']`
