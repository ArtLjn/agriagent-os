# ContextBundle 与工具调用边界 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 ContextBundle 预注入查询答案导致 LLM 不调 Skill 的根因，让查询型意图在 Rule Gate 阶段强制绑定对应 read Skill。

**Architecture:** 三层改造——(1) ContextBundle 白名单契约禁止查询答案字段进入 prompt；(2) Rule Gate 意图-工具强制绑定 + `tool_choice=required`，LLM 没得选；(3) Eval 集（B+D+E2 三类共 48 条）+ 污染对照断言根因消除。先跑 baseline 再改造，量化对比。

**Tech Stack:** Python 3.12 + FastAPI + LangChain Tools + pytest + pytest-mock。代码层级：`app/context/`（ContextBundle）+ `app/agent/tool_selector.py`（Rule Gate）+ `app/agent/runtime/`（LLM 调用）。

**Spec 来源:** `docs/farm-manager-design-spec/01_正式设计/13_Agent范式规范化设计.md` §5.9

---

## File Structure

### 创建

| 文件 | 职责 |
| --- | --- |
| `backend/app/context/allowlist.py` | ContextBundle 注入字段白名单常量 |
| `backend/tests/context/test_allowlist.py` | 白名单单测 |
| `backend/tests/context/test_builder_allowlist.py` | Builder 应用白名单集成测 |
| `backend/tests/agent/test_force_binding_rules.py` | 强制绑定配置单测 |
| `backend/tests/agent/test_select_tools_force_binding.py` | select_tools force binding 单测 |
| `backend/tests/agent/eval/__init__.py` | Eval 包标记 |
| `backend/tests/agent/eval/cases.py` | Eval 用例数据（48 条） |
| `backend/tests/agent/eval/conftest.py` | Eval 公共 fixture（mock Skill、污染 ContextBundle） |
| `backend/tests/agent/eval/test_baseline.py` | Baseline 跑批 |
| `backend/tests/agent/eval/test_pollution_differential.py` | 污染对照测试 |
| `backend/tests/agent/eval/test_multiturn_pollution.py` | E2 多轮污染测试 |

### 修改

| 文件 | 改动 |
| --- | --- |
| `backend/app/context/builder.py:75-117` | `build()` 末尾按白名单过滤 blocks |
| `backend/app/agent/tool_selection_rules.py` | 末尾新增 `QUERY_INTENT_FORCE_BINDING` 字典 |
| `backend/app/agent/tool_selector.py:182-299` | `select_tools` 返回 `ForceBindingResult`，绑定项不被裁剪 |
| `backend/app/agent/runtime/llm_support.py` | LLM 调用透传 `tool_choice="required"` |
| `backend/app/agent/runtime/nodes.py` | 埋 `tool_call_forced` / `final_reply_data_source` trace 事件 |

---

## Task 1: ContextBundle 白名单常量

**Files:**
- Create: `backend/app/context/allowlist.py`
- Test: `backend/tests/context/test_allowlist.py`

- [ ] **Step 1.1: 写失败测试**

```python
# backend/tests/context/test_allowlist.py
"""ContextBundle 白名单契约测试。"""
from app.context.allowlist import (
    ALLOWED_CONTEXT_KEYS,
    FORBIDDEN_CONTEXT_KEYS,
    is_allowed_key,
)


class TestAllowlistContract:
    def test_identity_keys_are_allowed(self):
        assert "farm_profile" in ALLOWED_CONTEXT_KEYS
        assert "user_settings" in ALLOWED_CONTEXT_KEYS

    def test_query_answer_keys_are_forbidden(self):
        assert "weather_snapshot" in FORBIDDEN_CONTEXT_KEYS
        assert "farm_status_snapshot" in FORBIDDEN_CONTEXT_KEYS
        assert "crop_cycle_details" in FORBIDDEN_CONTEXT_KEYS
        assert "recent_logs_summary" in FORBIDDEN_CONTEXT_KEYS
        assert "worker_list_snapshot" in FORBIDDEN_CONTEXT_KEYS
        assert "cost_summary_snapshot" in FORBIDDEN_CONTEXT_KEYS

    def test_is_allowed_key_returns_false_for_forbidden(self):
        assert is_allowed_key("weather_snapshot") is False

    def test_is_allowed_key_returns_true_for_whitelisted(self):
        assert is_allowed_key("farm_profile") is True

    def test_is_allowed_key_returns_false_for_unknown(self):
        assert is_allowed_key("totally_unknown_key") is False

    def test_no_overlap_between_allowed_and_forbidden(self):
        assert ALLOWED_CONTEXT_KEYS.isdisjoint(FORBIDDEN_CONTEXT_KEYS)
```

- [ ] **Step 1.2: 跑测试确认失败**

```bash
cd backend && poetry run pytest tests/context/test_allowlist.py -v
```
Expected: ImportError on `app.context.allowlist`.

- [ ] **Step 1.3: 实现白名单常量**

```python
# backend/app/context/allowlist.py
"""ContextBundle 注入字段白名单契约。

设计原则（见 13_Agent范式规范化设计.md §5.9.2）：
- 只承载身份、指针、状态、偏好
- 禁止承载可被询问的查询答案（天气、农场状态、茬口详情等）
"""

ALLOWED_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        # 身份/指针
        "farm_profile",
        "user_profile",
        "session_meta",
        "current_crop_cycle_pointer",  # 只放 ID，不放详情
        # 状态
        "pending_action_pointer",
        "pending_plan_pointer",
        "last_confirmed_at",
        # 偏好
        "user_settings",
        "assistant_role",
    }
)

FORBIDDEN_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "weather_snapshot",
        "weather_summary",
        "farm_status_snapshot",
        "crop_cycle_details",
        "crop_stage_details",
        "recent_logs_summary",
        "worker_list_snapshot",
        "cost_summary_snapshot",
        "debt_summary_snapshot",
        "labor_payables_snapshot",
    }
)


def is_allowed_key(key: str) -> bool:
    """判断 block key 是否允许注入 ContextBundle。"""
    return key in ALLOWED_CONTEXT_KEYS


__all__ = [
    "ALLOWED_CONTEXT_KEYS",
    "FORBIDDEN_CONTEXT_KEYS",
    "is_allowed_key",
]
```

- [ ] **Step 1.4: 跑测试确认通过**

```bash
cd backend && poetry run pytest tests/context/test_allowlist.py -v
```
Expected: 6 passed.

- [ ] **Step 1.5: Commit**

```bash
git add backend/app/context/allowlist.py backend/tests/context/test_allowlist.py
git commit -m "feat(context): add ContextBundle allowlist contract"
```

---

## Task 2: ContextBuilder 应用白名单过滤

**Files:**
- Modify: `backend/app/context/builder.py:75-117`（`build` 方法）
- Test: `backend/tests/context/test_builder_allowlist.py`

- [ ] **Step 2.1: 写失败测试**

```python
# backend/tests/context/test_builder_allowlist.py
"""ContextBuilder 白名单过滤集成测。"""
from app.context.builder import ContextBuilder
from app.context.models import ContextBlock
from app.context.allowlist import FORBIDDEN_CONTEXT_KEYS


class _FakeSelector:
    def __init__(self, blocks: list[ContextBlock]):
        self._blocks = blocks

    def select(self, **kwargs) -> list[ContextBlock]:
        return list(self._blocks)


class TestBuilderAllowlistFilter:
    def test_forbidden_blocks_are_dropped(self):
        forbidden_block = ContextBlock(
            key="weather_snapshot",
            source="test",
            purpose="should be filtered",
            content="天气：晴 30℃",
            priority=10,
        )
        allowed_block = ContextBlock(
            key="farm_profile",
            source="test",
            purpose="should remain",
            content="农场：测试农场",
            priority=10,
        )
        builder = ContextBuilder(
            selectors=[_FakeSelector([forbidden_block, allowed_block])],
            max_tokens=2000,
        )
        # build 需要 db，但 selectors 已注入 blocks，db=None 不调用 selector 之外的查询
        # 通过 mock 跳过 db 路径
        bundle = builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
        keys = {b.key for b in bundle.blocks}
        assert "weather_snapshot" not in keys
        assert "farm_profile" in keys

    def test_forbidden_blocks_recorded_in_dropped(self):
        forbidden_block = ContextBlock(
            key="farm_status_snapshot",
            source="test",
            purpose="should be dropped",
            content="农场状态快照",
            priority=10,
        )
        builder = ContextBuilder(
            selectors=[_FakeSelector([forbidden_block])],
            max_tokens=2000,
        )
        bundle = builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
        dropped_keys = {b.key for b in bundle.dropped_blocks}
        assert "farm_status_snapshot" in dropped_keys

    def test_all_forbidden_keys_covered(self):
        """契约测试：白名单的所有禁止字段都被过滤。"""
        for key in FORBIDDEN_CONTEXT_KEYS:
            block = ContextBlock(
                key=key,
                source="test",
                purpose="test",
                content=f"data for {key}",
                priority=10,
            )
            builder = ContextBuilder(
                selectors=[_FakeSelector([block])],
                max_tokens=2000,
            )
            bundle = builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
            assert key not in {b.key for b in bundle.blocks}, (
                f"forbidden key {key} was not filtered"
            )
```

- [ ] **Step 2.2: 跑测试确认失败**

```bash
cd backend && poetry run pytest tests/context/test_builder_allowlist.py -v
```
Expected: FAIL — forbidden blocks remain in `bundle.blocks`.

- [ ] **Step 2.3: 实现白名单过滤**

修改 `backend/app/context/builder.py`，在 `build` 方法 `self.budget.apply(blocks)` 之前插入过滤逻辑。

在文件顶部 import 区加：

```python
from app.context.allowlist import is_allowed_key
```

修改 `build` 方法（line 75-117），把 `blocks: list[ContextBlock] = []` 之后的循环改为：

```python
        blocks: list[ContextBlock] = []
        selector_errors: list[dict[str, str]] = []
        for selector in self.selectors:
            try:
                selected_blocks = selector.select(
                    db=db,
                    farm_id=farm_id,
                    user_id=user_id,
                    session_id=session_id,
                    **kwargs,
                )
                blocks.extend(
                    self._apply_dependency_metadata(
                        selected_blocks,
                        kwargs.get("context_dependency_map") or {},
                    )
                )
            except Exception as exc:
                selector_errors.append(
                    {
                        "selector": selector.__class__.__name__,
                        "error": str(exc)[:200],
                    }
                )

        # 白名单过滤：违禁字段不进入 prompt
        blocks = self._apply_allowlist_filter(blocks)

        bundle = self.budget.apply(blocks)
        bundle.metadata["selector_errors"] = selector_errors
        self._attach_dependency_summary(
            bundle,
            kwargs.get("context_dependency_map") or {},
        )
        self._record_trace(bundle, start)
        return bundle
```

在 `_apply_dependency_metadata` staticmethod 之后（约 line 224）新增：

```python
    @staticmethod
    def _apply_allowlist_filter(
        blocks: list[ContextBlock],
    ) -> list[ContextBlock]:
        """按白名单过滤 blocks，违禁字段不进入 prompt。

        设计意图见 13_Agent范式规范化设计.md §5.9.2。
        未在白名单中的 key 视为违禁，过滤掉。
        """
        filtered: list[ContextBlock] = []
        for block in blocks:
            if is_allowed_key(block.key):
                filtered.append(block)
        return filtered
```

**注意**：`budget.apply` 会把 `dropped_blocks` 填充预算超限的 blocks；白名单过滤掉的 blocks **不进入 budget**，因此不会出现在 `dropped_blocks` 中。如果需要 trace 区分（推荐），把过滤掉的 blocks 也记录到 bundle.metadata：

在 `bundle = self.budget.apply(blocks)` 之后加：

```python
        bundle.metadata["allowlist_filtered_keys"] = sorted(
            {b.key for b in blocks if not is_allowed_key(b.key)}
        )
```

不，上面 `blocks` 已被过滤。改用：在过滤前记录原始 keys，过滤后求差集：

```python
        original_keys = {b.key for b in blocks}
        blocks = self._apply_allowlist_filter(blocks)
        filtered_keys = original_keys - {b.key for b in blocks}

        bundle = self.budget.apply(blocks)
        bundle.metadata["selector_errors"] = selector_errors
        bundle.metadata["allowlist_filtered_keys"] = sorted(filtered_keys)
```

- [ ] **Step 2.4: 跑测试确认通过**

```bash
cd backend && poetry run pytest tests/context/test_builder_allowlist.py -v
```
Expected: 3 passed.

- [ ] **Step 2.5: 跑全量回归**

```bash
cd backend && poetry run pytest tests/test_context_engineering_e2e.py tests/context/ tests/test_prompt_composer.py -v
```
Expected: 现有用例不退化。如有 WeatherSelector 相关用例失败，把 selector 输出的 block.key 改为白名单内（如 `weather_pointer`），但内容改为指针型（"用户已配置天气城市"而非具体天气数据）。

- [ ] **Step 2.6: Commit**

```bash
git add backend/app/context/builder.py backend/tests/context/test_builder_allowlist.py
git commit -m "feat(context): filter ContextBundle blocks by allowlist"
```

---

## Task 3: 现有 Selector key 审计与重命名

**Files:**
- Modify: `backend/app/context/selectors.py`（或各 selector 文件）
- Test: 现有 `tests/test_context_engineering_e2e.py`

- [ ] **Step 3.1: 审计算当前各 selector 返回的 block key**

```bash
cd backend && grep -rn "key=\"" app/context/selectors.py 2>/dev/null || grep -rn "ContextBlock(" app/context/ --include="*.py"
```

记录每个 selector 输出的 block.key 列表。

- [ ] **Step 3.2: 把违禁 key 改名为指针型或删除**

逐个 selector 检查：

| Selector | 当前 key（示例） | 处理 |
| --- | --- | --- |
| WeatherSelector | `weather_snapshot` 或 `weather` | 改为 `weather_pointer`，内容仅含"用户已配置城市/坐标" |
| FarmSelector | `farm_profile` | 保留（白名单） |
| CycleSelector | `cycle_details` | 拆分：`current_crop_cycle_pointer`（指针）留在 bundle，详情删除 |
| WorkerSelector | `worker_list_snapshot` | 删除整条 selector 调用或改返回空（用 Skill 拿） |
| UnpaidLaborSummarySelector | `labor_payables_snapshot` | 删除（用 `get_labor_payables` Skill 拿） |
| LedgerSelector | `cost_summary_snapshot` | 删除（用 `get_cost_summary` Skill 拿） |

具体改动以 Step 3.1 grep 输出为准。

- [ ] **Step 3.3: 跑全量测试**

```bash
cd backend && poetry run pytest tests/ -v -k "context or builder or prompt_composer or prompt_engineering"
```
Expected: 全部通过。失败用例如非白名单相关，单独记录为后续任务，不阻塞本任务。

- [ ] **Step 3.4: Commit**

```bash
git add backend/app/context/
git commit -m "refactor(context): rename selectors to allowlist-compliant keys"
```

---

## Task 4: 强制绑定配置

**Files:**
- Modify: `backend/app/agent/tool_selection_rules.py`（末尾新增）
- Test: `backend/tests/agent/test_force_binding_rules.py`

- [ ] **Step 4.1: 写失败测试**

```python
# backend/tests/agent/test_force_binding_rules.py
"""查询型意图强制绑定规则单测。"""
from app.agent.tool_selection_rules import QUERY_INTENT_FORCE_BINDING


class TestForceBindingRules:
    def test_weather_intent_binds_weather(self):
        assert "weather" in QUERY_INTENT_FORCE_BINDING["天气"]

    def test_crop_cycle_intent_binds_get_crop_cycles(self):
        assert "get_crop_cycles" in QUERY_INTENT_FORCE_BINDING["我的茬口"]

    def test_workers_intent_binds_get_workers(self):
        assert "get_workers" in QUERY_INTENT_FORCE_BINDING["我的工人"]

    def test_labor_payables_intent_binds_get_labor_payables(self):
        assert "get_labor_payables" in QUERY_INTENT_FORCE_BINDING["未付人工"]

    def test_each_intent_maps_to_at_least_one_skill(self):
        for intent, skills in QUERY_INTENT_FORCE_BINDING.items():
            assert len(skills) >= 1, f"intent {intent} has no skill"

    def test_intent_keys_are_distinct_keywords(self):
        """每个意图 key 是用于匹配的关键词。"""
        for intent in QUERY_INTENT_FORCE_BINDING:
            assert isinstance(intent, str)
            assert len(intent) >= 2
```

- [ ] **Step 4.2: 跑测试确认失败**

```bash
cd backend && poetry run pytest tests/agent/test_force_binding_rules.py -v
```
Expected: ImportError on `QUERY_INTENT_FORCE_BINDING`.

- [ ] **Step 4.3: 实现强制绑定字典**

在 `backend/app/agent/tool_selection_rules.py` 末尾（`TOOL_CHAIN_MAP` 之后）新增：

```python
# 查询型意图 -> 强制绑定 Skill 映射。
# 设计意图（见 13_Agent范式规范化设计.md §5.9.3）：
# Rule Gate 识别到这些意图时，对应 Skill 必须进 selected_tools 并设 tool_choice=required。
# 不被 select_tools 的 difference_update 裁剪逻辑吃掉。
QUERY_INTENT_FORCE_BINDING: dict[str, set[str]] = {
    "天气": {"weather"},
    "下雨": {"weather"},
    "气温": {"weather"},
    "预报": {"weather"},
    "我的茬口": {"get_crop_cycles"},
    "当前种什么": {"get_crop_cycles"},
    "几号棚": {"get_crop_cycles"},
    "农场状态": {"get_farm_status"},
    "整体情况": {"get_farm_status"},
    "我的工人": {"get_workers"},
    "有哪些工人": {"get_workers"},
    "工人列表": {"get_workers"},
    "欠款": {"get_debt_summary"},
    "应付": {"get_labor_payables"},
    "未付人工": {"get_labor_payables"},
    "还欠多少人工": {"get_labor_payables"},
}
```

- [ ] **Step 4.4: 跑测试确认通过**

```bash
cd backend && poetry run pytest tests/agent/test_force_binding_rules.py -v
```
Expected: 6 passed.

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/agent/tool_selection_rules.py backend/tests/agent/test_force_binding_rules.py
git commit -m "feat(tool-rules): add QUERY_INTENT_FORCE_BINDING mapping"
```

---

## Task 5: select_tools 输出 force binding 信号

**Files:**
- Modify: `backend/app/agent/tool_selector.py:182-399`（`select_tools` 函数）
- Test: `backend/tests/agent/test_select_tools_force_binding.py`

- [ ] **Step 5.1: 写失败测试**

```python
# backend/tests/agent/test_select_tools_force_binding.py
"""select_tools 强制绑定信号单测。"""
from unittest.mock import MagicMock

from app.agent.tool_selector import select_tools


def _fake_tool(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


class TestSelectToolsForceBinding:
    def test_weather_input_forces_weather(self):
        all_tools = [_fake_tool("weather")]
        result = select_tools("今天天气怎么样", all_tools)
        assert "weather" in result.tools
        assert "weather" in result.force_binding

    def test_force_binding_survives_difference_update(self):
        """强制绑定不被 select_tools 内部裁剪吃掉。"""
        all_tools = [_fake_tool("get_crop_cycles"), _fake_tool("get_farm_status")]
        # "我的茬口" 命中 get_crop_cycles，正常情况下会被 difference_update 互斥逻辑影响
        # 但 force binding 应当穿透
        result = select_tools("我的茬口有哪些", all_tools)
        assert "get_crop_cycles" in result.tools
        assert "get_crop_cycles" in result.force_binding

    def test_no_force_binding_for_chitchat(self):
        all_tools = [_fake_tool("weather")]
        result = select_tools("你好", all_tools)
        assert "weather" not in result.force_binding
        assert "weather" not in result.tools

    def test_force_binding_tools_are_subset_of_tools(self):
        all_tools = [_fake_tool("weather")]
        result = select_tools("天气预报", all_tools)
        assert result.force_binding.issubset(set(result.tools))
```

- [ ] **Step 5.2: 跑测试确认失败**

```bash
cd backend && poetry run pytest tests/agent/test_select_tools_force_binding.py -v
```
Expected: FAIL — `select_tools` 当前返回 `list[str]`，没有 `.tools` / `.force_binding` 属性。

- [ ] **Step 5.3: 重构 select_tools 返回结构**

在 `backend/app/agent/tool_selector.py` 顶部 import 区加：

```python
from app.agent.tool_selection_rules import QUERY_INTENT_FORCE_BINDING
```

在 `LLMIntentClassifier` 类之前（约 line 52）新增 dataclass：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSelectionResult:
    """select_tools 返回结构。

    `tools` 是候选工具名集合（含强制绑定）。
    `force_binding` 是被 Rule Gate 强制绑定的工具子集，必须被 LLM 调用，
    应在 LLM 调用时设 `tool_choice=required`。
    """

    tools: list[str]
    force_binding: frozenset[str]

    def __iter__(self):
        return iter(self.tools)
```

修改 `select_tools` 函数签名（line 182），返回类型从 `list[str]` 改为 `ToolSelectionResult`：

```python
def select_tools(
    user_message: str,
    all_tools: list[BaseTool],
    top_k: int = 3,
    intent_classifier: LLMIntentClassifier | None = None,
) -> ToolSelectionResult:
    # 过滤掉禁用的 skill
    all_tools = [t for t in all_tools if _tool_enabled(t)]
    enabled_tool_names = {t.name for t in all_tools}
    candidates: set[str] = set()
    force_binding: set[str] = set()  # 新增

    # 强制绑定识别（在所有 difference_update 之前）
    for intent, skill_names in QUERY_INTENT_FORCE_BINDING.items():
        if intent in user_message:
            for skill_name in skill_names:
                if skill_name in enabled_tool_names:
                    candidates.add(skill_name)
                    force_binding.add(skill_name)

    # ... 原有的 WRITE_PATTERNS / QUERY_TRIGGERS 匹配逻辑保持不变 ...
    # （line 192-209 的 is_planting_advice / has_write_intent / has_query_intent 计算保留）
    # （WRITE_PATTERNS / QUERY_TRIGGERS 循环保留）

    # 所有 difference_update 之后，把 force_binding 加回 candidates（防止被裁剪）
    candidates |= force_binding

    # ... 原有 top_k 截断逻辑（如有）保留，但截断时不裁剪 force_binding ...

    return ToolSelectionResult(
        tools=sorted(candidates),
        force_binding=frozenset(force_binding),
    )
```

**关键约束**：
- `candidates |= force_binding` 必须在所有 `difference_update` 之后执行。
- 如有 top_k 截断逻辑（看 line 299 之后），截断时优先保留 force_binding。

**兼容性**：因为 `ToolSelectionResult.__iter__` 已实现，原来 `for t in select_tools(...)` 的代码仍可工作。但 `list[str]` 类型注解处需要逐一检查并改为 `.tools`。

- [ ] **Step 5.4: 修复调用方**

```bash
cd backend && grep -rn "select_tools(" app/ tests/ --include="*.py"
```

每个调用点：如果只用迭代或 list 语义，保持原样即可（`__iter__` 已实现）。如果用 `result[i]` 索引或 `len(result)`，需改为 `result.tools[i]` / `len(result.tools)`。

- [ ] **Step 5.5: 跑测试确认通过**

```bash
cd backend && poetry run pytest tests/agent/test_select_tools_force_binding.py tests/test_tool_selector.py -v
```
Expected: 新测试 4 passed；旧 test_tool_selector.py 全部通过（如有失败，按 Step 5.4 修调用方）。

- [ ] **Step 5.6: Commit**

```bash
git add backend/app/agent/tool_selector.py backend/tests/agent/test_select_tools_force_binding.py
git commit -m "feat(tool-selector): emit force_binding signal for query intents"
```

---

## Task 6: tool_choice=required 透传

**Files:**
- Modify: `backend/app/agent/runtime/llm_support.py`（LLM 调用处）
- Modify: `backend/app/agent/runtime/nodes.py`（节点协调处）
- Test: `backend/tests/agent/test_tool_choice_required.py`

- [ ] **Step 6.1: 定位 LLM 调用点**

```bash
cd backend && grep -rn "tool_choice\|chat.completions\|llm.invoke\|bind_tools" app/agent/runtime/ --include="*.py"
```

记录 LLM 绑定工具与调用的位置（通常在 `nodes.py` 的 LLM 节点或 `llm_support.py`）。

- [ ] **Step 6.2: 写失败测试**

```python
# backend/tests/agent/test_tool_choice_required.py
"""tool_choice=required 透传测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestToolChoiceRequired:
    async def test_force_binding_sets_tool_choice_required(self):
        """select_tools 返回 force_binding 时，LLM 调用必须传 tool_choice=required。"""
        from app.agent.tool_selector import ToolSelectionResult

        selection = ToolSelectionResult(
            tools=["weather"],
            force_binding=frozenset({"weather"}),
        )

        with patch("app.agent.runtime.llm_support._call_llm") as mock_call:
            mock_call.return_value = MagicMock()
            from app.agent.runtime.llm_support import _resolve_tool_choice

            choice = _resolve_tool_choice(selection)
            assert choice == "required"

    async def test_no_force_binding_keeps_auto(self):
        from app.agent.tool_selector import ToolSelectionResult

        selection = ToolSelectionResult(
            tools=[],
            force_binding=frozenset(),
        )
        from app.agent.runtime.llm_support import _resolve_tool_choice

        choice = _resolve_tool_choice(selection)
        assert choice == "auto"
```

- [ ] **Step 6.3: 跑测试确认失败**

```bash
cd backend && poetry run pytest tests/agent/test_tool_choice_required.py -v
```
Expected: ImportError on `_resolve_tool_choice`.

- [ ] **Step 6.4: 实现 _resolve_tool_choice**

在 `backend/app/agent/runtime/llm_support.py` 适当位置新增：

```python
from app.agent.tool_selector import ToolSelectionResult


def _resolve_tool_choice(selection: ToolSelectionResult) -> str:
    """根据 select_tools 结果决定 tool_choice。

    有强制绑定时返回 "required"，LLM 必须调用工具；
    否则返回 "auto" 让模型自主决定。
    """
    if selection.force_binding:
        return "required"
    return "auto"
```

- [ ] **Step 6.5: 在 LLM 调用处应用 tool_choice**

按 Step 6.1 grep 结果，找到 LLM 节点调用 `bind_tools` 或 `chat.completions.create` 的位置，把 tool_choice 透传进去：

```python
# 示例（实际位置和变量名按代码而定）：
selection = select_tools(user_message, all_tools)
tool_choice = _resolve_tool_choice(selection)

response = llm.invoke(
    messages,
    tools=selection.tools,
    tool_choice=tool_choice,  # 新增
)
```

如果是 OpenAI SDK：`client.chat.completions.create(..., tool_choice=tool_choice)`。
如果是 LangChain `bind_tools`：`llm.bind_tools(selection.tools).invoke(messages)`——LangChain 通常通过 `kwargs` 传 `tool_choice`，需查具体模型 bind 方法。

- [ ] **Step 6.6: 跑测试确认通过**

```bash
cd backend && poetry run pytest tests/agent/test_tool_choice_required.py -v
```
Expected: 2 passed.

- [ ] **Step 6.7: Commit**

```bash
git add backend/app/agent/runtime/llm_support.py backend/app/agent/runtime/nodes.py backend/tests/agent/test_tool_choice_required.py
git commit -m "feat(runtime): propagate tool_choice=required when force_binding present"
```

---

## Task 7: Trace 三个事件埋点

**Files:**
- Modify: `backend/app/context/builder.py:255-273`（`_record_trace`）
- Modify: `backend/app/agent/runtime/nodes.py`（LLM 节点和 final reply 处）
- Test: `backend/tests/agent/test_trace_events.py`

- [ ] **Step 7.1: 写失败测试**

```python
# backend/tests/agent/test_trace_events.py
"""trace 事件齐全性测试。"""
from unittest.mock import MagicMock


class TestTraceEvents:
    def test_context_bundle_built_event_emitted(self):
        """ContextBundle 构造完成后必须埋 context_bundle_built 事件。"""
        from app.context.builder import ContextBuilder
        from app.context.models import ContextBlock

        collector = MagicMock()
        builder = ContextBuilder(
            selectors=[],
            max_tokens=1000,
            trace_collector=collector,
        )
        builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
        # 断言 collector.record 被调用过，且 node_name 标识 context bundle
        assert collector.record.called
        call_kwargs = collector.record.call_args.kwargs
        assert call_kwargs.get("node_name") == "context_bundle"

    def test_force_binding_event_payload_includes_skill_names(self):
        """tool_call_forced 事件的 payload 必须含 skill 名。"""
        from app.agent.tool_selector import ToolSelectionResult

        selection = ToolSelectionResult(
            tools=["weather"],
            force_binding=frozenset({"weather"}),
        )
        payload = _build_force_binding_trace_payload(selection)
        assert payload["forced_skills"] == ["weather"]
        assert payload["tool_choice"] == "required"


def _build_force_binding_trace_payload(selection):
    from app.agent.tool_selector import ToolSelectionResult
    from app.agent.runtime.llm_support import _resolve_tool_choice

    return {
        "forced_skills": sorted(selection.force_binding),
        "tool_choice": _resolve_tool_choice(selection),
    }
```

- [ ] **Step 7.2: 跑测试确认失败**

```bash
cd backend && poetry run pytest tests/agent/test_trace_events.py -v
```
Expected: 部分通过（context_bundle 已有 trace），部分失败（force_binding payload 未定义）。

- [ ] **Step 7.3: 在 LLM 节点埋 tool_call_forced 事件**

定位 LLM 节点调用（Task 6 中已找到），在调用 LLM 前后加 trace：

```python
from app.infra.trace_collector import get_collector

# ... 在 LLM 调用之前 ...
selection = select_tools(user_message, all_tools)
tool_choice = _resolve_tool_choice(selection)

try:
    collector = get_collector()
    collector.record(
        node_type="tool_selection",
        node_name="tool_call_forced",
        input_data={"user_message": user_message[:200]},
        output_data={
            "forced_skills": sorted(selection.force_binding),
            "tool_choice": tool_choice,
            "selected_tools": selection.tools,
        },
        start_time=time.time(),
        duration_ms=0,
    )
except Exception:
    pass

response = llm.invoke(...)
```

- [ ] **Step 7.4: 在最终回复处埋 final_reply_data_source 事件**

定位 Final Response Builder（通常在 `nodes.py` 末尾或独立节点），埋点：

```python
# ... 在构造最终回复之后 ...
data_source = "context_bundle"
if tool_messages:  # 如果有 tool_calls 和 tool_results
    data_source = f"tool:{tool_messages[-1].name}"

try:
    collector = get_collector()
    collector.record(
        node_type="response",
        node_name="final_reply_data_source",
        input_data={"has_tool_results": bool(tool_messages)},
        output_data={"data_source": data_source},
        start_time=time.time(),
        duration_ms=0,
    )
except Exception:
    pass
```

- [ ] **Step 7.5: 跑测试确认通过**

```bash
cd backend && poetry run pytest tests/agent/test_trace_events.py -v
```
Expected: 全部通过。

- [ ] **Step 7.6: 跑回归**

```bash
cd backend && poetry run pytest tests/test_agent_runtime_architecture.py tests/test_context_engineering_e2e.py -v
```
Expected: 不退化。

- [ ] **Step 7.7: Commit**

```bash
git add backend/app/agent/runtime/nodes.py backend/tests/agent/test_trace_events.py
git commit -m "feat(trace): emit tool_call_forced and final_reply_data_source events"
```

---

## Task 8: Eval 框架 + Baseline 用例数据

**Files:**
- Create: `backend/tests/agent/eval/__init__.py`
- Create: `backend/tests/agent/eval/cases.py`
- Create: `backend/tests/agent/eval/conftest.py`
- Create: `backend/tests/agent/eval/test_baseline.py`

- [ ] **Step 8.1: 定义 EvalCase 数据结构 + ~12 条种子用例**

```python
# backend/tests/agent/eval/cases.py
"""Eval 用例数据。

设计意图（13_Agent范式规范化设计.md §5.9.5）：
- B 类：按意图/写操作/多意图/闲聊维度覆盖
- D 类：同意图不同表达方式
- E2 类：多轮污染场景
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str  # B_QUERY / B_WRITE / B_MULTI_INTENT / B_CHITCHAT / E2_MULTITURN
    user_message: str
    expected_skill: str | None  # 期望强制绑定的 Skill；闲聊负例为 None
    pollution_data: dict[str, str] | None = None  # 注入 ContextBundle 的污染数据
    skill_mock_return: dict | None = None  # Skill mock 返回值（与污染不同）
    previous_turns: list[str] = field(default_factory=list)  # E2 多轮历史


B_QUERY_CASES: list[EvalCase] = [
    # 5 意图 × 4 表达 = 20 条（D 类：同意图不同说法）
    EvalCase("q-weather-1", "B_QUERY", "天气如何", "weather"),
    EvalCase("q-weather-2", "B_QUERY", "今天下雨吗", "weather"),
    EvalCase("q-weather-3", "B_QUERY", "明天出门要带伞吗", "weather"),
    EvalCase("q-weather-4", "B_QUERY", "看下天气预报", "weather"),
    EvalCase("q-cycle-1", "B_QUERY", "我的茬口", "get_crop_cycles"),
    EvalCase("q-cycle-2", "B_QUERY", "当前种了什么", "get_crop_cycles"),
    EvalCase("q-cycle-3", "B_QUERY", "几号棚在种", "get_crop_cycles"),
    EvalCase("q-cycle-4", "B_QUERY", "种植批次列表", "get_crop_cycles"),
    EvalCase("q-workers-1", "B_QUERY", "我的工人", "get_workers"),
    EvalCase("q-workers-2", "B_QUERY", "有哪些工人", "get_workers"),
    EvalCase("q-workers-3", "B_QUERY", "工人列表", "get_workers"),
    EvalCase("q-workers-4", "B_QUERY", "现在谁在干", "get_workers"),
    EvalCase("q-payables-1", "B_QUERY", "未付人工", "get_labor_payables"),
    EvalCase("q-payables-2", "B_QUERY", "还欠多少人工钱", "get_labor_payables"),
    EvalCase("q-payables-3", "B_QUERY", "应付工资", "get_labor_payables"),
    EvalCase("q-payables-4", "B_QUERY", "人工欠款", "get_labor_payables"),
    # ... 继续 debt / farm_status 等
]

B_WRITE_CASES: list[EvalCase] = [
    EvalCase("w-cost-1", "B_WRITE", "记一笔化肥200元", "create_cost_record"),
    # ... 扩到 10 条
]

B_MULTI_INTENT_CASES: list[EvalCase] = [
    EvalCase("m-1", "B_MULTI_INTENT", "新来一个工人李丽工资100一天，今天去6号棚收水稻", None),
    # ... 扩到 5 条（expected_skill=None，验证走 pending plan）
]

B_CHITCHAT_CASES: list[EvalCase] = [
    EvalCase("c-1", "B_CHITCHAT", "你好", None),
    EvalCase("c-2", "B_CHITCHAT", "今天真热", None),
    # ... 扩到 8 条
]

E2_MULTITURN_CASES: list[EvalCase] = [
    EvalCase(
        "e2-1",
        "E2_MULTITURN",
        "天气如何",
        "weather",
        previous_turns=["你好", "最近忙啥", "我在管理农场"],
        pollution_data={"weather_snapshot": "晴 30℃"},
        skill_mock_return={"weather": "雨 25℃", "forecast": "未来 3 小时有雨"},
    ),
    # ... 扩到 5 条
]


def all_eval_cases() -> list[EvalCase]:
    return (
        B_QUERY_CASES + B_WRITE_CASES + B_MULTI_INTENT_CASES + B_CHITCHAT_CASES + E2_MULTITURN_CASES
    )
```

- [ ] **Step 8.2: 定义 conftest 公共 fixture**

```python
# backend/tests/agent/eval/conftest.py
"""Eval 公共 fixture：mock Skill 返回 + 构造污染 ContextBundle。"""
from unittest.mock import MagicMock

import pytest

from app.context.models import ContextBlock, ContextBundle


@pytest.fixture()
def mock_skill_registry():
    """mock 所有 Skill 的 execute 方法。"""
    registry = MagicMock()
    registry.execute = MagicMock(return_value={"status": "success", "data": {}})
    return registry


@pytest.fixture()
def pollution_bundle_factory():
    """构造含违禁字段的 ContextBundle（用于污染对照测试）。"""

    def _create(polition_data: dict[str, str]) -> ContextBundle:
        blocks = [
            ContextBlock(
                key=key,
                source="test_pollution",
                purpose="should_not_be_used",
                content=content,
                priority=10,
            )
            for key, content in polition_data.items()
        ]
        return ContextBundle(
            blocks=blocks,
            token_budget=2000,
            token_estimate=100,
        )

    return _create


@pytest.fixture()
def eval_metrics():
    """记录 eval 指标的可变 dict。"""
    return {
        "total": 0,
        "skill_triggered_correctly": 0,
        "skill_missed": 0,
        "chitchat_false_positive": 0,
        "data_source_matches_skill": 0,
    }
```

- [ ] **Step 8.3: 写 baseline 测试（先跑一遍，不改代码）**

```python
# backend/tests/agent/eval/test_baseline.py
"""Baseline：在改造前跑一遍 eval 集，记录当前指标。

执行：pytest tests/agent/eval/test_baseline.py -v -s
观察 stdout 输出的指标，记录到 spec 文档作为 baseline。
"""
import pytest

from tests.agent.eval.cases import all_eval_cases


@pytest.mark.parametrize("case", all_eval_cases(), ids=lambda c: c.case_id)
def test_eval_case_baseline(case, mock_skill_registry, pollution_bundle_factory, capsys):
    """跑每条 eval 用例，断言当前行为，记录指标。

    Baseline 阶段：测试可能大量失败（因为改造未实施），这正是 baseline 的价值。
    """
    from app.agent.tool_selector import select_tools

    # 构造 fake tools（按 case.expected_skill）
    all_tools = []
    if case.expected_skill:
        tool = MagicMock()
        tool.name = case.expected_skill
        all_tools.append(tool)

    result = select_tools(case.user_message, all_tools)

    # baseline 断言：force_binding 信号
    # 改造后这些断言应当通过；baseline 阶段记录失败比例
    if case.category == "B_QUERY":
        assert case.expected_skill in result.force_binding, (
            f"{case.case_id}: expected force_binding {case.expected_skill}, "
            f"got {result.force_binding}"
        )
```

- [ ] **Step 8.4: 跑 baseline**

```bash
cd backend && poetry run pytest tests/agent/eval/test_baseline.py -v --tb=no -q 2>&1 | tail -30
```

记录：通过率 X/Y，失败用例 ID 列表。**这就是 baseline**。

- [ ] **Step 8.5: Commit**

```bash
git add backend/tests/agent/eval/
git commit -m "test(eval): add eval framework with baseline cases"
```

---

## Task 9: 污染对照 + 多轮 eval

**Files:**
- Create: `backend/tests/agent/eval/test_pollution_differential.py`
- Create: `backend/tests/agent/eval/test_multiturn_pollution.py`

- [ ] **Step 9.1: 写污染对照测试**

```python
# backend/tests/agent/eval/test_pollution_differential.py
"""污染对照测试：验证回复数据来自 Skill 不来自 ContextBundle。

每条查询型用例跑两次：
- (a) ContextBundle 无污染
- (b) ContextBundle 塞入与 Skill mock 返回值不同的假数据
断言：两次回复一致，且都使用 Skill 返回值。
"""
from unittest.mock import MagicMock, patch

import pytest

from tests.agent.eval.cases import B_QUERY_CASES


@pytest.mark.parametrize("case", B_QUERY_CASES, ids=lambda c: c.case_id)
class TestPollutionDifferential:
    def test_clean_vs_polluted_replies_match(
        self, case, mock_skill_registry, pollution_bundle_factory
    ):
        if not case.skill_mock_return or not case.pollution_data:
            pytest.skip("only for cases with pollution data")

        # (a) 无污染
        with patch("app.agent.runtime.llm_support._get_runtime_context_bundle") as mock_ctx:
            mock_ctx.return_value = (MagicMock(blocks=[]), {})
            with patch.object(mock_skill_registry, "execute") as mock_exec:
                mock_exec.return_value = case.skill_mock_return
                # 跑 agent pipeline，捕获最终回复
                reply_clean = self._run_pipeline(case.user_message)

        # (b) 有污染
        polluted_bundle = pollution_bundle_factory(case.pollution_data)
        with patch("app.agent.runtime.llm_support._get_runtime_context_bundle") as mock_ctx:
            mock_ctx.return_value = (polluted_bundle, {})
            with patch.object(mock_skill_registry, "execute") as mock_exec:
                mock_exec.return_value = case.skill_mock_return
                reply_polluted = self._run_pipeline(case.user_message)

        # 断言两次一致
        assert reply_clean == reply_polluted, (
            f"{case.case_id}: polluted context changed reply, "
            f"clean={reply_clean!r}, polluted={reply_polluted!r}"
        )

        # 断言回复使用 Skill mock 值（不是污染值）
        for key, skill_value in case.skill_mock_return.items():
            if isinstance(skill_value, str):
                assert skill_value in reply_polluted, (
                    f"{case.case_id}: skill value {skill_value!r} not in reply"
                )

    @staticmethod
    def _run_pipeline(user_message: str) -> str:
        """跑一次 agent pipeline，返回最终回复文本。

        TODO: 按 graph.py 或 nodes.py 的入口调用。
        具体实现按现有 test_agent_service.py 模式。
        """
        from app.agent.graph import build_agent  # 按实际 import 调整

        # 简化版：直接调 graph，捕获 AIMessage.content
        # 实际实现需参考 tests/test_agent_service.py 的 fixture
        raise NotImplementedError("按现有 agent 集成测试模式补全")
```

**注意**：`_run_pipeline` 的具体实现要参考现有 `tests/test_agent_service.py` 或 `test_function_calling_e2e.py` 的模式。这是本任务最复杂的部分，可能需要拆为单独的 sub-task。

- [ ] **Step 9.2: 写多轮污染测试**

```python
# backend/tests/agent/eval/test_multiturn_pollution.py
"""E2 多轮污染测试：开场注入后第 N 轮查询仍必须调 Skill。"""
import pytest

from tests.agent.eval.cases import E2_MULTITURN_CASES


@pytest.mark.parametrize("case", E2_MULTITURN_CASES, ids=lambda c: c.case_id)
class TestMultiturnPollution:
    def test_nth_turn_still_calls_skill(self, case, pollution_bundle_factory):
        """第 N 轮（N>=2）询问仍触发 Skill 调用。"""
        from app.agent.tool_selector import select_tools

        # 模拟第 N 轮：用户消息 + 历史对话
        tool = MagicMock()
        tool.name = case.expected_skill

        # 第 N 轮的 select_tools 调用
        result = select_tools(case.user_message, [tool])

        # 断言仍然强制绑定
        assert case.expected_skill in result.force_binding, (
            f"{case.case_id}: skill {case.expected_skill} not force-bound on nth turn"
        )
```

- [ ] **Step 9.3: 实现 _run_pipeline（如果 Step 9.1 留了 TODO）**

参考 `tests/test_agent_service.py` 或 `tests/test_function_calling_e2e.py` 的 agent 入口调用方式，补全 `_run_pipeline`。

- [ ] **Step 9.4: 跑测试**

```bash
cd backend && poetry run pytest tests/agent/eval/ -v
```
Expected: 污染对照断言通过；多轮断言通过。

- [ ] **Step 9.5: Commit**

```bash
git add backend/tests/agent/eval/test_pollution_differential.py backend/tests/agent/eval/test_multiturn_pollution.py
git commit -m "test(eval): add pollution differential and multiturn eval"
```

---

## Task 10: 跑改造后 Eval 对比 Baseline + 文档同步

**Files:**
- Verify: 全套 eval 集
- Update: `docs/farm-manager-design-spec/01_正式设计/13_Agent范式规范化设计.md`（已更新 §5.9）
- Update: 如有 `docs/architecture/overview.md` 涉及 ContextBundle，同步说明

- [ ] **Step 10.1: 跑全套 eval，记录改造后指标**

```bash
cd backend && poetry run pytest tests/agent/eval/ tests/context/test_allowlist.py tests/context/test_builder_allowlist.py tests/agent/test_force_binding_rules.py tests/agent/test_select_tools_force_binding.py tests/agent/test_tool_choice_required.py -v --tb=no -q 2>&1 | tail -20
```

记录：通过率 X/Y。

- [ ] **Step 10.2: 对比 baseline，确认指标提升**

按 spec §5.9.6 量化指标对照：

| 指标 | Baseline | 改造后 | 目标 |
| --- | --- | --- | --- |
| ContextBundle 违禁字段注入率 | (Task 2 单测通过率) | 0 | 0 |
| 查询型意图触发对应 Skill 率 | (Task 8 baseline) | (Task 10.1) | ≥ 0.98 |
| Skill 调用与回复数据一致性 | (Task 9 污染对照) | 100% | 100% |
| 闲聊误触发 Skill 率 | (Task 8 baseline) | (Task 10.1) | ≤ 0.02 |

如有未达标项，进 Data Flywheel（见下一任务），不直接收工。

- [ ] **Step 10.3: 文档同步检查**

```bash
bash scripts/check-doc-freshness.sh 2>/dev/null || true
```

如脚本提示文档过期，按提示更新。

- [ ] **Step 10.4: 跑全量回归**

```bash
cd backend && poetry run pytest tests/ -v --tb=short -q 2>&1 | tail -30
```
Expected: 无新增失败。

- [ ] **Step 10.5: Commit**

```bash
git add -u
git commit -m "test: verify context bundle skill binding rollout metrics"
```

---

## Task 11（可选）: Data Flywheel 失败样本接入

**仅当 Task 10 指标未达标时执行。**

**Files:**
- Modify: 失败样本写入 `data_flywheel` 的回归用例路径

- [ ] **Step 11.1: 收集 eval 失败用例，写入修复包**

按 spec §5.8 + §5.9.8，失败类型分类：

- `context_injection`：白名单失效 → 进 Task 2 单测
- `tool_binding`：强制绑定未生效 → 进 Task 5 单测
- `data_source_mismatch`：回复用了污染值 → 进 Task 9 污染对照集

- [ ] **Step 11.2: 修复后重跑，直到达标**

回到对应 Task，补充规则/单测，再跑 Task 10。

---

## Task 12（可选）: 开场白独立通道

**仅当业务确认需要开场展示天气/状态时执行。**

**Files:**
- Create: `backend/app/agent/runtime/session_intro.py`
- Test: `backend/tests/agent/runtime/test_session_intro.py`

按 spec §5.9.4 时序图实现：session 创建事件触发，主动调 `weather + get_farm_status`，结果只渲染到开场回复，不写入 ContextBundle。

具体任务分解留待业务确认后展开。

---

## Self-Review Checklist

完成所有任务前，逐项确认：

- [ ] **Spec coverage**：§5.9.2 白名单 → Task 1-3；§5.9.3 强制绑定 → Task 4-6；§5.9.4 开场白 → Task 12（可选）；§5.9.5 验证 → Task 7-10；§5.9.6 指标 → Task 10；§5.9.7 实施顺序 → Task 顺序对齐；§5.9.8 失败类型 → Task 11。
- [ ] **Placeholder scan**：无 TBD/TODO（Task 9.3 的 NotImplementedError 是已知点，必须按 Step 9.3 补全）。
- [ ] **Type consistency**：`ToolSelectionResult`、`EvalCase`、`force_binding` 在所有任务中命名一致。
- [ ] **Commit hygiene**：每个 task 末尾有 commit step，提交信息符合 Conventional Commits。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-context-bundle-skill-binding.md`. Two execution options:

**1. Subagent-Driven (recommended)** - 每个 task 派一个 fresh subagent 执行，task 间 review，快速迭代。

**2. Inline Execution** - 在当前 session 顺序执行，按 checkpoint 批量审查。

哪种？
