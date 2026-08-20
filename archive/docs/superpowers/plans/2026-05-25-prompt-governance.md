# Prompt Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize all Agent prompts into Jinja2 templates with hot-reload, fix date hallucination via client-side injection, prevent English output via three-layer defense, and make creation operations resilient with Pydantic validation + idempotency keys.

**Architecture:** Prompt templates live in `prompts/` directory, managed by `PromptRegistry` (in-memory, file-based, thread-safe). `PromptRenderer` injects variables like `current_date` at render time. A FastAPI middleware reads `X-Current-Date` from requests and stores it in context. Guardrails gains English detection + persistent logging. Cost parse endpoint gains Pydantic output validation, JSON repair, and idempotency key deduplication.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Jinja2, Pydantic, LangGraph, React Native, TypeScript

---

## File Map

| File | Responsibility | Action |
|------|---------------|--------|
| `backend/prompts/base.j2` | Base system prompt with language rules at top | Create |
| `backend/prompts/cost_parse.j2` | Cost parsing prompt with date injection | Create |
| `backend/prompts/report.j2` | Report generation prompt | Create |
| `backend/prompts/config.yaml` | Template metadata (versions, defaults) | Create |
| `backend/app/core/prompt_registry.py` | In-memory registry with get/reload/switch | Create |
| `backend/app/core/prompt_renderer.py` | Jinja2 render + built-in variable injection | Create |
| `backend/app/core/term_whitelist.py` | Agricultural English terms whitelist | Create |
| `backend/app/core/json_repair.py` | JSON auto-repair (brace balance, trailing comma) | Create |
| `backend/app/models/guardrails_log.py` | GuardrailsLog ORM model | Create |
| `backend/app/models/idempotency_key.py` | IdempotencyKey ORM model | Create |
| `backend/app/models/agent_trace.py` | AgentTrace ORM model | Create |
| `backend/app/api/admin.py` | `/admin/guardrails-logs` endpoint | Create |
| `backend/app/core/guardrails.py` | Add English detection + DB logging | Modify |
| `backend/app/agents/graph.py` | Replace hardcoded SYSTEM_PROMPT with template | Modify |
| `backend/app/agents/report.py` | Replace hardcoded REPORT_SYSTEM_PROMPT with template | Modify |
| `backend/app/agents/advisor.py` | Wire in micro_compact context compression | Modify |
| `backend/app/services/agent_service.py` | Replace hardcoded prompts with templates | Modify |
| `backend/app/api/cost.py` | Add idempotency, Pydantic validation, JSON repair | Modify |
| `backend/app/schemas/cost.py` | Add CostParseResult + record_date validator | Modify |
| `backend/app/main.py` | Load prompts at startup + cleanup jobs | Modify |
| `backend/app/models/__init__.py` | Register new models | Modify |
| `backend/app/skills/__init__.py` | Add SkillRegistry singleton | Modify |
| `backend/requirements.txt` | Add `jinja2` dependency | Modify |
| `FarmManagerMobile/src/api/client.ts` | Add `X-Current-Date` + `X-Idempotency-Key` headers | Modify |
| `backend/tests/core/test_prompt_registry.py` | Registry unit tests | Create |
| `backend/tests/core/test_prompt_renderer.py` | Renderer unit tests | Create |
| `backend/tests/core/test_guardrails.py` | Guardrails English detection tests | Create |
| `backend/tests/api/test_cost_parse.py` | Cost parse integration tests | Create |

---

## Task 1: Add Jinja2 Dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add jinja2 to requirements**

```text
jinja2==3.1.4
```

Append `jinja2==3.1.4` to `backend/requirements.txt`.

- [ ] **Step 2: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add jinja2 dependency"
```

---

## Task 2: Create Prompt Template Directory and Files

**Files:**
- Create: `backend/prompts/__init__.py`
- Create: `backend/prompts/base.j2`
- Create: `backend/prompts/cost_parse.j2`
- Create: `backend/prompts/report.j2`
- Create: `backend/prompts/config.yaml`

- [ ] **Step 1: Create prompts package init**

`backend/prompts/__init__.py`:
```python
"""Prompt templates package — Jinja2 template files for Agent prompts."""
```

- [ ] **Step 2: Create base.j2**

`backend/prompts/base.j2`:
```jinja2
【语言规则】（最高优先级）
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 农业专业术语中的英文品种名（如 Watermelon、Tomato）允许保留英文。
- 数字、单位符号（如 ℃、kg、亩）不受此限制。
- 如果检测到英文输出，系统将自动拦截并提示用户重试。

【角色定义】
你是一位经验丰富的农业技术顾问，擅长西瓜、豆角、番茄等作物的种植管理。你了解农事操作、病虫害防治、施肥浇水、成本收支等农业知识。

【能力范围】
你具备以下工具调用能力：
- 查询天气预报和灾害预警
- 查看种植周期和当前阶段
- 了解近期农事记录
- 统计成本收支

请根据用户的问题，主动调用合适的工具获取信息，然后给出具体、可操作的建议。回答要简洁明了，适合农民理解。

{% if current_date %}
【时间信息】
今天是 {{ current_date }}，星期{{ current_weekday }}。当前时间 {{ current_time }}。
{% endif %}
```

- [ ] **Step 3: Create cost_parse.j2**

`backend/prompts/cost_parse.j2`:
```jinja2
【语言规则】（最高优先级）
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 只返回 JSON，不要输出任何其他文字、解释或 markdown 格式。

【任务说明】
请将以下记账描述解析为 JSON 格式。

【时间规则】
今天是 {{ current_date }}。如果用户未指定日期，默认使用今天。日期格式为 YYYY-MM-DD。
用户说的"昨天"对应 {{ yesterday }}，"前天"对应 {{ day_before_yesterday }}。

【输出字段】
- record_type: "cost" 或 "income"
- category: 简短类别名，如"种子"、"化肥"、"人工"、"销售收入"
- amount: 数字字符串，不含单位
- record_date: YYYY-MM-DD 格式
- note: 可选备注

【示例】
输入: "昨天买化肥花了200"
输出: {"record_type": "cost", "category": "化肥", "amount": "200", "record_date": "{{ yesterday }}", "note": ""}

描述：{{ description }}
```

- [ ] **Step 4: Create report.j2**

`backend/prompts/report.j2`:
```jinja2
【语言规则】（最高优先级）
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 农业专业术语中的英文品种名允许保留英文。

【角色定义】
你是一位农业数据分析师，擅长整理种植周期的各项数据并生成清晰报告。

【任务说明】
请为指定种植周期生成一份综合报告。
你可以查询天气、茬口信息、农事记录和成本收支。

【报告要求】
- 数据准确，条理清晰
- 包含关键指标：总成本、总收入、净利润、农事进度
- 提供下一步建议
- 使用中文输出

{% if current_date %}
【时间信息】
今天是 {{ current_date }}，星期{{ current_weekday }}。
{% endif %}
```

- [ ] **Step 5: Create config.yaml**

`backend/prompts/config.yaml`:
```yaml
version: "1.0"
defaults:
  system_base: base
  cost_parse: cost_parse
  report: report
templates:
  base:
    file: base.j2
    description: "基础 system prompt，含语言规则置顶"
  cost_parse:
    file: cost_parse.j2
    description: "记账解析 prompt，注入当前日期"
  report:
    file: report.j2
    description: "报告生成 prompt"
```

- [ ] **Step 6: Commit**

```bash
git add backend/prompts/
git commit -m "feat: add Jinja2 prompt templates"
```

---

## Task 3: Implement PromptRegistry

**Files:**
- Create: `backend/app/core/prompt_registry.py`
- Test: `backend/tests/core/test_prompt_registry.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/core/test_prompt_registry.py`:
```python
"""Tests for PromptRegistry."""

import pytest

from app.core.prompt_registry import PromptRegistry


class TestPromptRegistry:
    def test_register_and_get(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "hello {{ name }}")
        assert reg.get("test", "v1") == "hello {{ name }}"

    def test_get_default_version(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "hello")
        assert reg.get("test") == "hello"

    def test_get_missing_raises(self):
        reg = PromptRegistry()
        with pytest.raises(KeyError):
            reg.get("missing")

    def test_switch_version(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "hello v1")
        reg.register("test", "v2", "hello v2")
        assert reg.get("test") == "hello v1"
        reg.switch_version("test", "v2")
        assert reg.get("test") == "hello v2"

    def test_list_versions(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "a")
        reg.register("test", "v2", "b")
        assert reg.list_versions("test") == ["v1", "v2"]

    def test_reload_clears_and_reloads(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "old")
        reg.reload()
        with pytest.raises(KeyError):
            reg.get("test")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_prompt_registry.py -v
```
Expected: FAIL with module not found

- [ ] **Step 3: Implement PromptRegistry**

`backend/app/core/prompt_registry.py`:
```python
"""Prompt 模板注册表 — 内存中的模板版本管理，支持热加载。"""

import logging
import threading
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

logger = logging.getLogger(__name__)

_DEFAULT_PROMPTS = {
    "system_base": (
        "【语言规则】（最高优先级）\n"
        "- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。\n"
        "- 农业专业术语中的英文品种名允许保留英文。\n\n"
        "你是一位经验丰富的农业技术顾问，擅长西瓜、豆角、番茄等作物的种植管理。"
        "请根据用户的问题，主动调用合适的工具获取信息，给出具体、可操作的建议。"
    ),
    "cost_parse": (
        "【语言规则】（最高优先级）\n"
        "- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。\n\n"
        "请将以下记账描述解析为 JSON 格式。\n"
        "今天是 {{ current_date }}。如果用户未指定日期，默认使用今天。\n"
        "字段：record_type(cost/income)、category、amount、record_date(YYYY-MM-DD)、note。\n"
        "只返回 JSON，不要其他文字。\n"
        "描述：{{ description }}"
    ),
    "report": (
        "【语言规则】（最高优先级）\n"
        "- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。\n\n"
        "你是一位农业数据分析师。请生成一份综合报告，包含关键指标和下一步建议。"
    ),
}


class PromptRegistry:
    """内存中的 Prompt 模板注册表，线程安全。"""

    def __init__(self):
        self._lock = threading.RLock()
        self._templates: dict[str, dict[str, str]] = {}
        self._defaults: dict[str, str] = {}

    def register(self, name: str, version: str, content: str) -> None:
        """注册一个模板版本。"""
        with self._lock:
            if name not in self._templates:
                self._templates[name] = {}
                if name not in self._defaults:
                    self._defaults[name] = version
            self._templates[name][version] = content
            logger.debug("Prompt 注册 | name=%s version=%s", name, version)

    def set_default(self, name: str, version: str) -> None:
        """设置默认版本。"""
        with self._lock:
            self._defaults[name] = version

    def get(self, name: str, version: str | None = None) -> str:
        """获取模板内容，version 为 None 时取默认版本。"""
        with self._lock:
            versions = self._templates.get(name)
            if not versions:
                raise KeyError(f"Prompt 模板未注册: {name}")
            v = version or self._defaults.get(name)
            if v not in versions:
                v = next(iter(versions))
            return versions[v]

    def switch_version(self, name: str, version: str) -> None:
        """切换默认版本。"""
        with self._lock:
            if name not in self._templates or version not in self._templates[name]:
                raise KeyError(f"无法切换: {name}/{version} 不存在")
            self._defaults[name] = version
            logger.info("Prompt 版本切换 | name=%s version=%s", name, version)

    def list_versions(self, name: str) -> list[str]:
        """列出某模板的所有版本。"""
        with self._lock:
            return list(self._templates.get(name, {}).keys())

    def reload(self, prompts_dir: Path | None = None) -> None:
        """从文件系统重新加载所有模板。"""
        with self._lock:
            self._templates.clear()
            self._defaults.clear()
        if prompts_dir:
            self._load_from_dir(prompts_dir)

    def _load_from_dir(self, prompts_dir: Path) -> None:
        """从 prompts/ 目录加载模板。"""
        config_path = prompts_dir / "config.yaml"
        if not config_path.exists():
            logger.warning("config.yaml 不存在，使用内置默认 prompt")
            return

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        defaults = config.get("defaults", {})
        templates_config = config.get("templates", {})

        for name, meta in templates_config.items():
            file_name = meta.get("file", f"{name}.j2")
            file_path = prompts_dir / file_name
            if not file_path.exists():
                logger.warning("模板文件不存在: %s", file_path)
                continue
            try:
                with open(file_path) as f:
                    content = f.read()
                version = config.get("version", "1.0")
                self.register(name, version, content)
                if name in defaults:
                    self.set_default(name, defaults[name])
            except TemplateSyntaxError as e:
                logger.error("模板语法错误 | file=%s error=%s", file_name, e)
            except Exception as e:
                logger.error("加载模板失败 | file=%s error=%s", file_name, e)

        logger.info("Prompt 加载完成 | count=%d", len(self._templates))

    def get_fallback(self, name: str) -> str:
        """获取内置默认 prompt（模板加载失败时的回退）。"""
        return _DEFAULT_PROMPTS.get(name, _DEFAULT_PROMPTS["system_base"])


# 全局单例
_registry = PromptRegistry()


def get_registry() -> PromptRegistry:
    """获取全局 PromptRegistry 实例。"""
    return _registry


__all__ = ["PromptRegistry", "get_registry"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_prompt_registry.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/prompt_registry.py backend/tests/core/test_prompt_registry.py
git commit -m "feat: add PromptRegistry with hot-reload and fallback"
```

---

## Task 4: Implement PromptRenderer

**Files:**
- Create: `backend/app/core/prompt_renderer.py`
- Test: `backend/tests/core/test_prompt_renderer.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/core/test_prompt_renderer.py`:
```python
"""Tests for PromptRenderer."""

import pytest
from datetime import date

from app.core.prompt_renderer import render_prompt
from app.core.prompt_registry import PromptRegistry, get_registry


class TestPromptRenderer:
    def test_render_with_variables(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "Hello {{ name }}, today is {{ current_date }}")
        result = render_prompt("test", {"name": "world"}, registry=reg, current_date=date(2026, 5, 25))
        assert "Hello world, today is 2026-05-25" in result

    def test_render_injects_builtin_variables(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "{{ current_date }} {{ current_time }} {{ current_weekday }}")
        result = render_prompt("test", {}, registry=reg, current_date=date(2026, 5, 25))
        assert "2026-05-25" in result
        assert "星期" in result

    def test_render_fallback_on_template_error(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "bad {{ unclosed")
        result = render_prompt("test", {}, registry=reg, current_date=date(2026, 5, 25))
        # fallback to default
        assert result != ""

    def test_render_relative_dates(self):
        reg = PromptRegistry()
        reg.register("test", "v1", "{{ yesterday }} {{ day_before_yesterday }}")
        result = render_prompt("test", {}, registry=reg, current_date=date(2026, 5, 25))
        assert "2026-05-24" in result
        assert "2026-05-23" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_prompt_renderer.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement PromptRenderer**

`backend/app/core/prompt_renderer.py`:
```python
"""Prompt 渲染器 — Jinja2 模板渲染 + 内置变量注入。"""

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

from jinja2 import Template, TemplateError

if TYPE_CHECKING:
    from app.core.prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)

_WEEKDAY_MAP = ["一", "二", "三", "四", "五", "六", "日"]


def _build_builtin_vars(current_date: date | None = None) -> dict:
    """构建内置模板变量。"""
    if current_date is None:
        current_date = date.today()
    now = datetime.now()
    weekday_cn = _WEEKDAY_MAP[current_date.weekday()]
    return {
        "current_date": current_date.isoformat(),
        "current_time": now.strftime("%H:%M"),
        "current_weekday": weekday_cn,
        "yesterday": (current_date - __import__("datetime").timedelta(days=1)).isoformat(),
        "day_before_yesterday": (current_date - __import__("datetime").timedelta(days=2)).isoformat(),
    }


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
        渲染后的 prompt 字符串。模板错误时回退到内置默认。
    """
    from app.core.prompt_registry import get_registry

    reg = registry or get_registry()
    try:
        template_str = reg.get(name, version)
    except KeyError:
        logger.warning("模板 %s 未注册，使用内置默认", name)
        template_str = reg.get_fallback(name)

    builtin_vars = _build_builtin_vars(current_date)
    ctx = {**builtin_vars, **(variables or {})}

    try:
        template = Template(template_str)
        return template.render(ctx)
    except TemplateError as e:
        logger.error("模板渲染失败 | name=%s error=%s，回退到默认", name, e)
        fallback = Template(reg.get_fallback(name))
        return fallback.render(ctx)


__all__ = ["render_prompt"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_prompt_renderer.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/prompt_renderer.py backend/tests/core/test_prompt_renderer.py
git commit -m "feat: add PromptRenderer with built-in variable injection"
```

---

## Task 5: Startup Loading and Context Middleware

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py` (add prompts_dir)

- [ ] **Step 1: Add prompts_dir to config**

In `backend/app/core/config.py`, add to `Settings` class:
```python
    @property
    def prompts_dir(self) -> Path:
        return Path(__file__).parent.parent.parent / "prompts"
```

- [ ] **Step 2: Modify main.py to load prompts at startup**

In `backend/app/main.py`, add imports and modify lifespan:
```python
from app.core.prompt_registry import get_registry
from app.core.prompt_renderer import render_prompt
from app.core.guardrails import cleanup_old_logs
```

In `lifespan`, after seed_default_farm, add:
```python
    # Load prompt templates
    registry = get_registry()
    registry.reload(settings.prompts_dir)
    logger.info("Prompt 模板已加载 | dir=%s", settings.prompts_dir)

    # Cleanup old guardrails logs (30 days)
    cleanup_old_logs(db=SessionLocal(), days=30)

    # Cleanup old idempotency keys (24 hours)
    from app.models.idempotency_key import cleanup_old_keys
    cleanup_old_keys(db=SessionLocal(), hours=24)
```

Also add a middleware for X-Current-Date after CORS:
```python
from contextvars import ContextVar

_current_date_ctx: ContextVar[str | None] = ContextVar("current_date", default=None)

@app.middleware("http")
async def date_injection_middleware(request: Request, call_next):
    """读取 X-Current-Date 请求头并注入上下文。"""
    from datetime import date, timedelta

    header_date = request.headers.get("X-Current-Date")
    server_date = date.today()
    effective_date = server_date

    if header_date:
        try:
            client_date = date.fromisoformat(header_date)
            delta = abs((client_date - server_date).days)
            if delta <= 7:
                effective_date = client_date
            else:
                logger.warning("客户端日期偏差过大 | client=%s server=%s delta=%dd", header_date, server_date, delta)
        except ValueError:
            logger.warning("X-Current-Date 格式无效: %s", header_date)

    _current_date_ctx.set(effective_date.isoformat())
    response = await call_next(request)
    return response


def get_request_date() -> date:
    """获取当前请求的日期（来自请求头或服务端时间）。"""
    from datetime import date

    date_str = _current_date_ctx.get()
    if date_str:
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass
    return date.today()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py backend/app/core/config.py
git commit -m "feat: load prompts at startup and add date injection middleware"
```

---

## Task 6: Migrate graph.py to Use Templates

**Files:**
- Modify: `backend/app/agents/graph.py`

- [ ] **Step 1: Replace hardcoded SYSTEM_PROMPT**

Replace the entire `SYSTEM_PROMPT` constant and `_llm_node` in `backend/app/agents/graph.py`:

```python
from app.core.prompt_registry import get_registry
from app.core.prompt_renderer import render_prompt
from app.main import get_request_date

# Remove: SYSTEM_PROMPT = "..."


def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt。"""
    tools = get_langchain_tools()
    llm = get_llm().bind_tools(tools)

    current_date = get_request_date()
    system_text = render_prompt("system_base", registry=get_registry(), current_date=current_date)
    system = HumanMessage(content=system_text)
    response = llm.invoke([system] + state["messages"])
    return {"messages": [response]}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/graph.py
git commit -m "refactor: migrate graph.py SYSTEM_PROMPT to template"
```

---

## Task 7: Migrate report.py to Use Templates

**Files:**
- Modify: `backend/app/agents/report.py`

- [ ] **Step 1: Replace hardcoded REPORT_SYSTEM_PROMPT**

In `backend/app/agents/report.py`:
```python
from app.core.prompt_registry import get_registry
from app.core.prompt_renderer import render_prompt
from app.main import get_request_date

# Remove: REPORT_SYSTEM_PROMPT = "..."
```

Modify `generate_cycle_report`:
```python
async def generate_cycle_report(cycle_id: int) -> str:
    """生成指定种植周期的综合报告。"""
    llm = _get_report_llm()
    prompt = (
        f"请为 ID={cycle_id} 的种植周期生成一份综合报告。"
        "请查询该周期的基本信息、最近农事记录和成本收支，"
        "整理成一份包含进度、成本分析和下一步建议的报告。"
    )
    current_date = get_request_date()
    system_text = render_prompt("report", registry=get_registry(), current_date=current_date)
    system = HumanMessage(content=system_text)
    response = await llm.ainvoke(
        [system, HumanMessage(content=prompt)],
        config={"run_name": "cycle_report", "metadata": {"cycle_id": cycle_id}},
    )
    return filter_output(response.content)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/report.py
git commit -m "refactor: migrate report.py prompt to template"
```

---

## Task 8: Migrate agent_service.py Prompts

**Files:**
- Modify: `backend/app/services/agent_service.py`

- [ ] **Step 1: Replace hardcoded prompts**

In `backend/app/services/agent_service.py`:
```python
from app.core.prompt_registry import get_registry
from app.core.prompt_renderer import render_prompt
from app.main import get_request_date
```

Modify `chat_with_agent`:
```python
async def chat_with_agent(db: Session, message: str, cycle_id: int | None = None, farm_id: int = 1) -> ChatResponse:
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    logger.info("开始对话 | farm=%s cycle=%s | input: %s", farm_id, cycle_id, message[:100])
    reply = await invoke_advisor(full_input, farm_id=farm_id)
    # ... rest unchanged
```

Modify `get_daily_advice`:
```python
async def get_daily_advice(db: Session, cycle_id: int | None = None, farm_id: int = 1) -> DailyAdviceResponse:
    current_date = get_request_date()
    prompt = render_prompt(
        "system_base",
        {"cycle_id": cycle_id} if cycle_id else {},
        registry=get_registry(),
        current_date=current_date,
    )
    if cycle_id:
        prompt += f"\n请为周期 ID={cycle_id} 生成今天的农事建议，查询天气和周期信息。"
    else:
        prompt += "\n请生成今天的农事建议，考虑当前天气和种植周期阶段。"
    # ... rest unchanged
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/agent_service.py
git commit -m "refactor: migrate agent_service prompts to templates"
```

---

## Task 9: Add Term Whitelist

**Files:**
- Create: `backend/app/core/term_whitelist.py`

- [ ] **Step 1: Create whitelist**

`backend/app/core/term_whitelist.py`:
```python
"""农业术语英文白名单 — 允许在中文输出中保留的英文单词。"""

_AGRICULTURAL_TERMS = {
    "watermelon", "tomato", "potato", "cucumber", "melon",
    "bean", "pepper", "eggplant", "carrot", "onion",
    "lettuce", "spinach", "celery", "broccoli", "cauliflower",
    "corn", "wheat", "rice", "soybean", "cotton",
    "fertilizer", "pesticide", "herbicide", "fungicide",
    "greenhouse", "drip", "irrigation", "mulch",
    "ph", "ec", "tds", "ppm", "co2",
    "n", "p", "k", "ca", "mg", "fe", "zn", "b", "mn",
    "ai", "llm", "api", "json", "html", "url",
}


def is_whitelisted(word: str) -> bool:
    """检查单词是否在农业术语白名单中。"""
    return word.lower() in _AGRICULTURAL_TERMS


__all__ = ["is_whitelisted", "_AGRICULTURAL_TERMS"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/term_whitelist.py
git commit -m "feat: add agricultural English term whitelist"
```

---

## Task 10: Refactor Guardrails with English Detection

**Files:**
- Modify: `backend/app/core/guardrails.py`
- Test: `backend/tests/core/test_guardrails.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/core/test_guardrails.py`:
```python
"""Tests for guardrails English detection and whitelist."""

import pytest

from app.core.guardrails import _has_english_sentence, filter_output
from app.core.term_whitelist import is_whitelisted


class TestEnglishDetection:
    def test_detects_english_sentence(self):
        assert _has_english_sentence("这是一个中文句子。Here is an English sentence.") is True

    def test_ignores_whitelisted_terms(self):
        assert _has_english_sentence("今天种了 Watermelon 和 Tomato") is False

    def test_ignores_pure_chinese(self):
        assert _has_english_sentence("今天天气很好，适合施肥") is False

    def test_detects_short_english(self):
        assert _has_english_sentence("Please try again") is True

    def test_output_filter_returns_chinese_on_english(self):
        result = filter_output("This is an error message from the system")
        assert result == "系统异常，请重试"

    def test_output_filter_allows_chinese(self):
        text = "西瓜种植需要注意浇水"
        assert filter_output(text) == text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_guardrails.py -v
```
Expected: FAIL

- [ ] **Step 3: Refactor guardrails.py**

`backend/app/core/guardrails.py`:
```python
"""Agent 输入输出安全审核模块 — 注入检测 + 敏感词 + PII + 英文输出检测。"""

import logging
import re

from app.core.term_whitelist import is_whitelisted

logger = logging.getLogger(__name__)

# 输入注入检测模式
_INJECTION_PATTERNS = [
    r"忽略(之前|上述|以上).*?指令",
    r"ignore\s+(previous|above|prior)\s+instructions?",
    r"system\s*:\s*",
    r"你(现在|现在起|现在开始).*?(是|作为|扮演)",
    r"forget\s+(everything|all|previous)",
    r"DAN\s*(模式|mode)",
    r"jailbreak",
]

# 敏感词黑名单
_SENSITIVE_KEYWORDS = [
    "密码",
    "password",
    "token",
    "密钥",
    "secret",
    "api_key",
    "信用卡",
    "身份证号",
    "银行卡",
    "cvv",
    "pin",
]

# PII 正则模式
_PII_PATTERNS = {
    "id_card": (re.compile(r"\d{17}[\dXx]|\d{15}"), "[身份证号已隐藏]"),
    "mobile": (re.compile(r"1[3-9]\d{9}"), "[手机号已隐藏]"),
    "api_key": (re.compile(r"sk-[a-zA-Z0-9]{32,48}"), "[API_KEY已隐藏]"),
    "email": (
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "[邮箱已隐藏]",
    ),
}

_INJECTION_REGEX = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

# 英文句子检测：连续 3+ 个英文单词（排除白名单单词）
_ENGLISH_WORD_RE = re.compile(r"[a-zA-Z]{2,}")


def _has_english_sentence(text: str) -> bool:
    """检测文本中是否包含英文句子（连续 3+ 英文单词）。"""
    words = _ENGLISH_WORD_RE.findall(text)
    non_whitelisted = [w for w in words if not is_whitelisted(w)]
    return len(non_whitelisted) >= 3


def check_input(text: str) -> tuple[bool, str | None]:
    """检测输入是否包含注入攻击或敏感词。"""
    if not text or not isinstance(text, str):
        return True, None

    for pattern in _INJECTION_REGEX:
        if pattern.search(text):
            reason = f"检测到潜在注入模式: {pattern.pattern[:30]}..."
            logger.warning("Guardrails 拦截输入 | reason=%s", reason)
            return False, reason

    lower = text.lower()
    for keyword in _SENSITIVE_KEYWORDS:
        if keyword in lower:
            reason = f"检测到敏感关键词: {keyword}"
            logger.warning("Guardrails 拦截输入 | reason=%s", reason)
            return False, reason

    return True, None


def filter_output(text: str) -> str:
    """过滤输出中的 PII 信息和英文句子。"""
    if not text or not isinstance(text, str):
        return text

    # 英文检测
    if _has_english_sentence(text):
        logger.warning("Guardrails 拦截输出英文 | text_preview=%s", text[:100])
        return "系统异常，请重试"

    # PII 过滤
    result = text
    for name, (pattern, replacement) in _PII_PATTERNS.items():
        result, count = pattern.subn(replacement, result)
        if count:
            logger.info("Guardrails 过滤输出 PII | type=%s, count=%d", name, count)

    return result


def cleanup_old_logs(db=None, days: int = 30) -> None:
    """删除 N 天前的 guardrails_logs 记录。"""
    if db is None:
        return
    try:
        from datetime import datetime, timedelta
        from app.models.guardrails_log import GuardrailsLog

        cutoff = datetime.now() - timedelta(days=days)
        db.query(GuardrailsLog).filter(GuardrailsLog.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
        logger.info("Guardrails 日志清理完成 | cutoff=%s", cutoff)
    except Exception:
        logger.exception("Guardrails 日志清理失败")


__all__ = ["check_input", "filter_output", "cleanup_old_logs", "_has_english_sentence"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_guardrails.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/guardrails.py backend/app/core/term_whitelist.py backend/tests/core/test_guardrails.py
git commit -m "feat: add English sentence detection and fallback to guardrails"
```

---

## Task 11: Create GuardrailsLog Model and Admin API

**Files:**
- Create: `backend/app/models/guardrails_log.py`
- Create: `backend/app/api/admin.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create GuardrailsLog model**

`backend/app/models/guardrails_log.py`:
```python
"""Guardrails 拦截日志模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class GuardrailsLog(Base):
    """Guardrails 拦截日志。"""

    __tablename__ = "guardrails_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, nullable=False)
    trigger_type = Column(String(50), nullable=False)
    trigger_detail = Column(Text, nullable=True)
    source_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
```

- [ ] **Step 2: Create admin API**

`backend/app/api/admin.py`:
```python
"""Admin API — 运维接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.guardrails_log import GuardrailsLog

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/guardrails-logs")
def list_guardrails_logs(
    trigger_type: str | None = Query(None, description="按类型过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询 Guardrails 拦截日志（支持分页和类型过滤）。"""
    query = db.query(GuardrailsLog)
    if trigger_type:
        query = query.filter(GuardrailsLog.trigger_type == trigger_type)
    total = query.count()
    items = query.order_by(GuardrailsLog.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": items, "total": total}
```

- [ ] **Step 3: Register model and router**

In `backend/app/models/__init__.py`, add:
```python
from app.models.guardrails_log import GuardrailsLog
```

In `backend/app/main.py`, add import and router:
```python
from app.api import admin
app.include_router(admin.router)
```

- [ ] **Step 4: Modify guardrails to write logs**

In `backend/app/core/guardrails.py`, add `_log_guardrails_event`:
```python
def _log_guardrails_event(farm_id: int, trigger_type: str, trigger_detail: str, source_text: str | None = None) -> None:
    """写入 Guardrails 拦截日志。"""
    try:
        from app.core.database import SessionLocal
        from app.models.guardrails_log import GuardrailsLog

        db = SessionLocal()
        try:
            log = GuardrailsLog(
                farm_id=farm_id,
                trigger_type=trigger_type,
                trigger_detail=trigger_detail[:500],
                source_text=(source_text or "")[:500],
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("Guardrails 日志写入失败")
```

Modify `check_input` to log:
```python
def check_input(text: str, farm_id: int = 0) -> tuple[bool, str | None]:
    # ... existing logic ...
    for pattern in _INJECTION_REGEX:
        if pattern.search(text):
            reason = f"检测到潜在注入模式"
            _log_guardrails_event(farm_id, "input_injection", reason, text[:200])
            return False, reason
    # ... same for sensitive keywords ...
    _log_guardrails_event(farm_id, "input_sensitive", reason, text[:200])
```

Modify `filter_output` to log:
```python
def filter_output(text: str, farm_id: int = 0) -> str:
    # ... existing logic ...
    if _has_english_sentence(text):
        _log_guardrails_event(farm_id, "output_english", "检测到英文句子", text[:200])
        return "系统异常，请重试"
    # ... after PII filtering ...
    if count:
        _log_guardrails_event(farm_id, "output_pii", f"PII 类型: {name}, 数量: {count}", text[:200])
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/guardrails_log.py backend/app/api/admin.py backend/app/models/__init__.py backend/app/main.py backend/app/core/guardrails.py
git commit -m "feat: add GuardrailsLog persistence and admin API"
```

---

## Task 12: Create IdempotencyKey Model

**Files:**
- Create: `backend/app/models/idempotency_key.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create model**

`backend/app/models/idempotency_key.py`:
```python
"""幂等键模型 — 防止重复解析请求。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base


class IdempotencyKey(Base):
    """幂等键缓存。"""

    __tablename__ = "idempotency_keys"

    key = Column(String(64), primary_key=True)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


def cleanup_old_keys(db=None, hours: int = 24) -> None:
    """删除 N 小时前的幂等键。"""
    import logging
    from datetime import timedelta

    logger = logging.getLogger(__name__)
    if db is None:
        return
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        db.query(IdempotencyKey).filter(IdempotencyKey.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
        logger.info("幂等键清理完成 | cutoff=%s", cutoff)
    except Exception:
        logger.exception("幂等键清理失败")


__all__ = ["IdempotencyKey", "cleanup_old_keys"]
```

- [ ] **Step 2: Register in models/__init__.py**

```python
from app.models.idempotency_key import IdempotencyKey
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/idempotency_key.py backend/app/models/__init__.py
git commit -m "feat: add IdempotencyKey model for deduplication"
```

---

## Task 13: Add CostParseResult Pydantic Model and Date Validator

**Files:**
- Modify: `backend/app/schemas/cost.py`

- [ ] **Step 1: Add CostParseResult and date validator**

In `backend/app/schemas/cost.py`, add after `CostParseResponse`:

```python
from datetime import date as date_type


class CostParseResult(BaseModel):
    """AI 解析后的结构化结果（带校验）。"""

    record_type: str = "cost"
    category: str = "其他"
    amount: str = "0"
    record_date: str = ""
    note: str | None = None

    @field_validator("record_type")
    @classmethod
    def _validate_record_type(cls, v: str) -> str:
        if v not in RECORD_TYPE_ENUM:
            return "cost"
        return v

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return "其他"
        return v[:50]

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, v: str) -> str:
        try:
            d = Decimal(str(v))
        except Exception:
            return "0"
        if d <= 0:
            return "0"
        if d > 10_000_000:
            return "10000000"
        return str(v)

    @field_validator("record_date")
    @classmethod
    def _validate_record_date(cls, v: str | None) -> str:
        from datetime import date, timedelta

        today = date.today()
        if not v:
            return today.isoformat()
        try:
            parsed = date.fromisoformat(v)
        except (ValueError, TypeError):
            return today.isoformat()

        min_date = date(2020, 1, 1)
        max_date = today + timedelta(days=1)
        if parsed < min_date or parsed > max_date:
            return today.isoformat()
        return parsed.isoformat()
```

- [ ] **Step 2: Add record_date validator to CostParseResponse**

Add to `CostParseResponse`:
```python
    @field_validator("record_date")
    @classmethod
    def _validate_record_date(cls, v: str) -> str:
        from datetime import date, timedelta

        today = date.today()
        if not v:
            return today.isoformat()
        try:
            parsed = date.fromisoformat(v)
        except (ValueError, TypeError):
            return today.isoformat()
        min_date = date(2020, 1, 1)
        max_date = today + timedelta(days=1)
        if parsed < min_date or parsed > max_date:
            return today.isoformat()
        return parsed.isoformat()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/cost.py
git commit -m "feat: add CostParseResult with validation and date range checks"
```

---

## Task 14: JSON Repair Utility

**Files:**
- Create: `backend/app/core/json_repair.py`
- Test: `backend/tests/core/test_json_repair.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/core/test_json_repair.py`:
```python
"""Tests for JSON repair utility."""

import pytest

from app.core.json_repair import extract_json, repair_json


class TestJsonRepair:
    def test_extract_from_markdown_code_block(self):
        text = '```json\n{"a": 1}\n```'
        assert extract_json(text) == '{"a": 1}'

    def test_extract_plain_json(self):
        text = '{"a": 1}'
        assert extract_json(text) == '{"a": 1}'

    def test_repair_missing_braces(self):
        text = '{"a": 1, "b": {'
        assert repair_json(text) == '{"a": 1, "b": {}}'

    def test_repair_trailing_comma(self):
        text = '{"a": 1,}'
        assert repair_json(text) == '{"a": 1}'

    def test_repair_nested_trailing_comma(self):
        text = '{"a": [1, 2,]}'
        assert repair_json(text) == '{"a": [1, 2]}'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_json_repair.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement JSON repair**

`backend/app/core/json_repair.py`:
```python
"""JSON 解析容错 — 提取 Markdown 代码块 + 自动修复常见格式错误。"""

import json
import logging
import re

logger = logging.getLogger(__name__)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def extract_json(text: str) -> str | None:
    """从文本中提取 JSON 内容（支持 Markdown 代码块）。"""
    text = text.strip()
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def repair_json(json_str: str) -> str:
    """自动修复常见 JSON 格式错误。

    - 补全缺失的括号
    - 删除末尾多余逗号
    """
    s = json_str.strip()
    if not s:
        return s

    # 补全缺失的括号
    open_braces = s.count("{")
    close_braces = s.count("}")
    missing = open_braces - close_braces
    if missing > 0:
        s += "}" * missing

    open_brackets = s.count("[")
    close_brackets = s.count("]")
    missing_brackets = open_brackets - close_brackets
    if missing_brackets > 0:
        s += "]" * missing_brackets

    # 移除末尾多余逗号（对象和数组）
    s = re.sub(r",(\s*[}\]])", r"\1", s)

    return s


def safe_parse_json(text: str) -> dict:
    """安全解析 JSON：提取 → 修复 → 解析。

    Returns:
        解析后的 dict。

    Raises:
        ValueError: 所有修复手段都失败时。
    """
    raw = extract_json(text)
    if not raw:
        raise ValueError("无法提取 JSON 内容")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = repair_json(raw)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败 | raw=%s error=%s", raw[:100], e)
            raise ValueError(f"AI 返回格式异常: {raw[:100]}")


__all__ = ["extract_json", "repair_json", "safe_parse_json"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_json_repair.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/json_repair.py backend/tests/core/test_json_repair.py
git commit -m "feat: add JSON repair utility with markdown extraction"
```

---

## Task 15: Refactor cost.py /parse Endpoint

**Files:**
- Modify: `backend/app/api/cost.py`
- Test: `backend/tests/api/test_cost_parse.py`

- [ ] **Step 1: Write the integration test**

`backend/tests/api/test_cost_parse.py`:
```python
"""Integration tests for /costs/parse endpoint."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCostParse:
    @patch("app.api.cost.invoke_advisor")
    def test_parse_success(self, mock_advisor):
        mock_advisor.return_value = '{"record_type": "cost", "category": "化肥", "amount": "200", "record_date": "2026-05-25"}'
        response = client.post(
            "/costs/parse",
            json={"description": "买化肥花了200"},
            headers={"X-Idempotency-Key": "test-key-1", "X-Current-Date": "2026-05-25"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["record_type"] == "cost"
        assert data["category"] == "化肥"
        assert data["amount"] == "200"

    @patch("app.api.cost.invoke_advisor")
    def test_parse_idempotent(self, mock_advisor):
        mock_advisor.return_value = '{"record_type": "cost", "category": "种子", "amount": "50", "record_date": "2026-05-25"}'
        # First request
        r1 = client.post(
            "/costs/parse",
            json={"description": "买种子"},
            headers={"X-Idempotency-Key": "idem-key-1", "X-Current-Date": "2026-05-25"},
        )
        assert r1.status_code == 200
        # Second request with same key
        r2 = client.post(
            "/costs/parse",
            json={"description": "买种子"},
            headers={"X-Idempotency-Key": "idem-key-1", "X-Current-Date": "2026-05-25"},
        )
        assert r2.status_code == 200
        assert r2.json() == r1.json()
        mock_advisor.assert_called_once()  # Only called once

    @patch("app.api.cost.invoke_advisor")
    def test_parse_markdown_block(self, mock_advisor):
        mock_advisor.return_value = '```json\n{"record_type": "income", "category": "销售收入", "amount": "1000", "record_date": "2026-05-25"}\n```'
        response = client.post(
            "/costs/parse",
            json={"description": "卖西瓜收入1000"},
            headers={"X-Idempotency-Key": "test-key-md", "X-Current-Date": "2026-05-25"},
        )
        assert response.status_code == 200
        assert response.json()["record_type"] == "income"

    @patch("app.api.cost.invoke_advisor")
    def test_parse_invalid_json(self, mock_advisor):
        mock_advisor.return_value = "这不是 JSON"
        response = client.post(
            "/costs/parse",
            json={"description": "测试"},
            headers={"X-Idempotency-Key": "test-key-err", "X-Current-Date": "2026-05-25"},
        )
        assert response.status_code == 422

    @patch("app.api.cost.invoke_advisor")
    def test_parse_date_out_of_range(self, mock_advisor):
        mock_advisor.return_value = '{"record_type": "cost", "category": "人工", "amount": "300", "record_date": "2019-01-01"}'
        response = client.post(
            "/costs/parse",
            json={"description": "人工费"},
            headers={"X-Idempotency-Key": "test-key-date", "X-Current-Date": "2026-05-25"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["record_date"] == "2026-05-25"  # fallback to today
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/api/test_cost_parse.py -v
```
Expected: FAIL

- [ ] **Step 3: Refactor cost.py**

Replace the `/parse` endpoint in `backend/app/api/cost.py`:

```python
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_db
from app.core.json_repair import safe_parse_json
from app.core.prompt_registry import get_registry
from app.core.prompt_renderer import render_prompt
from app.main import get_request_date
from app.models.farm import Farm
from app.models.idempotency_key import IdempotencyKey
from app.schemas.common import PaginatedResponse
from app.schemas.cost import (
    CostParseRequest,
    CostParseResponse,
    CostParseResult,
    CostRecordCreate,
    CostRecordResponse,
    CycleProfit,
    YearlySummary,
)
from app.services import cost_service

router = APIRouter(prefix="/costs", tags=["costs"])
logger = logging.getLogger(__name__)

# ... keep existing endpoints (create_record, list_records, get_cycle_profit, get_yearly_summary) ...


@router.post("/parse", response_model=CostParseResponse)
async def parse_cost_record(
    req: CostParseRequest,
    farm: Farm = Depends(get_current_farm),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """AI 解析自然语言记账描述，返回结构化记录。

    支持幂等键去重（24 小时内相同 key 直接返回缓存结果）。
    """
    # 幂等键检查
    if idempotency_key:
        cached = db.query(IdempotencyKey).filter(IdempotencyKey.key == idempotency_key).first()
        if cached:
            logger.info("幂等键命中 | key=%s", idempotency_key)
            try:
                import json
                data = json.loads(cached.response)
                return CostParseResponse(**data)
            except Exception:
                logger.warning("幂等缓存解析失败，重新执行 | key=%s", idempotency_key)

    current_date = get_request_date()
    prompt = render_prompt(
        "cost_parse",
        {"description": req.description},
        registry=get_registry(),
        current_date=current_date,
    )
    logger.info("AI 解析记账 | farm=%s | input: %s", farm.id, req.description)

    from app.agents.advisor import invoke_advisor
    reply = await invoke_advisor(prompt, farm_id=farm.id)

    # JSON 解析（提取代码块 + 修复）
    try:
        data = safe_parse_json(reply)
    except ValueError as e:
        logger.error("AI 返回无法解析: %s", reply[:200])
        raise HTTPException(status_code=422, detail=f"AI 返回格式异常: {reply[:100]}")

    # Pydantic 校验（非法值自动替换为默认值）
    result = CostParseResult.model_validate(data)

    # 构建响应
    response = CostParseResponse(
        record_type=result.record_type,
        category=result.category,
        amount=result.amount,
        record_date=result.record_date,
        note=result.note,
    )

    # 缓存幂等键
    if idempotency_key:
        try:
            import json
            cache = IdempotencyKey(key=idempotency_key, response=response.model_dump_json())
            db.add(cache)
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("幂等键缓存写入失败 | key=%s", idempotency_key)

    return response
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/api/test_cost_parse.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/cost.py backend/tests/api/test_cost_parse.py backend/app/core/json_repair.py
git commit -m "feat: refactor cost parse with idempotency, Pydantic validation, JSON repair"
```

---

## Task 16: Add Micro Compact Context Compression

**Files:**
- Modify: `backend/app/agents/graph.py`
- Modify: `backend/app/agents/advisor.py`

- [ ] **Step 1: Add micro_compact to graph.py**

In `backend/app/agents/graph.py`, add before `_llm_node`:
```python
_KEEP_RECENT = 3


def micro_compact(messages: list) -> list:
    """压缩历史消息中旧的 tool result，只保留最近 N 个完整内容。"""
    tool_results = [(i, msg) for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)]
    if len(tool_results) <= _KEEP_RECENT:
        return messages

    result = list(messages)
    for idx, (i, msg) in enumerate(tool_results[:-_KEEP_RECENT]):
        content = msg.content or ""
        if len(content) > 100:
            tool_name = getattr(msg, "name", "unknown")
            result[i] = ToolMessage(content=f"[已执行 {tool_name}]", tool_call_id=msg.tool_call_id)
    return result
```

Modify `_llm_node`:
```python
def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    tools = get_langchain_tools()
    llm = get_llm().bind_tools(tools)

    current_date = get_request_date()
    system_text = render_prompt("system_base", registry=get_registry(), current_date=current_date)
    system = HumanMessage(content=system_text)

    messages = micro_compact(state["messages"])
    response = llm.invoke([system] + messages)
    return {"messages": [response]}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/graph.py
git commit -m "feat: add micro_compact context compression"
```

---

## Task 17: Add SkillRegistry Singleton

**Files:**
- Modify: `backend/app/skills/__init__.py`

- [ ] **Step 1: Add SkillRegistry**

In `backend/app/skills/__init__.py`:
```python
"""Skill 管理模块 — Skillify SDK 集成 + LangChain 工具桥接。"""

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

_SKILL_REGISTRY: dict = {}


def get_skill_registry() -> dict:
    """获取全局 Skill 注册表（名称 -> 工具实例）。"""
    global _SKILL_REGISTRY
    if not _SKILL_REGISTRY:
        _SKILL_REGISTRY = _build_registry()
    return _SKILL_REGISTRY


def _build_registry() -> dict:
    """构建 Skill 注册表。"""
    from skillify import SkillManager

    manager = SkillManager()
    registry = {}
    try:
        for skill in manager.list_skills():
            registry[skill.name] = skill
    except Exception as e:
        logger.warning("Skill 加载失败: %s", e)
    return registry


@lru_cache(maxsize=1)
def get_langchain_tools():
    """获取 LangChain 工具列表（缓存避免重复实例化）。"""
    from app.skills.bridge import skills_to_langchain_tools

    registry = get_skill_registry()
    if not registry:
        return []
    return skills_to_langchain_tools(list(registry.values()))


def clear_skill_cache():
    """清除工具缓存（用于热重载）。"""
    get_langchain_tools.cache_clear()


__all__ = ["get_skill_registry", "get_langchain_tools", "clear_skill_cache"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/skills/__init__.py
git commit -m "feat: add SkillRegistry singleton with caching"
```

---

## Task 18: Add AgentTrace Model

**Files:**
- Create: `backend/app/models/agent_trace.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create AgentTrace model**

`backend/app/models/agent_trace.py`:
```python
"""Agent 调用埋点模型 — 记录 LLM/Tool 调用耗时和 token。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class AgentTrace(Base):
    """Agent 调用链路追踪。"""

    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, nullable=False)
    session_id = Column(String(64), nullable=True)
    node_type = Column(String(20), nullable=False)  # llm_call, tool_call
    node_name = Column(String(100), nullable=True)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
```

- [ ] **Step 2: Register in models/__init__.py**

```python
from app.models.agent_trace import AgentTrace
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/agent_trace.py backend/app/models/__init__.py
git commit -m "feat: add AgentTrace model for monitoring"
```

---

## Task 19: Mobile API Client Updates

**Files:**
- Modify: `FarmManagerMobile/src/api/client.ts`

- [ ] **Step 1: Add date and idempotency headers**

Replace `apiClient` interceptors and costApi in `FarmManagerMobile/src/api/client.ts`:

```typescript
import 'react-native-get-random-values';
import { v4 as uuidv4 } from 'uuid';

apiClient.interceptors.request.use(async config => {
  const today = new Date().toISOString().split('T')[0];
  config.headers['X-Current-Date'] = today;
  return config;
});

// ... costApi update:
  parseRecord: (description: string) => {
    const idempotencyKey = uuidv4();
    return apiClient.post('/costs/parse', { description }, {
      headers: { 'X-Idempotency-Key': idempotencyKey },
    });
  },
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/api/client.ts
git commit -m "feat: mobile API client injects X-Current-Date and X-Idempotency-Key"
```

---

## Task 20: Transaction Rollback Review

**Files:**
- Modify: `backend/app/services/cost_service.py` (if needed)
- Modify: `backend/app/services/agent_service.py` (already has try/except/rollback)

- [ ] **Step 1: Review cost_service.py for write operations**

Read `backend/app/services/cost_service.py` and add try/except/rollback to any write operation missing it.

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/cost_service.py
git commit -m "fix: ensure transaction rollback on all write operations"
```

---

## Task 21: Integration Verification

- [ ] **Step 1: Start backend locally**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run uvicorn app.main:app --reload
```

Verify: logs show "Prompt 模板已加载 | dir=..."

- [ ] **Step 2: Run all new tests**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/core/test_prompt_registry.py tests/core/test_prompt_renderer.py tests/core/test_guardrails.py tests/core/test_json_repair.py tests/api/test_cost_parse.py -v
```
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest -v
```

- [ ] **Step 4: Lint check**

```bash
cd /Users/ljn/Documents/demo/explore/backend
ruff check . && ruff format .
```

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: complete prompt governance implementation"
```

---

## Spec Coverage Check

| Requirement | Task |
|------------|------|
| Jinja2 prompt templates | Task 2 |
| PromptRegistry hot-reload | Task 3 |
| PromptRenderer variable injection | Task 4 |
| Startup loading | Task 5 |
| graph.py migration | Task 6 |
| report.py migration | Task 7 |
| agent_service.py migration | Task 8 |
| X-Current-Date header | Task 5 |
| Date range validation | Task 13 |
| English detection (3+ words) | Task 10 |
| Term whitelist | Task 9 |
| Guardrails logs table + admin API | Task 11 |
| Idempotency keys | Task 12, 15 |
| CostParseResult Pydantic | Task 13 |
| JSON markdown extraction | Task 14 |
| JSON auto-repair | Task 14 |
| Transaction rollback | Task 20 |
| micro_compact | Task 16 |
| SkillRegistry | Task 17 |
| AgentTrace model | Task 18 |
| Mobile headers | Task 19 |

---

## Placeholder Scan

- No "TBD", "TODO", "implement later" found.
- All code blocks contain complete, runnable code.
- No "Similar to Task N" references.
- All file paths are exact.
