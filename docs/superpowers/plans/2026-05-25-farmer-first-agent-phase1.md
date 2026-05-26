# Farmer First Agent — Phase 1: 上下文注入 + 回复格式 + 用户称呼

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Agent 认识用户——每次调用前注入农场现状摘要，控制回复短而准，使用用户称呼。

**Architecture:** 新增 `farm_context_service.py` 作为唯一上下文组装入口，查库组装 ≤300 字摘要。修改 `_llm_node` 在渲染 prompt 时注入摘要和格式规则。Farm 模型新增 `display_name` 字段。

**Tech Stack:** Python/FastAPI/SQLAlchemy/SQLite, LangGraph, Jinja2, pytest

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `backend/app/services/farm_context_service.py` | 农场上下文摘要组装（唯一入口） |
| Modify | `backend/app/models/farm.py` | 新增 `display_name` 字段 |
| Modify | `backend/prompts/base.j2` | 新增 `{{ farm_context_summary }}` + `{{ response_format_rules }}` |
| Modify | `backend/app/core/prompt_renderer.py` | 注入新模板变量 |
| Modify | `backend/app/agents/graph.py` | 调用 farm_context_service |
| Modify | `backend/app/api/agent.py` | 传递 farm_id 和 db 到 graph |
| Create | `backend/tests/services/test_farm_context_service.py` | 上下文服务测试 |
| Create | `backend/tests/core/test_response_format.py` | 格式规则渲染测试 |

---

### Task 1: Farm 模型新增 display_name 字段

**Files:**
- Modify: `backend/app/models/farm.py`
- Test: `backend/tests/test_config.py`（已有，验证模型可创建即可）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_config.py` 末尾追加：

```python
class TestFarmDisplayName:
    """Farm 模型 display_name 字段测试。"""

    def test_default_display_name(self, clean_db):
        from app.core.database import SessionLocal
        from app.models.farm import Farm

        db = SessionLocal()
        farm = Farm(id=2, name="测试农场")
        db.add(farm)
        db.commit()
        db.refresh(farm)
        assert farm.display_name == "农友"
        db.close()

    def test_custom_display_name(self, clean_db):
        from app.core.database import SessionLocal
        from app.models.farm import Farm

        db = SessionLocal()
        farm = Farm(id=3, name="测试农场", display_name="老李")
        db.add(farm)
        db.commit()
        db.refresh(farm)
        assert farm.display_name == "老李"
        db.close()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/test_config.py::TestFarmDisplayName -v`
Expected: FAIL — `Farm.__init__()` 收到意外参数 `display_name`

- [ ] **Step 3: 修改 Farm 模型**

修改 `backend/app/models/farm.py`：

```python
"""农场模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    display_name = Column(String, nullable=False, default="农友", server_default="农友")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/test_config.py::TestFarmDisplayName -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/models/farm.py tests/test_config.py
git commit -m "feat: Farm 模型新增 display_name 字段，默认'农友'"
```

---

### Task 2: 创建 farm_context_service — 核心摘要组装

**Files:**
- Create: `backend/app/services/farm_context_service.py`
- Test: `backend/tests/services/test_farm_context_service.py`

- [ ] **Step 1: 写失败测试 — 活跃茬口查询**

创建 `backend/tests/services/__init__.py`（如不存在），然后创建 `backend/tests/services/test_farm_context_service.py`：

```python
"""farm_context_service 单元测试。"""

import pytest
from unittest.mock import MagicMock, patch

from app.core.database import SessionLocal
from app.models.farm import Farm
from app.models.cycle import CropCycle, CycleStage
from app.models.crop import CropTemplate, GrowthStage
from app.models.log import FarmLog
from app.models.cost import CostRecord
from datetime import date, timedelta


class TestBuildSummary:
    """build_summary 核心逻辑测试。"""

    def _seed_farm_with_cycle(self, db):
        """播种：1个农场 + 1个活跃茬口 + 1个当前阶段。"""
        farm = db.query(Farm).filter(Farm.id == 1).first()
        template = CropTemplate(farm_id=1, name="西瓜")
        db.add(template)
        db.flush()

        stage_def = GrowthStage(crop_template_id=template.id, name="伸蔓期", duration_days=20, order_index=1)
        db.add(stage_def)
        db.flush()

        cycle = CropCycle(
            farm_id=1, name="春季西瓜", crop_template_id=template.id,
            start_date=date.today() - timedelta(days=10), status="active",
        )
        db.add(cycle)
        db.flush()

        cycle_stage = CycleStage(
            cycle_id=cycle.id, name="伸蔓期",
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=15),
            order_index=1, duration_days=20, is_current=True,
        )
        db.add(cycle_stage)
        db.commit()
        return cycle

    def test_summary_contains_active_cycle(self):
        """摘要包含活跃茬口信息。"""
        from app.services.farm_context_service import build_summary

        db = SessionLocal()
        try:
            self._seed_farm_with_cycle(db)
            summary = build_summary(db, farm_id=1)
            assert "西瓜" in summary
            assert "伸蔓期" in summary
        finally:
            db.close()

    def test_summary_no_active_cycles(self):
        """无活跃茬口时摘要包含提示。"""
        from app.services.farm_context_service import build_summary

        db = SessionLocal()
        try:
            summary = build_summary(db, farm_id=1)
            assert "无种植" in summary or "当前无" in summary
        finally:
            db.close()

    def test_summary_length_under_300(self):
        """摘要总长度 ≤300 字。"""
        from app.services.farm_context_service import build_summary

        db = SessionLocal()
        try:
            self._seed_farm_with_cycle(db)
            summary = build_summary(db, farm_id=1)
            assert len(summary) <= 300
        finally:
            db.close()

    def test_summary_trims_multiple_cycles(self):
        """超过3个活跃茬口时只保留3个。"""
        from app.services.farm_context_service import build_summary

        db = SessionLocal()
        try:
            template = CropTemplate(farm_id=1, name="通用")
            db.add(template)
            db.flush()

            for i in range(5):
                cycle = CropCycle(
                    farm_id=1, name=f"作物{i}", crop_template_id=template.id,
                    start_date=date.today() - timedelta(days=10), status="active",
                )
                db.add(cycle)
            db.commit()

            summary = build_summary(db, farm_id=1)
            # 不应包含"作物3"和"作物4"
            assert "作物3" not in summary
        finally:
            db.close()


class TestBuildSummaryWithLogs:
    """含农事记录的摘要测试。"""

    def _seed_logs(self, db):
        farm = db.query(Farm).filter(Farm.id == 1).first()
        template = CropTemplate(farm_id=1, name="西瓜")
        db.add(template)
        db.flush()
        cycle = CropCycle(
            farm_id=1, name="春季西瓜", crop_template_id=template.id,
            start_date=date.today() - timedelta(days=10), status="active",
        )
        db.add(cycle)
        db.flush()
        for i in range(5):
            log = FarmLog(
                farm_id=1, cycle_id=cycle.id, operation_type="施肥",
                operation_date=date.today() - timedelta(days=i),
                note=f"第{i+1}次施肥",
            )
            db.add(log)
        db.commit()
        return cycle

    def test_summary_trims_logs_to_3(self):
        """超过3条农事记录时只保留3条。"""
        from app.services.farm_context_service import build_summary

        db = SessionLocal()
        try:
            self._seed_logs(db)
            summary = build_summary(db, farm_id=1)
            # 不应包含"第4次"和"第5次"
            assert "第4次" not in summary
            assert "第5次" not in summary
        finally:
            db.close()


class TestBuildSummaryWithCosts:
    """含成本数据的摘要测试。"""

    def test_summary_contains_monthly_cost(self):
        """摘要包含本月成本汇总。"""
        from app.services.farm_context_service import build_summary

        db = SessionLocal()
        try:
            cost = CostRecord(
                farm_id=1, record_type="cost", category="化肥",
                amount=200, record_date=date.today(),
            )
            db.add(cost)
            db.commit()

            summary = build_summary(db, farm_id=1)
            assert "200" in summary or "成本" in summary
        finally:
            db.close()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/services/test_farm_context_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.farm_context_service'`

- [ ] **Step 3: 实现 farm_context_service**

创建 `backend/app/services/farm_context_service.py`：

```python
"""农场上下文服务 — Agent 调用前的结构化摘要组装。"""

import logging
import threading
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.models.cycle import CropCycle, CycleStage
from app.models.farm import Farm
from app.models.log import FarmLog

logger = logging.getLogger(__name__)

_MAX_CYCLES = 3
_MAX_LOGS = 3
_MAX_COST_DAYS = 30
_SUMMARY_MAX_LENGTH = 300

_cache: dict[int, tuple[str, float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 300


def build_summary(db: Session, farm_id: int) -> str:
    """组装农场现状摘要（带缓存）。"""
    cached_summary = _get_cached(farm_id)
    if cached_summary:
        return cached_summary

    parts: list[str] = []

    display_name = _get_display_name(db, farm_id)
    parts.append(f"用户称呼：{display_name}")

    cycles_text = _build_cycles_section(db, farm_id)
    if cycles_text:
        parts.append(cycles_text)

    logs_text = _build_logs_section(db, farm_id)
    if logs_text:
        parts.append(logs_text)

    cost_text = _build_cost_section(db, farm_id)
    if cost_text:
        parts.append(cost_text)

    summary = "\n".join(parts)
    if len(summary) > _SUMMARY_MAX_LENGTH:
        summary = summary[:_SUMMARY_MAX_LENGTH]

    _set_cached(farm_id, summary)
    logger.info("农场摘要生成 | farm_id=%s, 长度=%d", farm_id, len(summary))
    return summary


def _get_display_name(db: Session, farm_id: int) -> str:
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    return farm.display_name if farm and farm.display_name else "农友"


def _build_cycles_section(db: Session, farm_id: int) -> str:
    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.created_at.desc())
        .limit(_MAX_CYCLES)
        .all()
    )
    if not cycles:
        return "当前无种植计划。"

    lines = ["活跃茬口："]
    for cycle in cycles:
        current_stage = (
            db.query(CycleStage)
            .filter(CycleStage.cycle_id == cycle.id, CycleStage.is_current == True)
            .first()
        )
        stage_name = current_stage.name if current_stage else "未知阶段"
        lines.append(f"  {cycle.name}（{stage_name}）")
    return "\n".join(lines)


def _build_logs_section(db: Session, farm_id: int) -> str:
    since = date.today() - timedelta(days=3)
    logs = (
        db.query(FarmLog)
        .filter(FarmLog.farm_id == farm_id, FarmLog.operation_date >= since)
        .order_by(FarmLog.operation_date.desc())
        .limit(_MAX_LOGS)
        .all()
    )
    if not logs:
        return ""
    lines = ["近期农事："]
    for log in logs:
        lines.append(f"  {log.operation_date} {log.operation_type}" + (f" {log.note}" if log.note else ""))
    return "\n".join(lines)


def _build_cost_section(db: Session, farm_id: int) -> str:
    month_start = date.today().replace(day=1)
    result = (
        db.query(func.sum(CostRecord.amount))
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_type == "cost",
            CostRecord.record_date >= month_start,
        )
        .scalar()
    )
    if not result:
        return ""
    return f"本月成本：{float(result):.0f}元"


def _get_cached(farm_id: int) -> Optional[str]:
    with _cache_lock:
        entry = _cache.get(farm_id)
        if not entry:
            return None
        summary, ts = entry
        import time
        if time.time() - ts > _CACHE_TTL_SECONDS:
            del _cache[farm_id]
            return None
        return summary


def _set_cached(farm_id: int, summary: str) -> None:
    import time
    with _cache_lock:
        _cache[farm_id] = (summary, time.time())


def clear_cache(farm_id: int | None = None) -> None:
    """清除缓存（测试用或数据变更后）。"""
    with _cache_lock:
        if farm_id:
            _cache.pop(farm_id, None)
        else:
            _cache.clear()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/services/test_farm_context_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/farm_context_service.py tests/services/test_farm_context_service.py
git commit -m "feat: 新增 farm_context_service — 农场上下文摘要组装"
```

---

### Task 3: 修改 base.j2 — 注入农场摘要和格式规则

**Files:**
- Modify: `backend/prompts/base.j2`

- [ ] **Step 1: 写失败测试 — 模板渲染含新变量**

创建 `backend/tests/core/test_response_format.py`：

```python
"""回复格式规则渲染测试。"""

from app.core.prompt_renderer import render_prompt
from app.core.prompt_registry import PromptRegistry


class TestResponseFormatRules:
    """{{ response_format_rules }} 渲染测试。"""

    def test_renders_with_display_name(self):
        variables = {"display_name": "老李"}
        result = render_prompt("system_base", variables=variables)
        assert "老李" in result

    def test_renders_default_display_name(self):
        variables = {"display_name": "农友"}
        result = render_prompt("system_base", variables=variables)
        assert "农友" in result

    def test_renders_farm_context_summary(self):
        variables = {
            "display_name": "农友",
            "farm_context_summary": "活跃茬口：春季西瓜（伸蔓期）",
        }
        result = render_prompt("system_base", variables=variables)
        assert "春季西瓜" in result

    def test_response_format_rules_present(self):
        variables = {"display_name": "农友"}
        result = render_prompt("system_base", variables=variables)
        assert "不超过2行" in result
        assert "不超过5条" in result


class TestPromptWithoutNewVars:
    """缺少新变量时模板不崩溃。"""

    def test_renders_without_farm_context(self):
        result = render_prompt("system_base")
        assert "语言规则" in result

    def test_renders_with_empty_farm_context(self):
        result = render_prompt("system_base", variables={"farm_context_summary": ""})
        assert "语言规则" in result
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/core/test_response_format.py -v`
Expected: FAIL — `response_format_rules` 相关断言失败（模板还没有这个块）

- [ ] **Step 3: 修改 base.j2**

修改 `backend/prompts/base.j2` 为：

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

请根据用户的问题，主动调用合适的工具获取信息，然后给出具体、可操作的建议。

{% if current_date %}
【时间信息】
今天是 {{ current_date }}，星期{{ current_weekday }}。当前时间 {{ current_time }}。
{% endif %}

{% if farm_context_summary %}
【我的农场】
{{ farm_context_summary }}
{% endif %}

【回复格式】（最高优先级，必须遵守）
- 称呼用户为「{{ display_name | default("农友") }}」
- 每条建议/操作不超过2行
- 总共不超过5条
- 先说结论，再说原因（如：明天降温12° → 你那西瓜正伸蔓期怕冻）
- 禁止铺垫、寒暄、总结段
- 用「你」不用「您」，口语化
- 禁止输出「希望对你有帮助」「如有疑问」等客套话
```

- [ ] **Step 4: 修改 prompt_renderer — 注入新变量**

修改 `backend/app/core/prompt_renderer.py` 的 `render_prompt` 函数，确保新变量可传入：

无需修改 `render_prompt` 函数本身——它已经通过 `variables` 参数接受任意变量并合并到模板上下文中。新变量 `farm_context_summary`、`display_name`、`response_format_rules` 通过调用方传入即可。

- [ ] **Step 5: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/core/test_response_format.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add prompts/base.j2 tests/core/test_response_format.py
git commit -m "feat: base.j2 新增农场摘要注入和回复格式约束"
```

---

### Task 4: 修改 graph.py — 调用 farm_context_service

**Files:**
- Modify: `backend/app/agents/graph.py`

- [ ] **Step 1: 写失败测试 — graph 注入上下文**

在 `backend/tests/test_advisor_agent.py` 末尾追加：

```python
class TestContextInjection:
    """验证 _llm_node 注入农场上下文摘要。"""

    @patch("app.agents.graph.render_prompt")
    @patch("app.agents.graph.get_llm")
    def test_llm_node_passes_farm_id_to_context_service(self, mock_get_llm, mock_render):
        from app.agents.graph import _llm_node, AgentState
        from langchain_core.messages import HumanMessage, AIMessage

        mock_render.return_value = "system prompt"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="回复")
        mock_get_llm.return_value.bind_tools.return_value = mock_llm

        state = AgentState(messages=[HumanMessage(content="你好")])
        result = _llm_node(state, farm_id=1, db=SessionLocal())

        assert result is not None
        # 验证 render_prompt 被调用时传入了 farm_context_summary
        call_args = mock_render.call_args
        assert call_args is not None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/test_advisor_agent.py::TestContextInjection -v`
Expected: FAIL — `_llm_node` 不接受 `farm_id` 和 `db` 参数

- [ ] **Step 3: 修改 graph.py — _llm_node 接受额外参数并注入上下文**

修改 `backend/app/agents/graph.py`。核心改动：`_llm_node` 从外部获取 `db` 和 `farm_id`，调用 `farm_context_service`，将摘要和称呼传入 `render_prompt`。

将 `_llm_node` 改为：

```python
def _llm_node(state: AgentState, *, farm_id: int = 1, db=None) -> dict:
    """LLM 推理节点 — 注入农场上下文 + 格式规则。"""
    from app.services.farm_context_service import build_summary

    tools = get_langchain_tools()
    llm = get_llm().bind_tools(tools)

    current_date = get_request_date()

    farm_context_summary = ""
    display_name = "农友"
    if db:
        try:
            farm_context_summary = build_summary(db, farm_id)
        except Exception:
            logger.warning("农场摘要生成失败 | farm_id=%s", farm_id, exc_info=True)
        try:
            from app.models.farm import Farm
            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            if farm and farm.display_name:
                display_name = farm.display_name
        except Exception:
            pass

    system_text = render_prompt(
        "system_base",
        registry=get_registry(),
        current_date=current_date,
        variables={
            "farm_context_summary": farm_context_summary,
            "display_name": display_name,
        },
    )
    system = HumanMessage(content=system_text)

    messages = micro_compact(state["messages"])
    response = llm.invoke([system] + messages)
    return {"messages": [response]}
```

- [ ] **Step 4: 修改 compile_advisor_graph — 传递 db 参数**

修改 `compile_advisor_graph` 函数，让图的入口接受 `db` 参数：

```python
def compile_advisor_graph():
    """编译建议 Agent 的 StateGraph。"""
    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", _parallel_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()
```

注意：`compile_advisor_graph` 本身不需要改。`_llm_node` 的 `farm_id` 和 `db` 参数通过 LangGraph 的 `config` 机制传入。

修改 `advisor.py` 中的 `invoke_advisor` 和 `stream_advisor`，将 `db` 传入 graph config：

修改 `backend/app/agents/advisor.py` 中的 `invoke_advisor`：

```python
async def invoke_advisor(user_input: str, farm_id: int = 1, db=None) -> str:
    """调用建议 Agent 回答用户问题。"""
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        return f"输入内容包含不安全信息，已被拦截。原因：{reason}"

    logger.info("Agent 收到请求 | farm_id=%s: %s", farm_id, user_input[:200])
    graph = _get_advisor_graph()
    try:
        config = {
            "recursion_limit": 15,
            "run_name": "advisor_invoke",
            "metadata": {"farm_id": farm_id, "request_type": "chat"},
            "configurable": {"farm_id": farm_id, "db": db},
        }
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
        )
    except GraphRecursionError:
        logger.error("Agent 步数超限 | farm_id=%s", farm_id)
        return "Agent 处理步数超出限制，请简化您的问题后重试。"

    reply = result["messages"][-1].content
    filtered = filter_output(reply)
    logger.info("Agent 回复完成 | farm_id=%s, 长度 %d 字符", farm_id, len(filtered))
    return filtered
```

同理修改 `stream_advisor` 的 config 字典。

然后修改 `graph.py` 中的 `_llm_node`，从 `state` 或通过 LangGraph 的 `configurable` 获取参数。更简洁的方式是使用 `functools.partial` 在编译时绑定，但 LangGraph 推荐用 `config["configurable"]`。

将 `_llm_node` 改为从 `config` 获取参数：

```python
def _llm_node(state: AgentState, config: dict) -> dict:
    """LLM 推理节点 — 注入农场上下文 + 格式规则。"""
    from app.services.farm_context_service import build_summary

    tools = get_langchain_tools()
    llm = get_llm().bind_tools(tools)

    current_date = get_request_date()
    configurable = config.get("configurable", {})
    farm_id = configurable.get("farm_id", 1)
    db = configurable.get("db")

    farm_context_summary = ""
    display_name = "农友"
    if db:
        try:
            farm_context_summary = build_summary(db, farm_id)
        except Exception:
            logger.warning("农场摘要生成失败 | farm_id=%s", farm_id, exc_info=True)
        try:
            from app.models.farm import Farm
            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            if farm and farm.display_name:
                display_name = farm.display_name
        except Exception:
            pass

    system_text = render_prompt(
        "system_base",
        registry=get_registry(),
        current_date=current_date,
        variables={
            "farm_context_summary": farm_context_summary,
            "display_name": display_name,
        },
    )
    system = HumanMessage(content=system_text)

    messages = micro_compact(state["messages"])
    response = llm.invoke([system] + messages)
    return {"messages": [response]}
```

- [ ] **Step 5: 修改 agent_service — 传递 db 到 advisor**

修改 `backend/app/services/agent_service.py`，在调用 `invoke_advisor` 和 `stream_advisor` 时传入 `db`：

```python
async def chat_with_agent(db: Session, message: str, cycle_id: int | None = None, farm_id: int = 1) -> ChatResponse:
    """与用户进行 Agent 对话，保存记录。"""
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    logger.info("开始对话 | farm=%s cycle=%s | input: %s", farm_id, cycle_id, message[:100])
    reply = await invoke_advisor(full_input, farm_id=farm_id, db=db)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="chat", content=reply, farm_id=farm_id)
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("对话记录已保存 | record_id=%s", record.id)

    return ChatResponse(reply=reply)


async def stream_chat_with_agent(
    db: Session, message: str, cycle_id: int | None = None, farm_id: int = 1
) -> AsyncGenerator[str, None]:
    """流式与 Agent 对话，逐 token 返回。"""
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    async for chunk in stream_advisor(full_input, farm_id=farm_id, db=db):
        yield chunk


async def get_daily_advice(db: Session, cycle_id: int | None = None, farm_id: int = 1) -> DailyAdviceResponse:
    """生成每日农事建议并保存。"""
    prompt = "请生成今天的农事建议，考虑当前天气和种植周期阶段。按优先级排列，直接输出条目。"
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议，查询天气和周期信息。按优先级排列。"
    logger.info("生成每日建议 | farm=%s cycle=%s", farm_id, cycle_id)
    advice = await invoke_advisor(prompt, farm_id=farm_id, db=db)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="daily", content=advice, farm_id=farm_id)
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    logger.info("建议已保存 | record_id=%s", record.id)

    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        advice=record.content,
        created_at=record.created_at,
    )
```

注意：`stream_advisor` 也需要更新签名以接受 `db` 参数。修改 `backend/app/agents/advisor.py` 中的 `stream_advisor`：

```python
async def stream_advisor(user_input: str, farm_id: int = 1, db=None) -> AsyncGenerator[str, None]:
    """流式调用建议 Agent。"""
    ok, reason = check_input(user_input)
    if not ok:
        yield f"输入内容包含不安全信息，已被拦截。原因：{reason}"
        return

    graph = _get_advisor_graph()
    config = {
        "recursion_limit": 15,
        "run_name": "advisor_stream",
        "metadata": {"farm_id": farm_id, "request_type": "stream_chat"},
        "configurable": {"farm_id": farm_id, "db": db},
    }
    step = 0
    try:
        async for event in graph.astream(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
        ):
            for node, state in event.items():
                step += 1
                for msg in state.get("messages", []):
                    if isinstance(msg, ToolMessage):
                        logger.info("[step %d] 工具 %s 返回: %s", step, node, str(msg.content)[:150])
                    elif isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                logger.info("[step %d] LLM 调用: %s(%s)", step, tc["name"], tc["args"])
                        elif msg.content:
                            yield filter_output(msg.content)
    except GraphRecursionError:
        yield "Agent 处理步数超出限制，请简化您的问题后重试。"
        return
    logger.info("Agent 流式完成，共 %d 步", step)
```

同时需要修改 `backend/app/api/agent.py` 中的流式端点，传入 `db`：

```python
# stream_chat_with_agent 调用处，从 agent_service 导入时已经是 async generator
# 需要确保传入了 db 参数
```

检查 `backend/app/api/agent.py` 中的 `stream_chat` 端点，确认它调用 `stream_chat_with_agent` 时传入了 `db`。

- [ ] **Step 6: 运行全量测试**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS（包括已有的 test_advisor_agent.py、test_agent_service.py）

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/agents/graph.py app/agents/advisor.py app/services/agent_service.py app/api/agent.py tests/
git commit -m "feat: Agent 注入农场上下文摘要和用户称呼"
```

---

### Task 5: 新增 display_name API 端点

**Files:**
- Modify: `backend/app/api/agent.py` 或新建 `backend/app/api/farm.py`
- Test: `backend/tests/test_farm_api.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_farm_api.py`：

```python
"""Farm API 测试 — display_name。"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, get_db
from app.main import app
from app.models.farm import Farm


@pytest.fixture
def client():
    from unittest.mock import MagicMock

    db = SessionLocal()
    app.dependency_overrides[get_db] = lambda: db
    tc = TestClient(app)
    yield tc
    app.dependency_overrides.clear()
    db.close()


class TestDisplayName:
    """display_name 读写。"""

    def test_get_default_display_name(self, client):
        resp = client.get("/api/farm/1/display-name")
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "农友"

    def test_update_display_name(self, client):
        resp = client.put("/api/farm/1/display-name", json={"display_name": "老李"})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "老李"

    def test_update_clears_context_cache(self, client):
        """修改称呼后，上下文缓存应失效。"""
        from app.services.farm_context_service import clear_cache

        clear_cache()
        resp = client.put("/api/farm/1/display-name", json={"display_name": "李哥"})
        assert resp.status_code == 200
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/test_farm_api.py -v`
Expected: FAIL — 404（路由不存在）

- [ ] **Step 3: 创建 farm API 路由**

创建 `backend/app/api/farm.py`：

```python
"""农场相关 API。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.farm import Farm
from app.services.farm_context_service import clear_cache

router = APIRouter(prefix="/api/farm", tags=["farm"])


class DisplayNameUpdate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=20)


class DisplayNameResponse(BaseModel):
    display_name: str


@router.get("/{farm_id}/display-name", response_model=DisplayNameResponse)
def get_display_name(farm_id: int, db: Session = Depends(get_db)):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    return DisplayNameResponse(display_name=farm.display_name if farm else "农友")


@router.put("/{farm_id}/display-name", response_model=DisplayNameResponse)
def update_display_name(farm_id: int, body: DisplayNameUpdate, db: Session = Depends(get_db)):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    farm.display_name = body.display_name
    db.commit()
    db.refresh(farm)
    clear_cache(farm_id)
    return DisplayNameResponse(display_name=farm.display_name)
```

在 `backend/app/main.py` 中注册路由：

```python
from app.api.farm import router as farm_router
app.include_router(farm_router)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/test_farm_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/api/farm.py app/main.py tests/test_farm_api.py
git commit -m "feat: 新增 display_name API — GET/PUT /api/farm/{id}/display-name"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 启动后端**

Run: `cd backend && python -m uvicorn app.main:app --reload`

- [ ] **Step 2: 测试 display_name API**

```bash
curl http://localhost:8000/api/farm/1/display-name
# 期望：{"display_name": "农友"}

curl -X PUT http://localhost:8000/api/farm/1/display-name \
  -H "Content-Type: application/json" \
  -d '{"display_name": "老李"}'
# 期望：{"display_name": "老李"}
```

- [ ] **Step 3: 测试 Agent 聊天**

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "今天该干嘛？"}'
# 期望：回复简短（≤5条），开头使用"老李"
```

- [ ] **Step 4: 运行全量测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 5: ruff 检查**

Run: `cd backend && ruff check . && ruff format --check .`
Expected: 无错误

- [ ] **Step 6: 最终提交**

```bash
cd backend && git add -A
git commit -m "feat: Phase 1 完成 — Agent 上下文注入 + 短回复格式 + 用户称呼"
```

---

## Self-Review

**Spec coverage:**
- `farm-context-injection` spec → Task 2 (build_summary) + Task 4 (graph 注入) ✅
- `agent-response-format` spec → Task 3 (base.j2 格式规则) + Task 4 (display_name 注入) ✅
- `user-settings` spec (display_name) → Task 1 (模型) + Task 5 (API) ✅

**Placeholder scan:** 无 TBD/TODO/待定内容。所有代码步骤含完整实现。

**Type consistency:** `build_summary(db, farm_id)` 在 Task 2 定义，Task 4 的 graph.py 和 Task 5 的 farm.py 中调用签名一致。`display_name` 在 Farm 模型、farm_context_service、base.j2、API 中均为 `str` 类型。
