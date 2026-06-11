# Skill Router Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 farm-manager 增加生产级 Skill Router，停止 `fallback_all` 全量工具暴露，降低 token 浪费，并补齐多意图 pending plan、工资默认规则和 debug 可观测性。

**Architecture:** 新增 `backend/app/agent/router/` 作为工具选择前置层，输出结构化 `RouterDecision`，由 runtime、ContextPolicy、preload 和 trace 消费。pending 写操作从单动作兼容层演进为 plan/step 队列，保留现有确认入口的兼容 API，并让 admin-web debug export 汇总 router、pending plan 和 skill I/O。

**Tech Stack:** FastAPI 后端、LangChain/LangGraph、SQLAlchemy/Alembic、pytest、React+TypeScript、Vitest、ESLint。

---

## 前置约束

- 全程简体中文。
- 不清理或回滚当前工作区已有脏改动。
- 手工编辑使用 `apply_patch`。
- 每个任务结束只暂存本任务文件，提交信息使用 Conventional Commits。
- 执行阶段先创建隔离分支或 worktree，避免混入用户已有 admin-web/mobile/weather 改动。

## 文件结构

### 新增后端 Router 包

- Create: `backend/app/agent/router/__init__.py`
  - 导出 `SkillRouter`、`RouterDecision`、`IntentFrame`、`ToolCandidate`、`DisclosureBudget`。
- Create: `backend/app/agent/router/models.py`
  - 定义 router 结构化模型和序列化方法。
- Create: `backend/app/agent/router/catalog.py`
  - 从 LangChain tools 与 registry 合成 Skill Catalog。
- Create: `backend/app/agent/router/registry.py`
  - 维护缺失的领域、意图、风险、实体、示例、上下文依赖、候选分组。
- Create: `backend/app/agent/router/classifier.py`
  - 规则分类常见读写意图、未知读写意图、多意图帧。
- Create: `backend/app/agent/router/policy.py`
  - 执行风险隔离、预算限制、safe default、未知写意图追问。
- Create: `backend/app/agent/router/service.py`
  - 编排 catalog、classifier、policy，返回 `RouterDecision`。

### 修改后端 Runtime 与 Context

- Modify: `backend/app/agent/tool_selector.py`
  - 保留 `select_tools()` 兼容入口，内部委托 `SkillRouter.route()`，彻底移除 `fallback_all` 返回全部工具。
- Modify: `backend/app/agent/state.py`
  - 增加 `router_decision` 状态字段。
- Modify: `backend/app/agent/runtime/nodes.py`
  - 在 LLM 绑定前生成/复用 `RouterDecision`；final answer 默认不重新绑定工具；记录 `skill_router` trace。
- Modify: `backend/app/agent/runtime/llm_support.py`
  - `_get_runtime_context_bundle()` 接受 `context_dependencies`。
- Modify: `backend/app/context/policy.py`
  - `ContextBuildRequest` 增加 `context_dependencies` 并优先使用 router 决策。
- Modify: `backend/app/context/preload.py`
  - 新增按 dependency 预热，保留按 tool 名预热兼容入口。

### 新增 Pending Plan

- Create: `backend/app/models/pending_plan.py`
  - 定义 `AgentPendingPlan`、`AgentPendingPlanStep`。
- Modify: `backend/app/models/__init__.py`
  - 导入 pending plan 模型，供 Alembic metadata 发现。
- Create: `backend/alembic/versions/<revision>_add_agent_pending_plans.py`
  - 创建 `agent_pending_plans`、`agent_pending_plan_steps`。
- Modify: `backend/app/infra/pending_actions.py`
  - 增加 plan dataclass、存取 API、旧 `PendingAction` 兼容视图。
- Modify: `backend/app/infra/pending_action_presenter.py`
  - 增加批量确认文案。
- Modify: `backend/app/agent/executor/pending_actions.py`
  - 支持确认 plan、逐步执行依赖步骤、失败停在当前步骤。

### 修改作业单工资规则

- Modify: `backend/app/agent/skills/create-operation-work-order/scripts/main.py`
  - `_build_labor_entries()` 从本句工资、工人默认工资、明确免工资三种路径确定单价；缺失时返回 clarification。

### 修改 admin-web debug export

- Modify: `admin-web/src/api/agent.ts`
  - 类型增加 `pending_plan` 或兼容字段。
- Modify: `admin-web/src/pages/Playground/sessionDebugExport.ts`
  - 导出 router diagnostics、pending plans、skill call I/O。
- Modify: `admin-web/src/pages/Playground/sessionDebugExport.test.ts`
  - 覆盖新增 debug JSON 字段。
- Modify: `admin-web/src/pages/Playground/index.tsx`
  - 传递 timeline/router/pending plan 到 export builder。

### 新增/修改测试

- Create: `backend/tests/agent/router/test_router_models.py`
- Create: `backend/tests/agent/router/test_skill_router.py`
- Create: `backend/tests/agent/router/test_router_policy.py`
- Create: `backend/tests/agent/test_runtime_router_binding.py`
- Create: `backend/tests/agent/test_pending_plan_executor.py`
- Create: `backend/tests/evaluation/test_skill_router_regression.py`
- Modify: `backend/tests/test_tool_selector.py`
- Modify: `backend/tests/context/test_policy.py`
- Modify: `backend/tests/skills/test_create_operation_work_order.py`
- Modify: `admin-web/src/pages/Playground/sessionDebugExport.test.ts`

---

## Task 1: Router 模型与 Catalog

**Files:**
- Create: `backend/app/agent/router/__init__.py`
- Create: `backend/app/agent/router/models.py`
- Create: `backend/app/agent/router/registry.py`
- Create: `backend/app/agent/router/catalog.py`
- Create: `backend/tests/agent/router/test_router_models.py`
- Create: `backend/tests/agent/router/test_skill_router.py`

- [ ] **Step 1: 写 Router 模型红灯测试**

Create `backend/tests/agent/router/test_router_models.py`:

```python
"""Router 模型测试。"""

import pytest

from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)

pytestmark = pytest.mark.no_db


def test_router_decision_serializes_for_trace() -> None:
    decision = RouterDecision(
        frames=[
            IntentFrame(
                domain="planting",
                intent="query_active_crops",
                risk="read",
                entities=["crop_cycle"],
                candidate_tools=["get_farm_status"],
                confidence=0.86,
            )
        ],
        selected_tools=["get_farm_status"],
        context_dependencies=["crop_cycles"],
        fallback="safe_read_default",
        reason="匹配活跃作物查询",
        rejected_tools=["create_crop_cycle"],
        schema_token_estimate=620,
        policy_violations=[],
    )

    payload = decision.to_trace_payload()

    assert payload["selected_tools"] == ["get_farm_status"]
    assert payload["frames"][0]["intent"] == "query_active_crops"
    assert payload["fallback"] == "safe_read_default"
    assert payload["schema_token_estimate"] == 620


def test_tool_candidate_keeps_routing_metadata() -> None:
    candidate = ToolCandidate(
        name="create_operation_work_order",
        domain="operation",
        intents=["create_work_order"],
        risk="write_confirm",
        entities=["worker", "planting_unit"],
        trigger_examples=["今天李树去6号棚收水稻"],
        anti_examples=["我的作业单有哪些"],
        context_dependencies=["workers", "planting_units", "active_cycles"],
        candidate_group="operation_write",
        schema_token_estimate=480,
    )

    assert candidate.name == "create_operation_work_order"
    assert candidate.risk == "write_confirm"
    assert candidate.context_dependencies == [
        "workers",
        "planting_units",
        "active_cycles",
    ]


def test_disclosure_budget_defaults_match_spec() -> None:
    budget = DisclosureBudget()

    assert budget.max_tools_default == 3
    assert budget.max_tools_complex == 5
    assert budget.max_write_tools == 1
    assert budget.max_schema_tokens == 1800
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_router_models.py -v
```

Expected: FAIL，错误包含 `ModuleNotFoundError: No module named 'app.agent.router'`。

- [ ] **Step 3: 实现 Router 模型**

Create `backend/app/agent/router/models.py`:

```python
"""Skill Router 数据模型。"""

from dataclasses import asdict, dataclass, field
from typing import Literal

RiskLevel = Literal["none", "read", "write_confirm", "write_high"]


@dataclass(frozen=True)
class DisclosureBudget:
    """工具 schema 暴露预算。"""

    max_tools_default: int = 3
    max_tools_complex: int = 5
    max_write_tools: int = 1
    max_schema_tokens: int = 1800


@dataclass(frozen=True)
class ToolCandidate:
    """Catalog 中的一条 Skill 候选。"""

    name: str
    domain: str
    intents: list[str]
    risk: RiskLevel
    entities: list[str] = field(default_factory=list)
    trigger_examples: list[str] = field(default_factory=list)
    anti_examples: list[str] = field(default_factory=list)
    context_dependencies: list[str] = field(default_factory=list)
    candidate_group: str = ""
    schema_token_estimate: int = 0
    enabled: bool = True


@dataclass(frozen=True)
class IntentFrame:
    """用户输入中的一个意图帧。"""

    domain: str
    intent: str
    risk: RiskLevel
    entities: list[str] = field(default_factory=list)
    candidate_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0
    params_hint: dict | None = None
    depends_on: list[str] = field(default_factory=list)
    requires_confirmation: bool = False


@dataclass(frozen=True)
class RouterDecision:
    """Router 输出给 runtime 的结构化决策。"""

    frames: list[IntentFrame] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    context_dependencies: list[str] = field(default_factory=list)
    fallback: str | None = None
    reason: str = ""
    rejected_tools: list[str] = field(default_factory=list)
    schema_token_estimate: int = 0
    policy_violations: list[str] = field(default_factory=list)
    clarification: str | None = None

    def to_trace_payload(self) -> dict:
        return asdict(self)
```

Create `backend/app/agent/router/__init__.py`:

```python
"""Skill Router 包。"""

from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)

__all__ = [
    "DisclosureBudget",
    "IntentFrame",
    "RouterDecision",
    "ToolCandidate",
]
```

- [ ] **Step 4: 运行模型测试确认通过**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_router_models.py -v
```

Expected: PASS。

- [ ] **Step 5: 写 Catalog 红灯测试**

Create `backend/tests/agent/router/test_skill_router.py` with initial catalog cases:

```python
"""Skill Catalog 测试。"""

from unittest.mock import MagicMock

import pytest

from app.agent.router.catalog import SkillCatalog

pytestmark = pytest.mark.no_db


def _tool(name: str, description: str = ""):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def test_catalog_enriches_work_order_metadata() -> None:
    catalog = SkillCatalog.from_tools(
        [
            _tool(
                "create_operation_work_order",
                "创建农事作业单，可同时记录多个工人",
            )
        ]
    )

    candidate = catalog.get("create_operation_work_order")

    assert candidate is not None
    assert candidate.domain == "operation"
    assert candidate.risk == "write_confirm"
    assert "create_work_order" in candidate.intents
    assert "workers" in candidate.context_dependencies
    assert "今天李树去6号棚收水稻" in candidate.trigger_examples


def test_catalog_marks_disabled_tools() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": False})()

    catalog = SkillCatalog.from_tools([tool])

    assert catalog.get("web_search").enabled is False
```

- [ ] **Step 6: 运行 Catalog 红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_skill_router.py -v
```

Expected: FAIL，错误包含 `No module named 'app.agent.router.catalog'`。

- [ ] **Step 7: 实现 registry 与 Catalog**

Create `backend/app/agent/router/registry.py`:

```python
"""Skill Router 静态注册表。"""

from app.infra.pending_actions import WRITE_SKILLS

CATALOG_REGISTRY: dict[str, dict] = {
    "get_farm_status": {
        "domain": "planting",
        "intents": ["query_farm_status", "query_active_crops"],
        "risk": "read",
        "entities": ["farm", "crop_cycle"],
        "trigger_examples": ["我家有哪些作物栽种", "农场现在是什么情况"],
        "anti_examples": ["创建茬口"],
        "context_dependencies": ["farm", "crop_cycles", "recent_operations"],
        "candidate_group": "planting_read",
    },
    "get_crop_cycle_info": {
        "domain": "planting",
        "intents": ["query_crop_cycle"],
        "risk": "read",
        "entities": ["crop_cycle"],
        "trigger_examples": ["查一下水稻茬口", "有哪些种植批次"],
        "anti_examples": ["创建水稻茬口"],
        "context_dependencies": ["crop_cycles"],
        "candidate_group": "planting_read",
    },
    "get_operation_work_orders": {
        "domain": "operation",
        "intents": ["query_work_orders"],
        "risk": "read",
        "entities": ["operation_work_order"],
        "trigger_examples": ["最近玉米授粉作业有哪些"],
        "anti_examples": ["今天李树去6号棚收水稻"],
        "context_dependencies": ["operation_work_orders", "workers"],
        "candidate_group": "operation_read",
    },
    "create_operation_work_order": {
        "domain": "operation",
        "intents": ["create_work_order"],
        "risk": "write_confirm",
        "entities": ["worker", "planting_unit", "crop_cycle", "labor"],
        "trigger_examples": ["今天李树去6号棚收水稻"],
        "anti_examples": ["我的作业单有哪些"],
        "context_dependencies": ["workers", "planting_units", "active_cycles"],
        "candidate_group": "operation_write",
    },
    "manage_workers": {
        "domain": "labor",
        "intents": ["create_worker", "update_worker", "deactivate_worker"],
        "risk": "write_confirm",
        "entities": ["worker", "labor"],
        "trigger_examples": ["新来一个工人李丽工资100一天", "删除工人李四"],
        "anti_examples": ["我的工人有哪些"],
        "context_dependencies": ["workers"],
        "candidate_group": "labor_write",
    },
    "get_workers": {
        "domain": "labor",
        "intents": ["query_workers"],
        "risk": "read",
        "entities": ["worker"],
        "trigger_examples": ["我的工人", "看看离职工人"],
        "anti_examples": ["新增工人"],
        "context_dependencies": ["workers"],
        "candidate_group": "labor_read",
    },
}


def default_risk_for_tool(name: str) -> str:
    return "write_confirm" if name in WRITE_SKILLS else "read"
```

Create `backend/app/agent/router/catalog.py`:

```python
"""Skill Catalog 构建。"""

import json

from langchain_core.tools import BaseTool

from app.agent.router.models import ToolCandidate
from app.agent.router.registry import CATALOG_REGISTRY, default_risk_for_tool
from app.agent.tool_selection_rules import DISABLED_SKILLS


def _schema_token_estimate(tool: BaseTool) -> int:
    payload = {
        "name": getattr(tool, "name", ""),
        "description": getattr(tool, "description", ""),
        "args_schema": str(getattr(tool, "args_schema", "")),
    }
    return max(80, len(json.dumps(payload, ensure_ascii=False)) // 2)


def _tool_enabled(tool: BaseTool) -> bool:
    metadata = getattr(tool, "skill_metadata", None)
    enabled = getattr(metadata, "enabled", None)
    if isinstance(enabled, bool):
        return enabled
    return tool.name not in DISABLED_SKILLS


class SkillCatalog:
    """按名称访问的 Skill Catalog。"""

    def __init__(self, candidates: list[ToolCandidate]) -> None:
        self._by_name = {candidate.name: candidate for candidate in candidates}

    @classmethod
    def from_tools(cls, tools: list[BaseTool]) -> "SkillCatalog":
        candidates = []
        for tool in tools:
            name = tool.name
            override = CATALOG_REGISTRY.get(name, {})
            candidates.append(
                ToolCandidate(
                    name=name,
                    domain=override.get("domain", "general"),
                    intents=list(override.get("intents", [name])),
                    risk=override.get("risk", default_risk_for_tool(name)),
                    entities=list(override.get("entities", [])),
                    trigger_examples=list(override.get("trigger_examples", [])),
                    anti_examples=list(override.get("anti_examples", [])),
                    context_dependencies=list(
                        override.get("context_dependencies", [])
                    ),
                    candidate_group=override.get("candidate_group", "general"),
                    schema_token_estimate=_schema_token_estimate(tool),
                    enabled=_tool_enabled(tool),
                )
            )
        return cls(candidates)

    def get(self, name: str) -> ToolCandidate | None:
        return self._by_name.get(name)

    def enabled(self) -> list[ToolCandidate]:
        return [candidate for candidate in self._by_name.values() if candidate.enabled]

    def names(self) -> list[str]:
        return list(self._by_name)
```

- [ ] **Step 8: 运行 Task 1 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_router_models.py tests/agent/router/test_skill_router.py -v
```

Expected: PASS。

- [ ] **Step 9: 提交 Task 1**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/router/__init__.py backend/app/agent/router/models.py backend/app/agent/router/registry.py backend/app/agent/router/catalog.py backend/tests/agent/router/test_router_models.py backend/tests/agent/router/test_skill_router.py
git commit -m "feat: add skill router catalog models"
```

---

## Task 2: Router Policy Stop-Loss

**Files:**
- Create: `backend/app/agent/router/classifier.py`
- Create: `backend/app/agent/router/policy.py`
- Create: `backend/app/agent/router/service.py`
- Modify: `backend/app/agent/router/__init__.py`
- Create: `backend/tests/agent/router/test_router_policy.py`
- Modify: `backend/tests/agent/router/test_skill_router.py`

- [ ] **Step 1: 写 stop-loss 红灯测试**

Append to `backend/tests/agent/router/test_skill_router.py`:

```python
from app.agent.router.service import SkillRouter


def test_session5_active_crop_query_selects_at_most_two_tools() -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("get_crop_cycle_info"),
        _tool("create_crop_cycle"),
        _tool("manage_workers"),
        _tool("create_operation_work_order"),
    ]

    decision = SkillRouter().route("我家有哪些作物栽种", tools)

    assert len(decision.selected_tools) <= 2
    assert set(decision.selected_tools) <= {"get_farm_status", "get_crop_cycle_info"}
    assert decision.fallback != "fallback_all"
    assert "create_operation_work_order" not in decision.selected_tools


def test_greeting_binds_no_tools() -> None:
    tools = [_tool("get_farm_status"), _tool("create_cost_record")]

    decision = SkillRouter().route("你好", tools)

    assert decision.selected_tools == []
    assert decision.fallback == "no_tools"


def test_unknown_farm_read_uses_safe_default() -> None:
    tools = [_tool("get_farm_status"), _tool("create_crop_cycle")]

    decision = SkillRouter().route("农场最近怎么样", tools)

    assert decision.selected_tools == ["get_farm_status"]
    assert decision.fallback == "safe_read_default"


def test_unknown_write_asks_clarification_without_write_tool() -> None:
    tools = [_tool("manage_workers"), _tool("create_operation_work_order")]

    decision = SkillRouter().route("帮我处理一下这个工人的事情", tools)

    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "请补充" in decision.clarification
```

- [ ] **Step 2: 写 Policy 预算红灯测试**

Create `backend/tests/agent/router/test_router_policy.py`:

```python
"""Router policy 测试。"""

import pytest

from app.agent.router.models import DisclosureBudget, IntentFrame, ToolCandidate
from app.agent.router.policy import RouterPolicy

pytestmark = pytest.mark.no_db


def _candidate(name: str, risk: str, tokens: int = 200) -> ToolCandidate:
    return ToolCandidate(
        name=name,
        domain="test",
        intents=[name],
        risk=risk,
        schema_token_estimate=tokens,
    )


def test_policy_allows_only_one_write_tool() -> None:
    decision = RouterPolicy().apply(
        message="新增工人并创建作业单",
        frames=[
            IntentFrame(
                domain="operation",
                intent="multi_write",
                risk="write_confirm",
                candidate_tools=["manage_workers", "create_operation_work_order"],
            )
        ],
        candidates=[
            _candidate("manage_workers", "write_confirm"),
            _candidate("create_operation_work_order", "write_confirm"),
        ],
    )

    assert len(decision.selected_tools) == 1
    assert decision.policy_violations == ["write_tool_budget_exceeded"]


def test_policy_trims_schema_token_budget() -> None:
    decision = RouterPolicy(
        DisclosureBudget(max_tools_default=3, max_schema_tokens=500)
    ).apply(
        message="看看天气成本和作业单",
        frames=[
            IntentFrame(
                domain="farm",
                intent="complex_read",
                risk="read",
                candidate_tools=["a", "b", "c"],
            )
        ],
        candidates=[
            _candidate("a", "read", tokens=300),
            _candidate("b", "read", tokens=300),
            _candidate("c", "read", tokens=300),
        ],
    )

    assert decision.selected_tools == ["a"]
    assert decision.schema_token_estimate == 300
    assert "schema_token_budget_exceeded" in decision.policy_violations
```

- [ ] **Step 3: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_skill_router.py tests/agent/router/test_router_policy.py -v
```

Expected: FAIL，错误包含 `No module named 'app.agent.router.service'` 或 `No module named 'app.agent.router.policy'`。

- [ ] **Step 4: 实现 classifier**

Create `backend/app/agent/router/classifier.py`:

```python
"""轻量意图分类器。"""

import re

from app.agent.router.models import IntentFrame

_QUERY_HINTS = ("哪些", "有哪些", "看看", "查询", "查一下", "最近", "怎么样")
_FARM_STATUS_HINTS = ("作物", "栽种", "农场", "茬口", "种植")
_WORK_ORDER_HINTS = ("作业", "采收", "授粉", "安排")
_WORKER_CREATE_RE = re.compile(r"(?:新来|招了|新增|创建).{0,8}工人")
_WORKER_WAGE_RE = re.compile(r"工资\s*\d+|日薪\s*\d+|\d+\s*(?:一天|每天)")
_AMBIGUOUS_WRITE_RE = re.compile(r"(处理|弄一下|搞一下).{0,10}(工人|作业|账)")


class RuleIntentClassifier:
    """覆盖农场核心高频意图。"""

    def classify(self, message: str) -> list[IntentFrame]:
        text = message.strip()
        if not text:
            return []
        frames: list[IntentFrame] = []

        if _WORKER_CREATE_RE.search(text) or _WORKER_WAGE_RE.search(text):
            frames.append(
                IntentFrame(
                    domain="labor",
                    intent="create_worker",
                    risk="write_confirm",
                    entities=["worker"],
                    candidate_tools=["manage_workers"],
                    confidence=0.86,
                    requires_confirmation=True,
                )
            )

        if any(hint in text for hint in _WORK_ORDER_HINTS) and not text.startswith(
            ("最近", "查询", "看看", "有哪些")
        ):
            frames.append(
                IntentFrame(
                    domain="operation",
                    intent="create_work_order",
                    risk="write_confirm",
                    entities=["operation_work_order", "worker"],
                    candidate_tools=["create_operation_work_order"],
                    confidence=0.82,
                    requires_confirmation=True,
                )
            )

        if any(hint in text for hint in _QUERY_HINTS) and any(
            hint in text for hint in _FARM_STATUS_HINTS
        ):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_active_crops",
                    risk="read",
                    entities=["crop_cycle"],
                    candidate_tools=["get_farm_status", "get_crop_cycle_info"],
                    confidence=0.88,
                )
            )

        if _AMBIGUOUS_WRITE_RE.search(text):
            frames.append(
                IntentFrame(
                    domain="general",
                    intent="ambiguous_write",
                    risk="write_confirm",
                    entities=[],
                    candidate_tools=[],
                    confidence=0.45,
                    requires_confirmation=True,
                )
            )

        return frames
```

- [ ] **Step 5: 实现 policy**

Create `backend/app/agent/router/policy.py`:

```python
"""Router policy guard。"""

from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)


class RouterPolicy:
    """在工具绑定前执行预算、风险和 fallback 控制。"""

    def __init__(self, budget: DisclosureBudget | None = None) -> None:
        self.budget = budget or DisclosureBudget()

    def apply(
        self,
        *,
        message: str,
        frames: list[IntentFrame],
        candidates: list[ToolCandidate],
    ) -> RouterDecision:
        if not frames:
            return RouterDecision(
                frames=[],
                selected_tools=[],
                fallback="no_tools",
                reason="未识别到需要工具的意图",
            )

        candidate_by_name = {candidate.name: candidate for candidate in candidates}
        ordered_names: list[str] = []
        for frame in frames:
            for name in frame.candidate_tools:
                if name in candidate_by_name and name not in ordered_names:
                    ordered_names.append(name)

        if self._has_ambiguous_write(frames):
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="clarify_write_intent",
                reason="写意图不明确，拒绝绑定写工具",
                clarification="请补充要新增、修改或删除的具体对象和关键参数。",
            )

        if not ordered_names and self._looks_like_farm_read(message, candidates):
            ordered_names = ["get_farm_status"]
            fallback = "safe_read_default"
        elif not ordered_names:
            return RouterDecision(
                frames=frames,
                selected_tools=[],
                fallback="no_tools",
                reason="没有可绑定候选工具",
            )
        else:
            fallback = None

        selected: list[str] = []
        rejected: list[str] = []
        policy_violations: list[str] = []
        write_count = 0
        token_count = 0
        max_tools = (
            self.budget.max_tools_complex
            if len(ordered_names) > self.budget.max_tools_default
            else self.budget.max_tools_default
        )

        for name in ordered_names:
            candidate = candidate_by_name.get(name)
            if candidate is None or not candidate.enabled:
                rejected.append(name)
                continue
            if candidate.risk.startswith("write"):
                write_count += 1
                if write_count > self.budget.max_write_tools:
                    rejected.append(name)
                    policy_violations.append("write_tool_budget_exceeded")
                    continue
            if len(selected) >= max_tools:
                rejected.append(name)
                policy_violations.append("tool_count_budget_exceeded")
                continue
            next_tokens = token_count + candidate.schema_token_estimate
            if next_tokens > self.budget.max_schema_tokens:
                rejected.append(name)
                policy_violations.append("schema_token_budget_exceeded")
                continue
            selected.append(name)
            token_count = next_tokens

        dependencies: list[str] = []
        for name in selected:
            candidate = candidate_by_name[name]
            for dependency in candidate.context_dependencies:
                if dependency not in dependencies:
                    dependencies.append(dependency)

        return RouterDecision(
            frames=frames,
            selected_tools=selected,
            context_dependencies=dependencies,
            fallback=fallback,
            reason="router policy applied",
            rejected_tools=rejected,
            schema_token_estimate=token_count,
            policy_violations=list(dict.fromkeys(policy_violations)),
        )

    @staticmethod
    def _has_ambiguous_write(frames: list[IntentFrame]) -> bool:
        return any(frame.intent == "ambiguous_write" for frame in frames)

    @staticmethod
    def _looks_like_farm_read(message: str, candidates: list[ToolCandidate]) -> bool:
        names = {candidate.name for candidate in candidates}
        return "get_farm_status" in names and any(
            hint in message for hint in ("农场", "作物", "种植", "情况", "怎么样")
        )
```

- [ ] **Step 6: 实现 SkillRouter service 并导出**

Create `backend/app/agent/router/service.py`:

```python
"""Skill Router 编排入口。"""

from langchain_core.tools import BaseTool

from app.agent.router.catalog import SkillCatalog
from app.agent.router.classifier import RuleIntentClassifier
from app.agent.router.models import RouterDecision
from app.agent.router.policy import RouterPolicy


class SkillRouter:
    """把用户消息路由为有限工具集合。"""

    def __init__(
        self,
        classifier: RuleIntentClassifier | None = None,
        policy: RouterPolicy | None = None,
    ) -> None:
        self.classifier = classifier or RuleIntentClassifier()
        self.policy = policy or RouterPolicy()

    def route(self, user_message: str, all_tools: list[BaseTool]) -> RouterDecision:
        catalog = SkillCatalog.from_tools(all_tools)
        frames = self.classifier.classify(user_message)
        candidates = catalog.enabled()
        return self.policy.apply(
            message=user_message,
            frames=frames,
            candidates=candidates,
        )
```

Modify `backend/app/agent/router/__init__.py`:

```python
"""Skill Router 包。"""

from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)
from app.agent.router.service import SkillRouter

__all__ = [
    "DisclosureBudget",
    "IntentFrame",
    "RouterDecision",
    "SkillRouter",
    "ToolCandidate",
]
```

- [ ] **Step 7: 运行 Router policy 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_skill_router.py tests/agent/router/test_router_policy.py -v
```

Expected: PASS。

- [ ] **Step 8: 提交 Task 2**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/router backend/tests/agent/router
git commit -m "feat: add skill router stop-loss policy"
```

---

## Task 3: `select_tools()` 兼容入口移除 `fallback_all`

**Files:**
- Modify: `backend/app/agent/tool_selector.py`
- Modify: `backend/tests/test_tool_selector.py`

- [ ] **Step 1: 修改旧 fallback 测试为新 stop-loss 语义**

Edit `backend/tests/test_tool_selector.py` `TestFallback` 部分：

```python
class TestFallback:
    def test_greeting_returns_no_tools(self):
        result = select_tools("你好", _make_tools())
        assert result == []

    def test_planting_advice_uses_safe_read_default(self):
        result = select_tools("西瓜怎么种", _make_tools())
        assert result == ["get_farm_status"]

    def test_how_to_plant_new_crop_uses_safe_read_default(self):
        result = select_tools("怎么种小麦", _make_tools())
        assert result == ["get_farm_status"]

    def test_planting_attention_uses_safe_read_default(self):
        result = select_tools("种小麦要注意什么", _make_tools())
        assert result == ["get_farm_status"]

    def test_no_fallback_all_for_unmatched_chat(self):
        tools = _make_tools()
        result = select_tools("随便聊聊", tools)
        assert result == []

    def test_metadata_enabled_false_excludes_safe_default(self):
        result = select_tools(
            "农场最近怎么样",
            _make_tools_with_enabled({"get_farm_status": False}),
        )
        assert "get_farm_status" not in result

    def test_metadata_enabled_true_overrides_legacy_disabled_set(self):
        result = select_tools(
            "搜索一下天气新闻",
            _make_tools_with_enabled({"web_search": True}),
        )
        assert len(result) <= 3

    def test_empty_message_returns_no_tools(self):
        result = select_tools("", _make_tools())
        assert result == []

    def test_empty_tools_returns_empty(self):
        result = select_tools("今天天气", [])
        assert result == []

    def test_top_k_limits_results(self):
        result = select_tools("看看天气和成本和余额和趋势", _make_tools(), top_k=2)
        assert len(result) <= 2

    def test_llm_intent_logs_returned_tools(self, caplog):
        classifier = MagicMock()
        classifier.classify.return_value = ["get_cost_summary"]

        with caplog.at_level("INFO", logger="app.agent.tool_selector"):
            result = select_tools(
                "帮我看看最近账怎么样",
                _make_tools(),
                intent_classifier=classifier,
            )

        assert result == ["get_cost_summary"]
        assert "tool_select | layer=llm_intent" in caplog.text
        assert "returned=['get_cost_summary']" in caplog.text

    def test_fallback_all_log_is_removed(self, caplog):
        with caplog.at_level("INFO", logger="app.agent.tool_selector"):
            result = select_tools("你好", _make_tools())

        assert result == []
        assert "fallback_all" not in caplog.text
        assert "tool_select | layer=router" in caplog.text
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_tool_selector.py -v
```

Expected: FAIL，旧 `fallback_all` 仍返回全部工具。

- [ ] **Step 3: 修改 `select_tools()` 委托 Router**

In `backend/app/agent/tool_selector.py`, add import:

```python
from app.agent.router.service import SkillRouter
```

Replace the final `if not candidates:` block after LLM classifier handling with:

```python
        decision = SkillRouter().route(user_message, all_tools)
        result = decision.selected_tools[:top_k]
        logger.info(
            (
                "tool_select | layer=router | input=%r | returned=%s | "
                "fallback=%s | reason=%s | total=%d"
            ),
            user_message[:80],
            result,
            decision.fallback,
            decision.reason,
            len(all_tools),
        )
        return result
```

Keep the existing rule-matched path unchanged so current deterministic tests continue to pass.

- [ ] **Step 4: 修正明确 advice 进入 safe default**

If `西瓜怎么种` still returns `[]`, add to `RuleIntentClassifier.classify()` before `return frames`:

```python
        if not frames and any(hint in text for hint in ("怎么种", "要注意什么")):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_planting_advice",
                    risk="read",
                    entities=["crop_cycle"],
                    candidate_tools=["get_farm_status"],
                    confidence=0.72,
                )
            )
```

- [ ] **Step 5: 运行 selector 与 router 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_tool_selector.py tests/agent/router -v
```

Expected: PASS。

- [ ] **Step 6: 提交 Task 3**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/tool_selector.py backend/app/agent/router/classifier.py backend/tests/test_tool_selector.py
git commit -m "fix: stop full tool fallback in selector"
```

---

## Task 4: Runtime 绑定 RouterDecision，final answer 不重绑全量工具

**Files:**
- Modify: `backend/app/agent/state.py`
- Modify: `backend/app/agent/runtime/nodes.py`
- Create: `backend/tests/agent/test_runtime_router_binding.py`

- [ ] **Step 1: 写 runtime 红灯测试**

Create `backend/tests/agent/test_runtime_router_binding.py`:

```python
"""Runtime router 绑定测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.router.models import RouterDecision
from app.agent.runtime.nodes import _llm_node

pytestmark = pytest.mark.no_db


class _FakeLLM:
    def __init__(self) -> None:
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    async def ainvoke(self, messages):
        response = MagicMock()
        response.content = "已整理结果"
        response.tool_calls = []
        response.response_metadata = {}
        response.id = "fake-response"
        return response


def _tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


@pytest.mark.asyncio
async def test_llm_node_uses_prepared_router_selected_tools() -> None:
    fake_llm = _FakeLLM()
    decision = RouterDecision(
        selected_tools=["get_farm_status"],
        context_dependencies=["crop_cycles"],
    )

    with (
        patch("app.agent.runtime.nodes.get_langchain_tools", return_value=[
            _tool("get_farm_status"),
            _tool("create_operation_work_order"),
        ]),
        patch("app.agent.runtime.nodes.get_llm", return_value=fake_llm),
        patch("app.agent.runtime.nodes._get_farm_context", new=AsyncMock(return_value={
            "display_name": "农友",
            "farm_location": "",
            "farm_coords": "",
            "active_crops": "",
        })),
        patch("app.agent.runtime.nodes._get_runtime_context_bundle", new=AsyncMock(return_value=(
            MagicMock(blocks=[], render_text=lambda: ""),
            {
                "display_name": "农友",
                "farm_location": "",
                "farm_coords": "",
                "active_crops": "",
            },
        ))),
        patch("app.agent.runtime.nodes._warm_tool_caches", new=AsyncMock()),
    ):
        await _llm_node(
            {
                "messages": [HumanMessage(content="我家有哪些作物栽种")],
                "farm_id": 1,
                "farm_uid": None,
                "intent": "query",
                "user_id": None,
                "session_id": "s1",
                "router_decision": decision,
            }
        )

    assert fake_llm.bound_tool_names == ["get_farm_status"]


@pytest.mark.asyncio
async def test_final_answer_with_tool_result_binds_no_tools_by_default() -> None:
    fake_llm = _FakeLLM()

    with (
        patch("app.agent.runtime.nodes.get_langchain_tools", return_value=[
            _tool("get_farm_status"),
            _tool("create_operation_work_order"),
        ]),
        patch("app.agent.runtime.nodes.get_llm", return_value=fake_llm),
        patch("app.agent.runtime.nodes._get_farm_context", new=AsyncMock(return_value={
            "display_name": "农友",
            "farm_location": "",
            "farm_coords": "",
            "active_crops": "",
        })),
        patch("app.agent.runtime.nodes._get_runtime_context_bundle", new=AsyncMock(return_value=(
            MagicMock(blocks=[], render_text=lambda: ""),
            {
                "display_name": "农友",
                "farm_location": "",
                "farm_coords": "",
                "active_crops": "",
            },
        ))),
        patch("app.agent.runtime.nodes._warm_tool_caches", new=AsyncMock()),
    ):
        await _llm_node(
            {
                "messages": [
                    HumanMessage(content="我家有哪些作物栽种"),
                    ToolMessage(content="当前有水稻", tool_call_id="call-1"),
                ],
                "farm_id": 1,
                "farm_uid": None,
                "intent": "query",
                "user_id": None,
                "session_id": "s1",
            }
        )

    assert fake_llm.bound_tool_names == []
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/test_runtime_router_binding.py -v
```

Expected: FAIL，第一个测试因为 state 不识别 `router_decision` 或 runtime 未消费它，第二个测试因为 final answer 仍绑定工具。

- [ ] **Step 3: 扩展 AgentState**

Modify `backend/app/agent/state.py`:

```python
from app.agent.router.models import RouterDecision
```

Add field:

```python
    router_decision: NotRequired[RouterDecision | None]
```

- [ ] **Step 4: 修改 `_llm_node()` 工具选择流程**

In `backend/app/agent/runtime/nodes.py`, import:

```python
from app.agent.router.models import RouterDecision
from app.agent.router.service import SkillRouter
```

Replace the current selected_names setup with:

```python
    prepared_router_decision = state.get("router_decision")
    if prepared_router_decision is not None and not isinstance(
        prepared_router_decision, RouterDecision
    ):
        raise TypeError("router_decision must be RouterDecision")

    if prepared_router_decision is not None:
        router_decision = prepared_router_decision
    elif has_tool_results:
        router_decision = RouterDecision(
            selected_tools=[],
            context_dependencies=[],
            fallback="final_answer_no_tools",
            reason="已有工具结果，final answer 默认不重新绑定工具",
        )
    else:
        router_decision = SkillRouter().route(user_msg, tools)

    selected_names = list(router_decision.selected_tools)
```

Keep `_is_operation_work_order_clarification()` append behavior after this block.

Remove the branch:

```python
    if prepared_selected_tool_names is not None:
        selected_tools = [t for t in tools if t.name in selected_names]
    elif has_tool_results:
        selected_names_set = expand_by_chain(set(selected_names))
        selected_tools = [t for t in tools if t.name in selected_names_set]
    else:
        selected_tools = [t for t in tools if t.name in selected_names]
```

Replace it with:

```python
    selected_tools = [t for t in tools if t.name in selected_names]
```

- [ ] **Step 5: 保留 explicit prepared_selected_tool_names 兼容**

After `selected_names = list(router_decision.selected_tools)`, add:

```python
    if prepared_selected_tool_names is not None:
        selected_names = list(prepared_selected_tool_names)
        router_decision = RouterDecision(
            selected_tools=selected_names,
            context_dependencies=list(router_decision.context_dependencies),
            fallback=router_decision.fallback,
            reason="使用预先准备的 selected_tool_names",
        )
```

- [ ] **Step 6: 运行 runtime 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/test_runtime_router_binding.py tests/test_mixed_tool_results.py tests/test_direct_tool_routing.py -v
```

Expected: PASS。

- [ ] **Step 7: 提交 Task 4**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/state.py backend/app/agent/runtime/nodes.py backend/tests/agent/test_runtime_router_binding.py
git commit -m "fix: bind runtime tools from router decision"
```

---

## Task 5: Context/preload 由 `RouterDecision.context_dependencies` 驱动

**Files:**
- Modify: `backend/app/context/policy.py`
- Modify: `backend/app/context/builder.py`
- Modify: `backend/app/context/preload.py`
- Modify: `backend/app/agent/runtime/llm_support.py`
- Modify: `backend/app/agent/runtime/nodes.py`
- Modify: `backend/tests/context/test_policy.py`
- Modify: `backend/tests/context/test_builder.py`

- [ ] **Step 1: 写 ContextPolicy 红灯测试**

Append to `backend/tests/context/test_policy.py`:

```python
def test_router_context_dependencies_drive_selectors() -> None:
    request = ContextBuildRequest(
        intent="query",
        selected_tool_names=[],
        context_dependencies=["workers", "planting_units"],
    )

    result = ContextPolicy().resolve(request)

    selector_names = {selector.__class__.__name__ for selector in result.selectors}
    assert "WorkerSelector" in selector_names
    assert "PlantingUnitSelector" in selector_names
    assert result.dependency_map["workers"] == ["workers"]
    assert result.dependency_map["planting_units"] == ["planting_units"]
```

- [ ] **Step 2: 写 preload dependency 红灯测试**

Create or append to `backend/tests/context/test_preload.py`:

```python
"""Context preload 测试。"""

import pytest

from app.context.preload import dependencies_to_preload_types

pytestmark = pytest.mark.no_db


def test_dependencies_to_preload_types_are_bounded() -> None:
    result = dependencies_to_preload_types(
        ["weather", "crop_cycles", "workers", "unknown"]
    )

    assert result == ["weather", "crop_cycle", "workers"]
```

- [ ] **Step 3: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_policy.py tests/context/test_preload.py -v
```

Expected: FAIL，`ContextBuildRequest` 没有 `context_dependencies`，`dependencies_to_preload_types` 未定义。

- [ ] **Step 4: 扩展 ContextBuildRequest 与依赖推导**

Modify `backend/app/context/policy.py`:

```python
    context_dependencies: list[str] = field(default_factory=list)
```

At the start of `_dependencies_from_request()` after `dependencies: set[str] = set()`:

```python
        dependencies.update(str(item) for item in request.context_dependencies)
```

Add selector alias:

```python
        "active_cycles": (CycleSelector, "cycle"),
        "farm": (FarmSelector, "farm"),
        "recent_operations": (OperationWorkOrderSelector, "operation_work_orders"),
```

- [ ] **Step 5: 实现 dependency preload helper**

Modify `backend/app/context/preload.py`:

```python
DEPENDENCY_PRELOAD_MAP: dict[str, list[str]] = {
    "weather": ["weather"],
    "crop_cycle": ["crop_cycle"],
    "crop_cycles": ["crop_cycle"],
    "active_cycles": ["crop_cycle"],
    "workers": ["workers"],
    "planting_units": ["planting_units"],
    "ledger": ["cost_summary"],
    "recent_operations": ["farm_logs"],
}


def dependencies_to_preload_types(dependencies: list[str]) -> list[str]:
    data_types: list[str] = []
    for dependency in dependencies:
        for data_type in DEPENDENCY_PRELOAD_MAP.get(dependency, []):
            if data_type not in data_types:
                data_types.append(data_type)
    return data_types
```

Update `__all__`:

```python
__all__ = [
    "DEPENDENCY_PRELOAD_MAP",
    "PRELOAD_MAP",
    "dependencies_to_preload_types",
    "warm_tool_caches",
]
```

- [ ] **Step 6: 让 runtime 传入 router dependencies**

Modify `_get_runtime_context_bundle()` signature in `backend/app/agent/runtime/llm_support.py` to accept:

```python
    context_dependencies: list[str] | None = None,
```

When constructing `ContextBuildRequest`, pass:

```python
        context_dependencies=list(context_dependencies or []),
```

Modify call in `backend/app/agent/runtime/nodes.py`:

```python
            context_dependencies=router_decision.context_dependencies,
```

- [ ] **Step 7: 运行 context 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_policy.py tests/context/test_builder.py tests/context/test_preload.py -v
```

Expected: PASS。

- [ ] **Step 8: 提交 Task 5**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/context/policy.py backend/app/context/builder.py backend/app/context/preload.py backend/app/agent/runtime/llm_support.py backend/app/agent/runtime/nodes.py backend/tests/context/test_policy.py backend/tests/context/test_builder.py backend/tests/context/test_preload.py
git commit -m "feat: drive context from router dependencies"
```

---

## Task 6: Router trace 与 admin debug 数据源

**Files:**
- Modify: `backend/app/agent/runtime/nodes.py`
- Create: `backend/tests/agent/router/test_router_trace.py`
- Modify: `admin-web/src/pages/Playground/sessionDebugExport.ts`
- Modify: `admin-web/src/pages/Playground/sessionDebugExport.test.ts`

- [ ] **Step 1: 写 router trace 红灯测试**

Create `backend/tests/agent/router/test_router_trace.py`:

```python
"""Router trace 测试。"""

import pytest

from app.agent.router.models import IntentFrame, RouterDecision

pytestmark = pytest.mark.no_db


def test_router_decision_trace_payload_contains_diagnostics() -> None:
    decision = RouterDecision(
        frames=[
            IntentFrame(
                domain="planting",
                intent="query_active_crops",
                risk="read",
                candidate_tools=["get_farm_status"],
            )
        ],
        selected_tools=["get_farm_status"],
        rejected_tools=["create_crop_cycle"],
        fallback="safe_read_default",
        schema_token_estimate=620,
        policy_violations=[],
    )

    payload = decision.to_trace_payload()

    assert payload["frames"][0]["risk"] == "read"
    assert payload["selected_tools"] == ["get_farm_status"]
    assert payload["rejected_tools"] == ["create_crop_cycle"]
    assert payload["policy_violations"] == []
```

- [ ] **Step 2: 在 `_llm_node()` 记录 `skill_router` trace**

After router decision is resolved in `backend/app/agent/runtime/nodes.py`, add:

```python
    get_collector().record(
        node_type="skill_router",
        node_name="skill_router",
        input_data={"message": user_msg[:500]},
        output_data=router_decision.to_trace_payload(),
        token_usage={
            "schema_token_estimate": router_decision.schema_token_estimate,
            "usage_source": "router_estimate",
        },
    )
```

This token usage must not be accumulated by `TraceCollector` because only `node_type == "llm_call"` is billed.

- [ ] **Step 3: 写 admin export 红灯测试**

Append to `admin-web/src/pages/Playground/sessionDebugExport.test.ts`:

```typescript
  it('导出 router diagnostics 和 pending plans', () => {
    const exported = buildSessionDebugExport({
      sessionId: 'session-router',
      simulateUserId: null,
      copiedAt: '2026-06-10T00:00:00.000Z',
      messages: [],
      timeline: {
        request_id: 'req-router',
        rounds: [
          {
            round_index: 1,
            nodes: [
              {
                node_type: 'skill_router',
                node_name: 'skill_router',
                duration_ms: 2,
                status: 'success',
                token_usage: { schema_token_estimate: 620 },
                start_time: null,
                error_message: null,
                input_data: { message: '我家有哪些作物栽种' },
                output_data: {
                  selected_tools: ['get_farm_status'],
                  fallback: 'safe_read_default',
                },
              },
              {
                node_type: 'pending_plan',
                node_name: 'agent_pending_plan',
                duration_ms: 1,
                status: 'success',
                token_usage: null,
                start_time: null,
                error_message: null,
                input_data: { raw_user_input: '新来工人并安排采收' },
                output_data: { plan_id: 'plan-1', steps: [] },
              },
            ],
          },
        ],
      },
    });

    expect(exported.router_diagnostics).toEqual([
      {
        round_index: 1,
        input_data: { message: '我家有哪些作物栽种' },
        output_data: {
          selected_tools: ['get_farm_status'],
          fallback: 'safe_read_default',
        },
      },
    ]);
    expect(exported.pending_plans).toEqual([
      {
        round_index: 1,
        input_data: { raw_user_input: '新来工人并安排采收' },
        output_data: { plan_id: 'plan-1', steps: [] },
      },
    ]);
  });
```

- [ ] **Step 4: 扩展 debug export 类型与 builder**

Modify `admin-web/src/pages/Playground/sessionDebugExport.ts`:

```typescript
export interface SessionDebugRouterDiagnostic {
  round_index: number;
  input_data: TracePayload;
  output_data: TracePayload;
}

export interface SessionDebugPendingPlan {
  round_index: number;
  input_data: TracePayload;
  output_data: TracePayload;
}
```

Add to `SessionDebugExport`:

```typescript
  router_diagnostics: SessionDebugRouterDiagnostic[];
  pending_plans: SessionDebugPendingPlan[];
```

Add in builder:

```typescript
  const routerDiagnostics = (timeline?.rounds ?? []).flatMap((round) => (
    round.nodes
      .filter((node) => node.node_type === 'skill_router')
      .map((node) => ({
        round_index: round.round_index,
        input_data: node.input_data,
        output_data: node.output_data,
      }))
  ));

  const pendingPlans = (timeline?.rounds ?? []).flatMap((round) => (
    round.nodes
      .filter((node) => node.node_type === 'pending_plan')
      .map((node) => ({
        round_index: round.round_index,
        input_data: node.input_data,
        output_data: node.output_data,
      }))
  ));
```

Return fields:

```typescript
    router_diagnostics: routerDiagnostics,
    pending_plans: pendingPlans,
```

- [ ] **Step 5: 运行 Task 6 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_router_trace.py -v

cd /Users/ljn/Documents/demo/explore/admin-web
npx vitest run src/pages/Playground/sessionDebugExport.test.ts
```

Expected: PASS。

- [ ] **Step 6: 提交 Task 6**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/runtime/nodes.py backend/tests/agent/router/test_router_trace.py admin-web/src/pages/Playground/sessionDebugExport.ts admin-web/src/pages/Playground/sessionDebugExport.test.ts
git commit -m "feat: export router diagnostics in debug data"
```

---

## Task 7: Pending Plan 持久模型与兼容存取 API

**Files:**
- Create: `backend/app/models/pending_plan.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<revision>_add_agent_pending_plans.py`
- Modify: `backend/app/infra/pending_actions.py`
- Create: `backend/tests/agent/test_pending_plan_store.py`

- [ ] **Step 1: 写 pending plan store 红灯测试**

Create `backend/tests/agent/test_pending_plan_store.py`:

```python
"""Pending plan 存取测试。"""

import pytest

from app.infra.pending_actions import (
    PendingPlanStep,
    get_pending_plan,
    remove_pending,
    store_pending_plan,
)

pytestmark = pytest.mark.no_db


def test_store_pending_plan_keeps_multiple_steps() -> None:
    remove_pending(1, session_id="s-plan")
    plan_id = store_pending_plan(
        farm_id=1,
        session_id="s-plan",
        raw_user_input="我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了",
        router_decision={
            "selected_tools": ["manage_workers"],
            "frames": [{"intent": "create_worker"}, {"intent": "create_work_order"}],
        },
        steps=[
            PendingPlanStep(
                step_id="step-1",
                tool_name="manage_workers",
                params={"name": "王大妈", "default_unit_price": 100},
                confirmation_state="pending",
            ),
            PendingPlanStep(
                step_id="step-2",
                tool_name="create_operation_work_order",
                params={
                    "workers": "王大妈",
                    "unit_names": "5号棚",
                    "operation_type": "采收",
                    "unit_price": 100,
                },
                depends_on=["step-1"],
                confirmation_state="pending",
            ),
        ],
    )

    plan = get_pending_plan(1, session_id="s-plan")

    assert plan is not None
    assert plan.plan_id == plan_id
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "manage_workers"
    assert plan.steps[1].depends_on == ["step-1"]

    remove_pending(1, session_id="s-plan")
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/test_pending_plan_store.py -v
```

Expected: FAIL，`PendingPlanStep`、`store_pending_plan` 未定义。

- [ ] **Step 3: 添加 SQLAlchemy 模型**

Create `backend/app/models/pending_plan.py`:

```python
"""Agent pending plan 持久模型。"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AgentPendingPlan(Base):
    __tablename__ = "agent_pending_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(64), unique=True, nullable=False, index=True)
    farm_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="pending")
    current_step_index = Column(Integer, nullable=False, default=0)
    raw_user_input = Column(Text, nullable=False, default="")
    router_decision = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    steps = relationship(
        "AgentPendingPlanStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="AgentPendingPlanStep.step_index",
    )


class AgentPendingPlanStep(Base):
    __tablename__ = "agent_pending_plan_steps"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        String(64),
        ForeignKey("agent_pending_plans.plan_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(String(64), nullable=False)
    step_index = Column(Integer, nullable=False)
    tool_name = Column(String(128), nullable=False)
    params = Column(JSON, nullable=False, default=dict)
    depends_on = Column(JSON, nullable=False, default=list)
    confirmation_state = Column(String(32), nullable=False, default="pending")
    execution_status = Column(String(32), nullable=False, default="pending")
    result_payload = Column(JSON, nullable=True)
    error_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    plan = relationship("AgentPendingPlan", back_populates="steps")
```

Modify `backend/app/models/__init__.py`:

```python
from app.models.pending_plan import AgentPendingPlan, AgentPendingPlanStep
```

- [ ] **Step 4: 添加 Alembic migration**

Create `backend/alembic/versions/<revision>_add_agent_pending_plans.py` using the next unique revision id:

```python
"""add agent pending plans

Revision ID: <revision>
Revises: e7b2c4d6f8a3
Create Date: 2026-06-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "<revision>"
down_revision = "e7b2c4d6f8a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_pending_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False),
        sa.Column("raw_user_input", sa.Text(), nullable=False),
        sa.Column("router_decision", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id"),
    )
    op.create_index("ix_agent_pending_plans_farm_id", "agent_pending_plans", ["farm_id"])
    op.create_index("ix_agent_pending_plans_plan_id", "agent_pending_plans", ["plan_id"])
    op.create_index("ix_agent_pending_plans_session_id", "agent_pending_plans", ["session_id"])

    op.create_table(
        "agent_pending_plan_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("confirmation_state", sa.String(length=32), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["agent_pending_plans.plan_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_pending_plan_steps_plan_id", "agent_pending_plan_steps", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_pending_plan_steps_plan_id", table_name="agent_pending_plan_steps")
    op.drop_table("agent_pending_plan_steps")
    op.drop_index("ix_agent_pending_plans_session_id", table_name="agent_pending_plans")
    op.drop_index("ix_agent_pending_plans_plan_id", table_name="agent_pending_plans")
    op.drop_index("ix_agent_pending_plans_farm_id", table_name="agent_pending_plans")
    op.drop_table("agent_pending_plans")
```

Replace `<revision>` with a concrete unique id, for example `a3f1c9d8e7b4`.

- [ ] **Step 5: 添加 in-memory 兼容 plan API**

Modify `backend/app/infra/pending_actions.py`:

```python
@dataclass
class PendingPlanStep:
    step_id: str
    tool_name: str
    params: dict
    depends_on: list[str] | None = None
    confirmation_state: str = "pending"
    execution_status: str = "pending"
    result_payload: dict | None = None
    error_payload: dict | None = None


@dataclass
class PendingPlan:
    plan_id: str
    farm_id: int
    session_id: str | None
    status: str
    current_step_index: int
    raw_user_input: str
    router_decision: dict
    steps: list[PendingPlanStep]
    created_at: float
```

Add storage:

```python
_pending_plans: dict[tuple[int, str | None], PendingPlan] = {}
```

Add functions:

```python
def store_pending_plan(
    *,
    farm_id: int,
    session_id: str | None,
    raw_user_input: str,
    router_decision: dict,
    steps: list[PendingPlanStep],
) -> str:
    plan_id = uuid.uuid4().hex
    normalized_steps = [
        PendingPlanStep(
            step_id=step.step_id,
            tool_name=step.tool_name,
            params=dict(step.params),
            depends_on=list(step.depends_on or []),
            confirmation_state=step.confirmation_state,
            execution_status=step.execution_status,
            result_payload=step.result_payload,
            error_payload=step.error_payload,
        )
        for step in steps
    ]
    _pending_plans[_pending_key(farm_id, session_id)] = PendingPlan(
        plan_id=plan_id,
        farm_id=farm_id,
        session_id=session_id,
        status="pending",
        current_step_index=0,
        raw_user_input=raw_user_input,
        router_decision=dict(router_decision),
        steps=normalized_steps,
        created_at=time.time(),
    )
    return plan_id


def get_pending_plan(
    farm_id: int,
    session_id: str | None = None,
) -> PendingPlan | None:
    plan = _pending_plans.get(_pending_key(farm_id, session_id))
    if plan is None:
        return None
    if time.time() - plan.created_at > _TIMEOUT_SECONDS:
        _pending_plans.pop(_pending_key(farm_id, session_id), None)
        return None
    return plan
```

Update `remove_pending()`:

```python
    if session_id is None:
        for key in [key for key in _pending_plans if key[0] == farm_id]:
            _pending_plans.pop(key, None)
    else:
        _pending_plans.pop(_pending_key(farm_id, session_id), None)
```

Update `__all__` to include `PendingPlan`, `PendingPlanStep`, `store_pending_plan`, `get_pending_plan`, `_pending_plans`。

- [ ] **Step 6: 运行 pending plan store 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/test_pending_plan_store.py tests/test_pending_actions.py -v
```

Expected: PASS。

- [ ] **Step 7: 提交 Task 7**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/models/pending_plan.py backend/app/models/__init__.py backend/alembic/versions/*_add_agent_pending_plans.py backend/app/infra/pending_actions.py backend/tests/agent/test_pending_plan_store.py
git commit -m "feat: add pending plan storage"
```

---

## Task 8: 多意图 pending plan 生成与确认执行

**Files:**
- Modify: `backend/app/agent/router/classifier.py`
- Modify: `backend/app/agent/router/service.py`
- Modify: `backend/app/infra/pending_action_presenter.py`
- Modify: `backend/app/agent/executor/pending_actions.py`
- Modify: `backend/app/infra/pending_actions.py`
- Create: `backend/tests/agent/test_pending_plan_executor.py`
- Modify: `backend/tests/agent/router/test_skill_router.py`

- [ ] **Step 1: 写 session4 多意图红灯测试**

Append to `backend/tests/agent/router/test_skill_router.py`:

```python
def test_session4_worker_create_plus_harvest_becomes_two_frames() -> None:
    tools = [
        _tool("manage_workers"),
        _tool("create_operation_work_order"),
        _tool("get_farm_status"),
    ]

    decision = SkillRouter().route(
        "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了",
        tools,
    )

    assert [frame.intent for frame in decision.frames] == [
        "create_worker",
        "create_work_order",
    ]
    assert decision.selected_tools == ["manage_workers"]
    assert decision.frames[1].depends_on == ["create_worker"]
    assert decision.frames[1].params_hint["unit_price"] == 100
```

- [ ] **Step 2: 写 pending plan 执行红灯测试**

Create `backend/tests/agent/test_pending_plan_executor.py`:

```python
"""Pending plan executor 测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.executor.pending_actions import handle_pending_action
from app.infra.pending_actions import (
    PendingPlanStep,
    get_pending_plan,
    remove_pending,
    store_pending_plan,
)

pytestmark = pytest.mark.no_db


@pytest.fixture(autouse=True)
def clean_pending_plan():
    remove_pending(1, session_id="s-plan")
    yield
    remove_pending(1, session_id="s-plan")


@pytest.mark.asyncio
async def test_confirm_pending_plan_executes_all_steps_in_order() -> None:
    store_pending_plan(
        farm_id=1,
        session_id="s-plan",
        raw_user_input="新来工人并安排采收",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[
            PendingPlanStep(
                step_id="create-worker",
                tool_name="manage_workers",
                params={"name": "王大妈", "default_unit_price": 100},
            ),
            PendingPlanStep(
                step_id="create-work-order",
                tool_name="create_operation_work_order",
                params={
                    "workers": "王大妈",
                    "operation_type": "采收",
                    "unit_names": "5号棚",
                    "unit_price": 100,
                },
                depends_on=["create-worker"],
            ),
        ],
    )

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new=AsyncMock(side_effect=["已创建工人", "已创建农事作业单"]),
    ) as execute:
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            session_id="s-plan",
        )

    assert decision.handled is True
    assert decision.reply == "已执行：\n1. 已创建工人\n2. 已创建农事作业单"
    assert get_pending_plan(1, session_id="s-plan") is None
    assert [call.kwargs["skill_name"] for call in execute.await_args_list] == [
        "manage_workers",
        "create_operation_work_order",
    ]
```

- [ ] **Step 3: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_skill_router.py tests/agent/test_pending_plan_executor.py -v
```

Expected: FAIL，多意图 params_hint/depends_on 未实现，executor 不处理 plan。

- [ ] **Step 4: 扩展 classifier 抽取多意图 hint**

In `backend/app/agent/router/classifier.py`, add helper:

```python
_WAGE_RE = re.compile(r"(?:工资|日薪)?\s*(?P<amount>\d+(?:\.\d+)?)\s*(?:元|块)?\s*(?:一天|每天|日薪)?")
_UNIT_RE = re.compile(r"(?P<unit>\d+号棚)")
_WORKER_NAME_RE = re.compile(r"工人(?P<name>[\u4e00-\u9fff]{2,4})")


def _extract_wage(text: str) -> int | None:
    match = _WAGE_RE.search(text)
    return int(float(match.group("amount"))) if match else None


def _extract_unit(text: str) -> str | None:
    match = _UNIT_RE.search(text)
    return match.group("unit") if match else None


def _extract_worker_name(text: str) -> str | None:
    match = _WORKER_NAME_RE.search(text)
    return match.group("name") if match else None
```

When adding create worker frame:

```python
            worker_name = _extract_worker_name(text)
            wage = _extract_wage(text)
            params_hint = {}
            if worker_name:
                params_hint["name"] = worker_name
            if wage is not None:
                params_hint["default_unit_price"] = wage
                params_hint["default_pay_type"] = "daily"
```

Use the `params_hint=params_hint` argument.

When adding create work order frame:

```python
            worker_name = _extract_worker_name(text)
            wage = _extract_wage(text)
            unit_name = _extract_unit(text)
            params_hint = {"operation_type": "采收"} if "收" in text else {}
            if worker_name:
                params_hint["workers"] = worker_name
            if wage is not None:
                params_hint["unit_price"] = wage
            if unit_name:
                params_hint["unit_names"] = unit_name
```

If a worker frame already exists, set:

```python
                    depends_on=["create_worker"] if frames else [],
```

- [ ] **Step 5: 实现 batch confirmation presenter**

Modify `backend/app/infra/pending_action_presenter.py`:

```python
def build_plan_confirm_message(steps) -> str:
    lines = [f"请确认将执行 {len(steps)} 步：", ""]
    for index, step in enumerate(steps, start=1):
        if step.tool_name == "manage_workers":
            name = step.params.get("name") or step.params.get("worker_name") or "工人"
            wage = step.params.get("default_unit_price")
            lines.append(f"{index}. 创建工人：{name}，日薪{wage}元")
        elif step.tool_name == "create_operation_work_order":
            lines.append(
                f"{index}. 创建采收作业单：{step.params.get('unit_names', '未指定地块')}，"
                f"工人{step.params.get('workers', '未指定')}，应付{step.params.get('unit_price', '未指定')}元"
            )
        else:
            lines.append(f"{index}. 执行 {step.tool_name}")
    lines.extend(["", "确认后会按顺序执行以上操作。确认吗？"])
    return "\n".join(lines)
```

Export it in `__all__` if the file has an export list.

- [ ] **Step 6: executor 优先处理 pending plan**

In `backend/app/agent/executor/pending_actions.py`, import:

```python
from app.infra.pending_actions import get_pending_plan
from app.infra.pending_action_presenter import build_plan_confirm_message
```

Add helper:

```python
async def _confirm_pending_plan(
    farm_id: int,
    plan,
    farm_uid: str | None = None,
    session_id: str | None = None,
) -> PendingActionDecision:
    results = []
    for index, step in enumerate(plan.steps, start=1):
        result = await _execute_write_skill(
            farm_id=farm_id,
            skill_name=step.tool_name,
            params=step.params,
            farm_uid=farm_uid,
        )
        results.append(f"{index}. {result}")
        cache_groups = _get_metadata_cache_groups(
            step.tool_name,
            farm_id=farm_id,
            farm_uid=farm_uid,
        )
        _clear_cache_groups(step.tool_name, cache_groups)
    remove_pending(farm_id, session_id=session_id)
    return PendingActionDecision.confirmed("已执行：\n" + "\n".join(results))
```

At the start of `handle_pending_action()`:

```python
    pending_plan = get_pending_plan(farm_id, session_id=session_id)
    if pending_plan is not None:
        intent = detect_user_intent(message)
        if intent == "confirm":
            return await _confirm_pending_plan(
                farm_id,
                pending_plan,
                farm_uid=farm_uid,
                session_id=session_id,
            )
        if intent == "cancel":
            remove_pending(farm_id, session_id=session_id)
            return PendingActionDecision.canceled()
        return PendingActionDecision.modified(
            reply="当前有一组待确认操作，还没有执行。\n"
            + build_plan_confirm_message(pending_plan.steps),
            handled=True,
        )
```

- [ ] **Step 7: 运行 pending plan 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/agent/router/test_skill_router.py tests/agent/test_pending_plan_executor.py tests/agent/test_pending_action_executor.py -v
```

Expected: PASS。

- [ ] **Step 8: 提交 Task 8**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/router/classifier.py backend/app/agent/router/service.py backend/app/infra/pending_action_presenter.py backend/app/agent/executor/pending_actions.py backend/app/infra/pending_actions.py backend/tests/agent/test_pending_plan_executor.py backend/tests/agent/router/test_skill_router.py
git commit -m "feat: support multi-step pending plans"
```

---

## Task 9: 作业单工资默认规则

**Files:**
- Modify: `backend/app/agent/skills/create-operation-work-order/scripts/main.py`
- Modify: `backend/tests/skills/test_create_operation_work_order.py`

- [ ] **Step 1: 写工资规则红灯测试**

Append to `backend/tests/skills/test_create_operation_work_order.py`:

```python
@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "create_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_create_work_order_uses_worker_default_wage_when_unit_price_missing(
    mock_to_response, mock_create, mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=Decimal("100"),
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker

    response = MagicMock(
        operation_type="采收",
        operation_date=date(2026, 6, 8),
        unit_names=[],
        labor_entries=[MagicMock()],
        total_payable_amount=Decimal("100"),
        total_paid_amount=Decimal("0"),
        total_unpaid_amount=Decimal("100"),
    )
    mock_create.return_value = MagicMock()
    mock_to_response.return_value = response

    result = await CreateOperationWorkOrderSkill().execute(
        {
            "operation_type": "采收",
            "worker_name": "李丽",
        },
        ctx,
    )

    assert result.status.value == "success"
    work_order_create = mock_create.call_args.args[1]
    assert work_order_create.labor_entries[0].unit_price == Decimal("100")
    assert work_order_create.labor_entries[0].pay_type == "daily"


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
async def test_create_work_order_asks_wage_when_missing_everywhere(mock_session, ctx):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=None,
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker

    result = await CreateOperationWorkOrderSkill().execute(
        {
            "operation_type": "采收",
            "worker_name": "李丽",
        },
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "工资" in result.reply
    assert "不会默认记为0" in result.reply


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "create_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_create_work_order_allows_explicit_no_wage(
    mock_to_response, mock_create, mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=None,
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker
    mock_create.return_value = MagicMock()
    mock_to_response.return_value = MagicMock(
        operation_type="采收",
        operation_date=date(2026, 6, 8),
        unit_names=[],
        labor_entries=[MagicMock()],
        total_payable_amount=Decimal("0"),
        total_paid_amount=Decimal("0"),
        total_unpaid_amount=Decimal("0"),
    )

    result = await CreateOperationWorkOrderSkill().execute(
        {
            "operation_type": "采收",
            "worker_name": "李丽",
            "no_wage": True,
        },
        ctx,
    )

    assert result.status.value == "success"
    work_order_create = mock_create.call_args.args[1]
    assert work_order_create.labor_entries[0].unit_price == Decimal("0")
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/skills/test_create_operation_work_order.py -v
```

Expected: FAIL，缺失单价时仍默认 `Decimal("0")`。

- [ ] **Step 3: 修改 `_build_labor_entries()` 返回 clarification**

In `backend/app/agent/skills/create-operation-work-order/scripts/main.py`, before creating work order:

```python
            labor_entries, labor_error = _build_labor_entries(
                db,
                farm_id,
                worker_names,
                params,
            )
            if labor_error:
                return SkillResult(
                    status=ResultStatus.NEED_CLARIFY,
                    reply=labor_error,
                )
```

Change function signature:

```python
def _build_labor_entries(
    db,
    farm_id: int,
    worker_names: list[str],
    params: dict,
) -> tuple[list[LaborEntryCreate], str | None]:
```

Implement body:

```python
    if not worker_names:
        return [], None
    explicit_unit_price = _to_decimal(params.get("unit_price"))
    explicit_no_wage = bool(params.get("no_wage")) or str(
        params.get("wage_policy") or ""
    ) in {"none", "no_wage", "free"}
    pay_type_param = str(params.get("pay_type") or "").strip()
    paid_worker = str(params.get("paid_worker") or "").strip()
    paid_amount = _to_decimal(params.get("paid_amount")) or Decimal("0")
    entries = []
    for name in worker_names:
        worker = _find_or_create_worker(
            db,
            farm_id,
            name,
            explicit_unit_price or Decimal("0"),
        )
        unit_price = _resolve_labor_unit_price(
            worker=worker,
            explicit_unit_price=explicit_unit_price,
            explicit_no_wage=explicit_no_wage,
        )
        if unit_price is None:
            return [], (
                f"请补充{name}本次作业的工资。"
                "系统不会默认记为0；如果本次不计工资，请明确说明不计工资。"
            )
        pay_type = pay_type_param or getattr(worker, "default_pay_type", None) or "daily"
        entry_paid = (
            paid_amount if paid_worker and paid_worker == name else Decimal("0")
        )
        entries.append(
            LaborEntryCreate(
                worker_id=worker.id,
                pay_type=pay_type,
                quantity=Decimal("1"),
                unit_price=unit_price,
                paid_amount=entry_paid,
            )
        )
    return entries, None
```

Add helper:

```python
def _resolve_labor_unit_price(
    *,
    worker: Worker,
    explicit_unit_price: Decimal | None,
    explicit_no_wage: bool,
) -> Decimal | None:
    if explicit_unit_price is not None:
        return explicit_unit_price
    default_unit_price = _to_decimal(getattr(worker, "default_unit_price", None))
    if default_unit_price is not None:
        return default_unit_price
    if explicit_no_wage:
        return Decimal("0")
    return None
```

- [ ] **Step 4: 运行工资测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/skills/test_create_operation_work_order.py tests/skills/test_planting_operation_skills.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交 Task 9**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/skills/create-operation-work-order/scripts/main.py backend/tests/skills/test_create_operation_work_order.py
git commit -m "fix: require explicit labor wage for work orders"
```

---

## Task 10: 回归评估与最终验证

**Files:**
- Create: `backend/tests/evaluation/test_skill_router_regression.py`
- Modify: `backend/tests/chat-session/session4.json` only if fixture normalization is required and the file is already intended as test data.
- Modify: `backend/tests/chat-session/session5.json` only if fixture normalization is required and the file is already intended as test data.

- [ ] **Step 1: 写 session 回归测试**

Create `backend/tests/evaluation/test_skill_router_regression.py`:

```python
"""Skill Router 回归测试。"""

import pytest

from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name


TOOLS = [
    _Tool("get_farm_status"),
    _Tool("get_crop_cycle_info"),
    _Tool("create_crop_cycle"),
    _Tool("manage_workers"),
    _Tool("create_operation_work_order"),
    _Tool("get_operation_work_orders"),
    _Tool("get_workers"),
    _Tool("settle_labor_payment"),
    _Tool("delete_crop_cycle"),
]


def test_session5_crop_query_is_bounded() -> None:
    decision = SkillRouter().route("我家有哪些作物栽种", TOOLS)

    assert len(decision.selected_tools) <= 2
    assert set(decision.selected_tools) <= {"get_farm_status", "get_crop_cycle_info"}
    assert decision.schema_token_estimate <= 1800


def test_session4_worker_and_harvest_has_step_recall() -> None:
    decision = SkillRouter().route(
        "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了",
        TOOLS,
    )

    intents = [frame.intent for frame in decision.frames]
    assert "create_worker" in intents
    assert "create_work_order" in intents
    assert len(decision.selected_tools) == 1


def test_read_intent_does_not_expose_write_tools() -> None:
    decision = SkillRouter().route("我的工人有哪些", TOOLS)

    assert all(
        name not in decision.selected_tools
        for name in ["manage_workers", "create_operation_work_order", "delete_crop_cycle"]
    )


def test_high_risk_delete_not_exposed_for_unknown_text() -> None:
    decision = SkillRouter().route("随便聊聊", TOOLS)

    assert "delete_crop_cycle" not in decision.selected_tools
```

- [ ] **Step 2: 运行回归测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/evaluation/test_skill_router_regression.py -v
```

Expected: PASS。

- [ ] **Step 3: 运行后端定向回归**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest \
  tests/agent/router \
  tests/test_tool_selector.py \
  tests/agent/test_runtime_router_binding.py \
  tests/agent/test_pending_plan_store.py \
  tests/agent/test_pending_plan_executor.py \
  tests/agent/test_pending_action_executor.py \
  tests/context/test_policy.py \
  tests/context/test_builder.py \
  tests/context/test_preload.py \
  tests/skills/test_create_operation_work_order.py \
  tests/evaluation/test_skill_router_regression.py \
  -v
```

Expected: PASS。

- [ ] **Step 4: 运行 admin-web 定向验证**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/admin-web
npx vitest run src/pages/Playground/sessionDebugExport.test.ts src/pages/Playground/index.test.ts
npx tsc --noEmit -p tsconfig.app.json
npx eslint src/pages/Playground/sessionDebugExport.ts src/pages/Playground/sessionDebugExport.test.ts src/pages/Playground/index.tsx src/api/agent.ts
```

Expected: PASS。若全量 lint 仍只有既有 unrelated hook dependency warning，在最终说明中标注为既有问题。

- [ ] **Step 5: 运行项目要求的 lint 与架构检查**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
ruff check backend/app backend/tests
ruff format --check backend/app backend/tests
bash scripts/check-layer-deps.sh
bash scripts/check-guide-sensor-pairing.sh
bash scripts/check-lint-expiry.sh
```

Expected: PASS。

- [ ] **Step 6: 检查污染文件未被纳入提交**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git status --short
git diff --name-only --cached
```

Expected: staged 文件只包含本计划列出的实现文件与测试文件，不包含 `__pycache__/`、`.DS_Store`、`*.pyc`、`*.egg-info/`、数据库 `*.db-shm`/`*.db-wal` 或移动端/admin-web unrelated 改动。

- [ ] **Step 7: 提交 Task 10**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/tests/evaluation/test_skill_router_regression.py
git commit -m "test: add skill router regression coverage"
```

---

## 自检清单

- Spec 覆盖：
  - Router/Catalog：Task 1、Task 2。
  - 禁止未知场景 fallback 全量工具：Task 2、Task 3、Task 10。
  - 常规 1-3 个工具、复杂最多 5 个、写操作最多 1 个写工具：Task 2。
  - final answer 阶段默认不重绑全量工具：Task 4。
  - read/write 隔离，未知写意图追问，未知读意图 safe default：Task 2、Task 3。
  - context/preload 由 `RouterDecision.context_dependencies` 驱动：Task 5。
  - 多意图写操作升级 pending plan：Task 7、Task 8。
  - 作业单工资不能静默为 0：Task 9。
  - admin-web debug JSON 包含 router diagnostics、pending plans、skill call I/O：Task 6。
  - session4/session5 回归：Task 8、Task 10。
- 占位符扫描：
  - 没有使用“待定”或“之后补”作为实现内容。
  - migration revision 需要执行者用唯一 id 替换 `<revision>`，替换动作在 Task 7 Step 4 明确要求，并给出可用值 `a3f1c9d8e7b4`。
- 类型一致性：
  - `RouterDecision.selected_tools` 在 router、runtime、trace 中保持 list[str]。
  - `context_dependencies` 在 router、state、ContextBuildRequest 中保持 list[str]。
  - `PendingPlanStep.depends_on` 对外为 list[str]，存储时标准化空列表。
