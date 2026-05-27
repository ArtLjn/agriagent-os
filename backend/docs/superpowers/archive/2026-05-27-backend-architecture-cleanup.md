# Backend Architecture Cleanup 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理 `app/core/` 目录的职责混杂问题 — 删除死代码、消除 prompt 双数据源、将模块按职责拆分到 `agent/` 和 `infra/` 包。

**Architecture:** 三分法拆分：`core/` 保留纯基础设施（config/database/logger/date_context/json_repair/seed），Agent 专属模块移入 `agent/`，可观测性/运维模块移入 `infra/`。所有改动为内部重组，不影响外部 API。

**Tech Stack:** Python 3.12 / FastAPI / pytest / ruff

---

## 文件结构

### 删除
- `app/core/term_whitelist.py` — 死代码，零引用

### 移动到 `app/agent/`（从 `app/agents/` + `app/core/`）
- `app/agents/graph.py` → `app/agent/graph.py`
- `app/agents/advisor.py` → `app/agent/advisor.py`
- `app/agents/report.py` → `app/agent/report.py`
- `app/agents/state.py` → `app/agent/state.py`
- `app/core/llm.py` → `app/agent/llm.py`
- `app/core/guardrails.py` → `app/agent/guardrails.py`
- `app/core/prompt_registry.py` → `app/agent/prompt_registry.py`
- `app/core/prompt_renderer.py` → `app/agent/prompt_renderer.py`
- `app/skills/` 目录整体 → `app/agent/skills/`

### 移动到 `app/infra/`（从 `app/core/`）
- `app/core/trace_collector.py` → `app/infra/trace_collector.py`
- `app/core/trace_dao.py` → `app/infra/trace_dao.py`
- `app/core/trace_context.py` → `app/infra/trace_context.py`
- `app/core/trace_cleaner.py` → `app/infra/trace_cleaner.py`
- `app/core/circuit_breaker.py` → `app/infra/circuit_breaker.py`
- `app/core/limiter.py` → `app/infra/limiter.py`
- `app/core/pending_actions.py` → `app/infra/pending_actions.py`
- `app/core/skill_cache.py` → `app/infra/skill_cache.py`

### 留在 `app/core/`（不动）
- `config.py`、`database.py`、`logger.py`、`date_context.py`、`json_repair.py`、`seed.py`

### 修改（import 更新）
- `app/main.py` — agents→agent、trace/limiter→infra
- `app/api/agent.py` — llm/limiter→agent+infra
- `app/api/cost.py` — prompt_registry/prompt_renderer/agents→agent
- `app/api/admin_config.py` — prompt_registry/skill_cache/skills→agent
- `app/services/agent_service.py` — agents/trace/guardrails/pending_actions/skills→agent+infra
- `app/agent/llm.py`（移动后）— circuit_breaker→infra
- `app/agent/prompt_renderer.py`（移动后）— prompt_registry→同包
- `app/agent/graph.py`（移动后）— llm/prompt_registry/prompt_renderer/pending_actions/trace→同包+infra
- `app/agent/advisor.py`（移动后）— guardrails/trace_context→同包+infra
- `app/agent/report.py`（移动后）— llm/guardrails/prompt_registry/prompt_renderer/skills→同包
- `app/infra/trace_collector.py`（移动后）— trace_dao/trace_context→同包

### 测试文件更新
- `tests/test_llm.py` — `app.core.llm` → `app.agent.llm`
- `tests/test_advisor_agent.py` — `app.agents.*` → `app.agent.*`
- `tests/test_agent_api.py` — `app.core.limiter` → `app.infra.limiter`
- `tests/test_agent_service.py` — `app.agents.*` + `app.core.*` → `app.agent.*` + `app.infra.*`
- `tests/test_prompt_registry.py` — `app.core.prompt_*` → `app.agent.prompt_*`、`app.agents.graph` → `app.agent.graph`
- `tests/test_pending_actions.py` — `app.core.pending_actions` → `app.infra.pending_actions`、`app.agents.graph` → `app.agent.graph`
- `tests/test_function_calling_e2e.py` — `app.agents.graph` → `app.agent.graph`
- `tests/core/test_guardrails.py` — `app.core.guardrails` → `app.agent.guardrails`
- `tests/core/test_prompt_registry.py` — `app.core.prompt_registry` → `app.agent.prompt_registry`
- `tests/core/test_prompt_renderer.py` — `app.core.prompt_*` → `app.agent.prompt_*`
- `tests/core/test_prompt_injection.py` — `app.core.prompt_*` → `app.agent.prompt_*`
- `tests/core/test_trace_collector.py` — `app.core.trace_*` → `app.infra.trace_*`
- `tests/core/test_trace_dao.py` — `app.core.trace_dao` → `app.infra.trace_dao`
- `tests/core/test_trace_context.py` — `app.core.trace_context` → `app.infra.trace_context`
- `tests/core/test_trace_cleaner.py` — `app.core.trace_cleaner` → `app.infra.trace_cleaner`
- `tests/agents/test_guardrails_integration.py` — `app.agents.*` → `app.agent.*`
- `tests/api/test_admin_config.py` — `app.core.prompt_registry` + `app.skills` → `app.agent.*`
- `tests/api/test_agent_api.py` — `app.core.limiter` → `app.infra.limiter`

---

## Task 1: 删除死代码 term_whitelist.py

**Files:**
- Delete: `app/core/term_whitelist.py`
- Test: `tests/`（无需新增测试，只需确认无影响）

- [ ] **Step 1: 全局搜索确认无残留引用**

Run: `cd backend && grep -r "term_whitelist\|is_whitelisted\|_AGRICULTURAL_TERMS" --include="*.py" .`
Expected: 只在 `app/core/term_whitelist.py` 自身出现，无其他文件引用

- [ ] **Step 2: 删除文件**

Run: `rm backend/app/core/term_whitelist.py`

- [ ] **Step 3: 运行全量测试确认无影响**

Run: `cd backend && python -m pytest -v`
Expected: 所有测试 PASS

- [ ] **Step 4: 提交**

```bash
cd backend && git add -A && git commit -m "chore: 删除死代码 term_whitelist.py（零引用）"
```

---

## Task 2: 消除 prompt 双数据源 — 删除 _DEFAULT_PROMPTS 和 get_fallback

**Files:**
- Modify: `app/core/prompt_registry.py`
- Modify: `app/core/prompt_renderer.py`
- Modify: `tests/core/test_prompt_injection.py` — 删除 `TestFallbackTemplateUpdate` 类
- Modify: `tests/core/test_prompt_renderer.py` — 修改 fallback 测试

### 2a: 删除 _DEFAULT_PROMPTS 和 get_fallback

- [ ] **Step 1: 写失败测试 — 验证 get_fallback 不再存在**

修改 `tests/core/test_prompt_registry.py`，新增测试：

```python
def test_get_fallback_removed():
    """get_fallback 方法已被删除。"""
    reg = PromptRegistry()
    assert not hasattr(reg, "get_fallback")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/core/test_prompt_registry.py::test_get_fallback_removed -v`
Expected: FAIL — `get_fallback` 仍然存在

- [ ] **Step 3: 删除 `_DEFAULT_PROMPTS` 字典和 `get_fallback` 方法**

编辑 `app/core/prompt_registry.py`：
1. 删除 `_DEFAULT_PROMPTS` 字典（第 12-51 行，整个变量定义）
2. 删除 `get_fallback` 方法（第 142-144 行）
3. 删除 `__all__` 中的相关条目（如有）

删除后的文件应只保留 `PromptRegistry` 类和 `get_registry()` 函数。

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && python -m pytest tests/core/test_prompt_registry.py -v`
Expected: PASS

### 2b: 修改 prompt_renderer — 模板未注册时抛 KeyError

- [ ] **Step 5: 写失败测试 — 模板未注册时抛出 KeyError**

修改 `tests/core/test_prompt_renderer.py`，新增测试：

```python
def test_render_raises_on_unregistered_template(self):
    """模板未注册时抛出 KeyError，不再静默回退。"""
    reg = PromptRegistry()
    with pytest.raises(KeyError, match="system_base"):
        render_prompt("system_base", {}, registry=reg, current_date=date(2026, 5, 25))
```

- [ ] **Step 6: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/core/test_prompt_renderer.py::TestPromptRenderer::test_render_raises_on_unregistered_template -v`
Expected: FAIL — 当前 `render_prompt` 会回退到 `get_fallback`

- [ ] **Step 7: 修改 prompt_renderer.py — 移除 fallback 逻辑**

编辑 `app/core/prompt_renderer.py`，将 `render_prompt` 函数改为：

```python
def render_prompt(
    name: str,
    variables: dict | None = None,
    *,
    registry: "PromptRegistry | None" = None,
    current_date: date | None = None,
    version: str | None = None,
) -> str:
    """渲染指定名称的 prompt 模板。

    Args:
        name: 模板名称（注册表中的 key）。
        variables: 用户自定义变量。
        registry: PromptRegistry 实例，默认使用全局实例。
        current_date: 当前日期，默认使用服务端今天。
        version: 指定版本，默认使用注册表默认版本。

    Returns:
        渲染后的 prompt 字符串。

    Raises:
        KeyError: 模板未注册。
        TemplateError: 模板语法错误。
    """
    from app.core.prompt_registry import get_registry

    reg = registry or get_registry()
    template_str = reg.get(name, version)
    logger.debug(
        "模板渲染 | name=%s | hit=true | vars=%s",
        name,
        list((variables or {}).keys()),
    )

    builtin_vars = _build_builtin_vars(current_date)
    ctx = {**builtin_vars, **(variables or {})}
    template = Template(template_str)
    return template.render(ctx)
```

- [ ] **Step 8: 运行测试确认 PASS**

Run: `cd backend && python -m pytest tests/core/test_prompt_renderer.py -v`
Expected: PASS

### 2c: 修复依赖 fallback 的测试

- [ ] **Step 9: 修改 `tests/core/test_prompt_renderer.py` 的 fallback 测试**

将 `test_render_fallback_on_template_error` 修改为验证抛出异常：

```python
def test_render_raises_on_template_syntax_error(self):
    """模板语法错误时抛出 TemplateError。"""
    from jinja2 import TemplateError

    reg = PromptRegistry()
    reg.register("test", "v1", "bad {{ unclosed")
    with pytest.raises(TemplateError):
        render_prompt("test", {}, registry=reg, current_date=date(2026, 5, 25))
```

- [ ] **Step 10: 修改 `tests/core/test_prompt_injection.py` — 删除 TestFallbackTemplateUpdate**

删除整个 `TestFallbackTemplateUpdate` 类（第 190-221 行），包含 `test_fallback_contains_display_name`、`test_fallback_contains_farm_context_summary`、`test_fallback_renders_with_variables` 三个方法。这些测试依赖已删除的 `_DEFAULT_PROMPTS` 和 `get_fallback`。

- [ ] **Step 11: 修改 `tests/test_prompt_registry.py` — 修复引用 _DEFAULT_PROMPTS 的测试**

在 `tests/test_prompt_registry.py` 中找到 `test_system_base_prompt_contains_tool_calling_rule` 测试。此测试直接检查 `_DEFAULT_PROMPTS`，需要改为从文件加载后验证：

```python
def test_system_base_prompt_contains_tool_calling_rule():
    """system_base 模板包含工具调用硬约束规则。"""
    from pathlib import Path
    prompts_dir = Path(__file__).resolve().parent.parent / "app" / "prompts"
    base_j2 = prompts_dir / "base.j2"
    if base_j2.exists():
        content = base_j2.read_text()
        assert "禁止凭记忆回答" in content
        assert "必须先调用对应工具" in content
```

- [ ] **Step 12: 运行全量测试**

Run: `cd backend && python -m pytest -v`
Expected: PASS

- [ ] **Step 13: 提交**

```bash
cd backend && git add -A && git commit -m "refactor: 删除 _DEFAULT_PROMPTS 双数据源，模板未注册时抛 KeyError"
```

---

## Task 3: 创建 agent/ 包并迁移 Agent 模块

**Files:**
- Create: `app/agent/__init__.py`
- Move: `app/agents/*.py` → `app/agent/*.py`
- Move: `app/core/llm.py` → `app/agent/llm.py`
- Move: `app/core/guardrails.py` → `app/agent/guardrails.py`
- Move: `app/core/prompt_registry.py` → `app/agent/prompt_registry.py`
- Move: `app/core/prompt_renderer.py` → `app/agent/prompt_renderer.py`
- Move: `app/skills/` → `app/agent/skills/`

> **注意：** 此 Task 只做文件移动和包内 import 修正。对外部 import 的更新在 Task 5 进行。

- [ ] **Step 1: 创建 agent/ 包**

```bash
mkdir -p backend/app/agent
```

创建 `backend/app/agent/__init__.py`：

```python
"""Agent 模块 — Agent 领域逻辑（LLM、guardrails、prompt、skills）。"""
```

- [ ] **Step 2: 移动 agents/ 下的 4 个文件**

```bash
cd backend
git mv app/agents/graph.py app/agent/graph.py
git mv app/agents/advisor.py app/agent/advisor.py
git mv app/agents/report.py app/agent/report.py
git mv app/agents/state.py app/agent/state.py
```

- [ ] **Step 3: 移动 core/ 下的 4 个 Agent 模块**

```bash
cd backend
git mv app/core/llm.py app/agent/llm.py
git mv app/core/guardrails.py app/agent/guardrails.py
git mv app/core/prompt_registry.py app/agent/prompt_registry.py
git mv app/core/prompt_renderer.py app/agent/prompt_renderer.py
```

- [ ] **Step 4: 移动 skills/ 目录**

```bash
cd backend
git mv app/skills app/agent/skills
```

- [ ] **Step 5: 删除旧的 agents/ 目录**

```bash
rm -rf backend/app/agents
```

（git mv 后旧目录应已空，只需确认删除）

- [ ] **Step 6: 修复 agent/ 包内部交叉引用的 import**

`app/agent/llm.py` 第 14 行：
```python
# 旧: from app.core.circuit_breaker import CircuitBreaker, call_with_retry
from app.infra.circuit_breaker import CircuitBreaker, call_with_retry
```
> 注：circuit_breaker 此时还未移到 infra/，但 Task 4 会处理。此处先保持 `from app.core.circuit_breaker` 不变，在 Task 5 统一更新。

实际上，为避免中间态 import 错误，**agent/ 包内的交叉引用暂时不动**，统一在 Task 5 一起更新。此处只确认文件已移动到位。

- [ ] **Step 7: 验证文件结构**

Run: `ls -la backend/app/agent/`
Expected: 看到 `__init__.py`、`graph.py`、`advisor.py`、`report.py`、`state.py`、`llm.py`、`guardrails.py`、`prompt_registry.py`、`prompt_renderer.py`、`skills/` 目录

Run: `ls backend/app/agents/ 2>/dev/null || echo "已删除"`
Expected: "已删除" 或目录不存在

- [ ] **Step 8: 暂不提交（等 Task 4 完成后一起提交）**

---

## Task 4: 创建 infra/ 包并迁移可观测性模块

**Files:**
- Create: `app/infra/__init__.py`
- Move: `app/core/trace_*.py` (4个) → `app/infra/`
- Move: `app/core/circuit_breaker.py` → `app/infra/`
- Move: `app/core/limiter.py` → `app/infra/`
- Move: `app/core/pending_actions.py` → `app/infra/`
- Move: `app/core/skill_cache.py` → `app/infra/`

- [ ] **Step 1: 创建 infra/ 包**

```bash
mkdir -p backend/app/infra
```

创建 `backend/app/infra/__init__.py`：

```python
"""Infra 模块 — 可观测性、容错、限流、缓存等运维基础设施。"""
```

- [ ] **Step 2: 移动 8 个模块**

```bash
cd backend
git mv app/core/trace_collector.py app/infra/trace_collector.py
git mv app/core/trace_dao.py app/infra/trace_dao.py
git mv app/core/trace_context.py app/infra/trace_context.py
git mv app/core/trace_cleaner.py app/infra/trace_cleaner.py
git mv app/core/circuit_breaker.py app/infra/circuit_breaker.py
git mv app/core/limiter.py app/infra/limiter.py
git mv app/core/pending_actions.py app/infra/pending_actions.py
git mv app/core/skill_cache.py app/infra/skill_cache.py
```

- [ ] **Step 3: 验证 core/ 目录仅剩基础设施**

Run: `ls backend/app/core/`
Expected: `__init__.py`、`config.py`、`database.py`、`logger.py`、`date_context.py`、`json_repair.py`、`seed.py`（共 7 个文件）

- [ ] **Step 4: 验证 infra/ 目录结构**

Run: `ls backend/app/infra/`
Expected: `__init__.py` + 8 个模块文件（共 9 个文件）

- [ ] **Step 5: 暂不提交（等 Task 5 完成后一起提交）**

---

## Task 5: 批量更新所有 import 路径

**Files:**
- Modify: 所有引用了被移动模块的 .py 文件（约 30+ 处）

这是最关键的 Task。按文件逐一更新。

### 5a: 更新 `app/agent/` 内部交叉引用

- [ ] **Step 1: 更新 `app/agent/llm.py`**

第 14 行：
```python
# 旧: from app.core.circuit_breaker import CircuitBreaker, call_with_retry
from app.infra.circuit_breaker import CircuitBreaker, call_with_retry
```

- [ ] **Step 2: 更新 `app/agent/prompt_renderer.py`**

第 10 行和第 52 行：
```python
# 旧: from app.core.prompt_registry import PromptRegistry
from app.agent.prompt_registry import PromptRegistry

# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry
```

- [ ] **Step 3: 更新 `app/agent/advisor.py`**

```python
# 旧: from app.agents.graph import compile_advisor_graph
from app.agent.graph import compile_advisor_graph

# 旧: from app.core.guardrails import check_input, filter_output
from app.agent.guardrails import check_input, filter_output

# 旧: from app.core.trace_context import clear_trace, init_trace
from app.infra.trace_context import clear_trace, init_trace
```

- [ ] **Step 4: 更新 `app/agent/graph.py`**

```python
# 旧: from app.core.llm import get_llm
from app.agent.llm import get_llm

# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry

# 旧: from app.core.prompt_renderer import render_prompt
from app.agent.prompt_renderer import render_prompt

# 旧: from app.core.pending_actions import is_write_skill, store_pending
from app.infra.pending_actions import is_write_skill, store_pending

# 旧: from app.core.trace_collector import get_collector
from app.infra.trace_collector import get_collector

# 旧: from app.core.trace_context import increment_round
from app.infra.trace_context import increment_round

# 旧: from app.skills import get_langchain_tools
from app.agent.skills import get_langchain_tools
```

- [ ] **Step 5: 更新 `app/agent/report.py`**

```python
# 旧: from app.core.llm import get_llm
from app.agent.llm import get_llm

# 旧: from app.core.guardrails import filter_output
from app.agent.guardrails import filter_output

# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry

# 旧: from app.core.prompt_renderer import render_prompt
from app.agent.prompt_renderer import render_prompt

# 旧: from app.skills import get_langchain_tools
from app.agent.skills import get_langchain_tools
```

### 5b: 更新 `app/infra/` 内部交叉引用

- [ ] **Step 6: 更新 `app/infra/trace_collector.py`**

```python
# 旧: from app.core.trace_dao import TraceDAO
from app.infra.trace_dao import TraceDAO

# 旧: from app.core.trace_context import get_trace, get_round_index
from app.infra.trace_context import get_trace, get_round_index
```

### 5c: 更新 `app/api/` 下的文件

- [ ] **Step 7: 更新 `app/api/agent.py`**

```python
# 旧: from app.core.llm import LlmNotConfiguredError
from app.agent.llm import LlmNotConfiguredError

# 旧: from app.core.limiter import limiter
from app.infra.limiter import limiter
```

- [ ] **Step 8: 更新 `app/api/cost.py`**

```python
# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry

# 旧: from app.core.prompt_renderer import render_prompt
from app.agent.prompt_renderer import render_prompt

# 旧: from app.agents.advisor import invoke_advisor
from app.agent.advisor import invoke_advisor
```

- [ ] **Step 9: 更新 `app/api/admin_config.py`**

```python
# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry

# 旧: from app.core.skill_cache import clear_cache
from app.infra.skill_cache import clear_cache

# 旧: from app.skills import get_skill_manager
from app.agent.skills import get_skill_manager

# 旧: from app.skills import clear_skill_cache
from app.agent.skills import clear_skill_cache
```

### 5d: 更新 `app/services/` 下的文件

- [ ] **Step 10: 更新 `app/services/agent_service.py`**

```python
# 旧: from app.agents.advisor import invoke_advisor, stream_advisor
from app.agent.advisor import invoke_advisor, stream_advisor

# 旧: from app.agents.report import generate_cycle_report
from app.agent.report import generate_cycle_report

# 旧: from app.core.pending_actions import ...
from app.infra.pending_actions import ...

# 旧: from app.core.trace_collector import get_collector
from app.infra.trace_collector import get_collector

# 旧: from app.core.trace_context import clear_trace, init_trace
from app.infra.trace_context import clear_trace, init_trace

# 旧: from app.core.guardrails import filter_output
from app.agent.guardrails import filter_output

# 旧: from app.skills import build_skill_context, get_langchain_tools
from app.agent.skills import build_skill_context, get_langchain_tools

# 旧: from app.skills import get_skill_manager
from app.agent.skills import get_skill_manager
```

### 5e: 更新 `app/main.py`

- [ ] **Step 11: 更新 `app/main.py`**

```python
# 旧: from app.core.limiter import limiter
from app.infra.limiter import limiter

# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry

# 旧: from app.core.trace_cleaner import clean_expired_traces
from app.infra.trace_cleaner import clean_expired_traces

# 旧: from app.core.trace_collector import start_trace_system, stop_trace_system
from app.infra.trace_collector import start_trace_system, stop_trace_system
```

### 5f: 更新 `app/agent/skills/` 下引用 skill_cache 的文件

- [ ] **Step 12: 更新所有 skills 中的 skill_cache import**

需要更新以下文件中的 `from app.core.skill_cache import cached`：
- `app/agent/skills/cost-summary/scripts/main.py`
- `app/agent/skills/crop-cycle/scripts/main.py`
- `app/agent/skills/cost-analytics/scripts/main.py`
- `app/agent/skills/farm-logs/scripts/main.py`
- `app/agent/skills/weather/scripts/main.py`

全部改为：
```python
from app.infra.skill_cache import cached
```

同时需要更新 `app/agent/skills/__init__.py` 中对 `app.core.config` 的引用（保持不变，因为 config 还在 core/）。

### 5g: 批量验证 — 全局搜索确认无残留

- [ ] **Step 13: 全局搜索确认旧路径零残留**

Run:
```bash
cd backend && grep -r "from app\.core\.llm\|from app\.core\.guardrails\|from app\.core\.prompt_registry\|from app\.core\.prompt_renderer\|from app\.core\.trace_collector\|from app\.core\.trace_dao\|from app\.core\.trace_context\|from app\.core\.trace_cleaner\|from app\.core\.circuit_breaker\|from app\.core\.limiter\|from app\.core\.pending_actions\|from app\.core\.skill_cache\|from app\.core\.term_whitelist\|from app\.agents\." --include="*.py" .
```
Expected: 零匹配

- [ ] **Step 14: 运行全量测试**

Run: `cd backend && python -m pytest -v`
Expected: PASS

- [ ] **Step 15: 运行 ruff 检查**

Run: `cd backend && ruff check . && ruff format .`
Expected: 无错误

- [ ] **Step 16: 提交 Task 3+4+5 的所有改动**

```bash
cd backend && git add -A && git commit -m "refactor: core/ 三分法拆分 — Agent 模块移入 agent/，可观测性模块移入 infra/"
```

---

## Task 6: 更新所有测试文件的 import 路径

**Files:**
- Modify: ~15 个测试文件

### 6a: `tests/test_llm.py`

- [ ] **Step 1: 替换 import**

```python
# 旧: from app.core.llm import LlmNotConfiguredError
from app.agent.llm import LlmNotConfiguredError

# 旧: import app.core.llm as llm_module
import app.agent.llm as llm_module

# 旧: from app.core.llm import get_llm
from app.agent.llm import get_llm
```

需要更新所有 `@patch("app.core.llm...")` 装饰器：
```python
# 旧: @patch("app.core.llm.settings")
@patch("app.agent.llm.settings")

# 旧: @patch("app.core.llm.ChatOpenAI")
@patch("app.agent.llm.ChatOpenAI")
```

### 6b: `tests/test_advisor_agent.py`

- [ ] **Step 2: 替换 import**

```python
# 旧: from app.agents.advisor import ...
from app.agent.advisor import build_advisor_agent, invoke_advisor, stream_advisor, _build_history_messages
```

### 6c: `tests/test_agent_api.py`（根目录）

- [ ] **Step 3: 替换 import**

```python
# 旧: from app.core.limiter import limiter
from app.infra.limiter import limiter
```

### 6d: `tests/test_agent_service.py`

- [ ] **Step 4: 替换 import**

```python
# 旧: from app.core.pending_actions import store_pending, remove_pending
from app.infra.pending_actions import store_pending, remove_pending
```

### 6e: `tests/test_prompt_registry.py`（根目录）

- [ ] **Step 5: 替换 import**

```python
# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry

# 旧: from app.core.prompt_renderer import render_prompt
from app.agent.prompt_renderer import render_prompt

# 旧: from app.agents.graph import _get_season
from app.agent.graph import _get_season
```

### 6f: `tests/test_pending_actions.py`

- [ ] **Step 6: 替换 import**

```python
# 旧: from app.core.pending_actions import ...
from app.infra.pending_actions import ...

# 旧: from app.agents.graph import _parallel_tool_node
from app.agent.graph import _parallel_tool_node
```

### 6g: `tests/test_function_calling_e2e.py`

- [ ] **Step 7: 替换 import**

```python
# 旧: from app.agents.graph import compile_advisor_graph
from app.agent.graph import compile_advisor_graph
```

### 6h: `tests/core/` 下的测试文件

- [ ] **Step 8: 更新 `tests/core/test_guardrails.py`**

```python
# 旧: from app.core.guardrails import check_input, filter_output
from app.agent.guardrails import check_input, filter_output
```

- [ ] **Step 9: 更新 `tests/core/test_prompt_registry.py`**

```python
# 旧: from app.core.prompt_registry import PromptRegistry
from app.agent.prompt_registry import PromptRegistry
```

- [ ] **Step 10: 更新 `tests/core/test_prompt_renderer.py`**

```python
# 旧: from app.core.prompt_renderer import render_prompt
from app.agent.prompt_renderer import render_prompt

# 旧: from app.core.prompt_registry import PromptRegistry
from app.agent.prompt_registry import PromptRegistry
```

- [ ] **Step 11: 更新 `tests/core/test_prompt_injection.py`**

```python
# 旧: from app.core.prompt_renderer import render_prompt
from app.agent.prompt_renderer import render_prompt

# 旧: from app.core.prompt_registry import PromptRegistry
from app.agent.prompt_registry import PromptRegistry
```

- [ ] **Step 12: 更新 `tests/core/test_trace_collector.py`**

```python
# 旧: from app.core.trace_collector import TraceCollector
from app.infra.trace_collector import TraceCollector

# 旧: from app.core.trace_context import init_trace, clear_trace
from app.infra.trace_context import init_trace, clear_trace
```

- [ ] **Step 13: 更新 `tests/core/test_trace_dao.py`**

```python
# 旧: from app.core.trace_dao import TraceDAO
from app.infra.trace_dao import TraceDAO
```

- [ ] **Step 14: 更新 `tests/core/test_trace_context.py`**

```python
# 旧: from app.core.trace_context import ...
from app.infra.trace_context import ...
```

- [ ] **Step 15: 更新 `tests/core/test_trace_cleaner.py`**

```python
# 旧: from app.core.trace_cleaner import clean_expired_traces
from app.infra.trace_cleaner import clean_expired_traces
```

### 6i: `tests/agents/` 和 `tests/api/` 下的测试文件

- [ ] **Step 16: 更新 `tests/agents/test_guardrails_integration.py`**

```python
# 旧: from app.agents.advisor import invoke_advisor, stream_advisor
from app.agent.advisor import invoke_advisor, stream_advisor

# 旧: from app.agents.report import generate_cycle_report
from app.agent.report import generate_cycle_report
```

- [ ] **Step 17: 更新 `tests/api/test_agent_api.py`**

```python
# 旧: from app.core.limiter import limiter
from app.infra.limiter import limiter
```

- [ ] **Step 18: 更新 `tests/api/test_admin_config.py`**

```python
# 旧: from app.core.prompt_registry import get_registry
from app.agent.prompt_registry import get_registry

# 旧: from app.skills import get_skill_manager
from app.agent.skills import get_skill_manager
```

### 6j: 验证

- [ ] **Step 19: 运行全量测试**

Run: `cd backend && python -m pytest -v`
Expected: PASS

- [ ] **Step 20: 运行 ruff 检查**

Run: `cd backend && ruff check . && ruff format .`
Expected: 无错误

- [ ] **Step 21: 提交**

```bash
cd backend && git add -A && git commit -m "test: 更新所有测试文件的 import 路径以匹配新包结构"
```

---

## Task 7: 最终验证与收尾

**Files:**
- Modify: 项目根目录 `CLAUDE.md`（更新目录说明）

- [ ] **Step 1: 全局搜索确认零残留**

Run:
```bash
cd backend && grep -r "from app\.core\.\(llm\|guardrails\|prompt_registry\|prompt_renderer\|term_whitelist\|trace_collector\|trace_dao\|trace_context\|trace_cleaner\|circuit_breaker\|limiter\|pending_actions\|skill_cache\)" --include="*.py" . | grep -v "__pycache__"
```
Expected: 零匹配

Run:
```bash
cd backend && grep -r "from app\.agents\." --include="*.py" . | grep -v "__pycache__"
```
Expected: 零匹配

- [ ] **Step 2: 确认 `app/core/` 目录仅剩 7 个文件**

Run: `ls backend/app/core/`
Expected: `__init__.py`、`config.py`、`database.py`、`logger.py`、`date_context.py`、`json_repair.py`、`seed.py`

- [ ] **Step 3: 确认 `app/agent/` 目录结构完整**

Run: `ls -R backend/app/agent/`
Expected: `__init__.py`、`graph.py`、`advisor.py`、`report.py`、`state.py`、`llm.py`、`guardrails.py`、`prompt_registry.py`、`prompt_renderer.py`、`skills/` 目录

- [ ] **Step 4: 确认 `app/infra/` 目录结构完整**

Run: `ls backend/app/infra/`
Expected: `__init__.py` + 8 个模块文件

- [ ] **Step 5: 运行全量测试最终确认**

Run: `cd backend && python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: 运行 ruff 最终确认**

Run: `cd backend && ruff check . && ruff format .`
Expected: 无错误

- [ ] **Step 7: 更新 CLAUDE.md 快速导航表**

在项目根目录 `CLAUDE.md` 的硬性规则部分，更新依赖方向说明：

```
1. 依赖方向：schemas/ → agent/ → api/ → infra/ → core/ → models/ → services/（后端）
```

（将原来的 `agents/` 改为 `agent/`，新增 `infra/`）

- [ ] **Step 8: 提交收尾**

```bash
cd backend && git add -A && git commit -m "docs: 更新 CLAUDE.md 依赖方向说明，反映 agent/infra/core 三分法"
```
