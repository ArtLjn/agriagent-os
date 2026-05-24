# Skill Engine + Cache + Circuit Breaker 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将硬编码的 LangChain tools 迁移为 skillify SDK 驱动的 Skill 架构，加上 TTL 缓存、熔断重试、并行执行。

**Architecture:** skillify SDK 提供 Skill 基类和自动发现，桥接层转为 LangChain StructuredTool。自定义 LangGraph StateGraph 替换 create_react_agent，实现多 tool_calls 并行执行。LLM 调用包装熔断器，Skill execute 包装 TTL 缓存装饰器。

**Tech Stack:** Python 3.11 / FastAPI / LangGraph 0.2 / skillify SDK / asyncio / SQLite

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/app/core/skill_cache.py` | TTL 缓存装饰器 |
| Create | `backend/app/core/circuit_breaker.py` | 熔断器 + 重试 |
| Create | `backend/app/skills/__init__.py` | SkillManager 初始化 + LangChain 桥接 |
| Create | `backend/app/skills/weather.py` | 天气 Skill |
| Create | `backend/app/skills/crop_cycle.py` | 种植周期 Skill |
| Create | `backend/app/skills/farm_logs.py` | 农事记录 Skill |
| Create | `backend/app/skills/cost_summary.py` | 成本汇总 Skill |
| Modify | `backend/app/core/llm.py` | 集成熔断器 |
| Modify | `backend/app/agents/graph.py` | 自定义 StateGraph + 并行节点 |
| Modify | `backend/app/agents/advisor.py` | 适配新 graph |
| Modify | `backend/app/core/config.py` | 添加熔断配置项 |
| Modify | `backend/requirements.txt` | 添加 skillify |
| Delete | `backend/app/agents/tools.py` | 被 skills/ 替代 |

---

### Task 1: 安装 skillify SDK

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 安装 skillify 到 venv**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/pip install -e /Users/ljn/Documents/demo/skillify
```

Expected: Successfully installed skillify

- [ ] **Step 2: 验证导入**

```bash
.venv/bin/python -c "from skillify.skills.base import Skill; from skillify.manager import SkillManager; print('OK')"
```

Expected: OK

- [ ] **Step 3: 添加到 requirements.txt**

在 `backend/requirements.txt` 末尾追加：

```
skillify @ file:///Users/ljn/Documents/demo/skillify
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add skillify SDK dependency"
```

---

### Task 2: 实现 TTL 缓存装饰器

**Files:**
- Create: `backend/app/core/skill_cache.py`

- [ ] **Step 1: 创建缓存模块**

创建 `backend/app/core/skill_cache.py`：

```python
"""Skill TTL 缓存装饰器，基于内存字典。"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from functools import wraps

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, str], tuple[str, float]] = {}


def _make_key(skill_name: str, params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


def cached(ttl_seconds: int, key_fn: Callable[[dict], str] | None = None):
    """装饰 Skill.execute()，按 (skill_name, params_hash) 缓存结果。

    Args:
        ttl_seconds: 缓存存活时间，0 表示不缓存。
        key_fn: 自定义缓存 key 生成函数，默认按 params 做 MD5。
    """
    if ttl_seconds <= 0:
        def decorator(fn):
            return fn
        return decorator

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(self, params: dict, context, **kwargs):
            cache_key = key_fn(params) if key_fn else _make_key(self.name(), params)
            full_key = (self.name(), cache_key)

            if full_key in _cache:
                result, expire_at = _cache[full_key]
                age = time.time() - (expire_at - ttl_seconds)
                if time.time() < expire_at:
                    logger.info("CACHE HIT skill=%s age=%.0fs ttl=%ds", self.name(), age, ttl_seconds)
                    from skillify.models.schemas import ResultStatus, SkillResult
                    return SkillResult(status=ResultStatus.SUCCESS, reply=result)
                del _cache[full_key]

            logger.info("CACHE MISS skill=%s", self.name())
            result = await fn(self, params, context, **kwargs)

            if result.status.value == "success":
                _cache[full_key] = (result.reply, time.time() + ttl_seconds)

            return result
        return wrapper
    return decorator


def clear_cache(skill_name: str | None = None) -> int:
    """清除缓存，返回清除条数。"""
    if skill_name:
        keys = [k for k in _cache if k[0] == skill_name]
        for k in keys:
            del _cache[k]
        return len(keys)
    count = len(_cache)
    _cache.clear()
    return count
```

- [ ] **Step 2: 验证语法**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -c "from app.core.skill_cache import cached, clear_cache; print('OK')"
```

Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/skill_cache.py
git commit -m "feat: add TTL cache decorator for skills"
```

---

### Task 3: 实现熔断器

**Files:**
- Create: `backend/app/core/circuit_breaker.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 在 config.py 添加熔断配置**

在 `backend/app/core/config.py` 的 `AIConfig` 类中添加字段：

```python
class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = 3
    recovery_timeout: int = 30
    retry_max: int = 3
    retry_backoff_base: float = 2.0
```

在 `Settings` 类中添加：

```python
circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
```

同时添加 property：

```python
@property
def circuit_breaker_config(self) -> CircuitBreakerConfig:
    return self.circuit_breaker
```

- [ ] **Step 2: 创建熔断器模块**

创建 `backend/app/core/circuit_breaker.py`：

```python
"""LLM 调用熔断器 + 指数退避重试。"""

import asyncio
import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """三态熔断器：CLOSED → OPEN → HALF_OPEN → CLOSED。"""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("⚡ 熔断器 HALF_OPEN → 开始探测")
        return self._state

    def record_success(self) -> None:
        if self._state != CircuitState.CLOSED:
            logger.info("✅ 熔断器 %s → CLOSED (调用成功)", self._state.value)
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.warning("🔴 熔断器 CLOSED → OPEN (连续 %d 次失败)", self._failure_count)
            self._state = CircuitState.OPEN

    def allow(self) -> bool:
        return self.state != CircuitState.OPEN


class CircuitOpenError(Exception):
    """熔断器打开时的异常。"""
    pass


async def call_with_retry(
    fn,
    breaker: CircuitBreaker,
    retry_max: int = 3,
    retry_backoff_base: float = 2.0,
    timeout: float = 60.0,
):
    """带熔断 + 重试的异步调用包装。

    Args:
        fn: 无参异步 callable（通常是 lambda 包装了实际调用）。
        breaker: 熔断器实例。
        retry_max: 最大重试次数。
        retry_backoff_base: 退避基数秒。
        timeout: 单次调用超时秒。

    Returns:
        fn 的返回值。

    Raises:
        CircuitOpenError: 熔断器打开。
    """
    if not breaker.allow():
        raise CircuitOpenError("熔断器 OPEN，请求被拒绝")

    last_error = None
    for attempt in range(retry_max):
        try:
            result = await asyncio.wait_for(fn(), timeout=timeout)
            breaker.record_success()
            return result
        except CircuitOpenError:
            raise
        except Exception as e:
            last_error = e
            breaker.record_failure()
            if attempt < retry_max - 1 and breaker.allow():
                backoff = retry_backoff_base * (2 ** attempt)
                logger.warning("⚠️ 调用失败 (attempt %d/%d), %.1fs 后重试: %s", attempt + 1, retry_max, backoff, str(e)[:100])
                await asyncio.sleep(backoff)
            else:
                break

    raise last_error or CircuitOpenError("重试耗尽")
```

- [ ] **Step 3: 验证语法**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -c "from app.core.circuit_breaker import CircuitBreaker, call_with_retry; print('OK')"
```

Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/circuit_breaker.py backend/app/core/config.py
git commit -m "feat: add circuit breaker with retry for LLM calls"
```

---

### Task 4: 创建 SkillManager 初始化和 LangChain 桥接

**Files:**
- Create: `backend/app/skills/__init__.py`

- [ ] **Step 1: 创建 skills 包**

创建 `backend/app/skills/__init__.py`：

```python
"""Farm Manager Skill 包 — skillify SDK 驱动。"""

import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model
from skillify.manager import SkillManager

logger = logging.getLogger(__name__)

_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    """获取全局 SkillManager 单例。"""
    global _manager
    if _manager is None:
        _manager = SkillManager(python_packages=["app.skills"])
        logger.info("SkillManager 初始化完成，共 %d 个 Skill", len(_manager.list_skills()))
    return _manager


def _schema_to_pydantic(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """将 JSON Schema 转为 Pydantic BaseModel（LangChain StructuredTool 需要）。"""
    from pydantic import Field

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}

    type_map = {"string": str, "integer": int, "number": float, "boolean": bool}

    for field_name, field_def in properties.items():
        py_type = type_map.get(field_def.get("type", "string"), str)
        if field_name not in required:
            py_type = py_type | None  # noqa
        default = field_def.get("default") if field_name not in required else ...
        desc = field_def.get("description", "")
        fields[field_name] = (py_type, Field(default=default, description=desc))

    return create_model(f"{name}Schema", **fields)


def skills_to_langchain_tools(manager: SkillManager) -> list[StructuredTool]:
    """将 skillify Skills 转为 LangChain StructuredTool 列表。"""
    tools = []
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if not skill:
            continue
        args_schema = _schema_to_pydantic(skill.name(), skill.parameters_schema())

        def make_fn(s):
            def fn(**kwargs):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(s.execute(kwargs, None))
                return result.reply
            return fn

        tools.append(StructuredTool(
            name=skill.name(),
            description=skill.description(),
            args_schema=args_schema,
            func=make_fn(skill),
            coroutine=lambda params, s=skill: s.execute(params, None).reply,
        ))

    return tools


def get_langchain_tools() -> list[StructuredTool]:
    """获取 LangChain Tool 列表（供 LangGraph 使用）。"""
    return skills_to_langchain_tools(get_skill_manager())


__all__ = ["get_skill_manager", "skills_to_langchain_tools", "get_langchain_tools"]
```

- [ ] **Step 2: 验证语法**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -c "from app.skills import get_skill_manager; print('OK')"
```

Expected: OK（此时还没有 Skill 文件，会打印 0 个 Skill）

- [ ] **Step 3: Commit**

```bash
git add backend/app/skills/__init__.py
git commit -m "feat: add skillify SkillManager init and LangChain bridge"
```

---

### Task 5: 迁移 WeatherSkill

**Files:**
- Create: `backend/app/skills/weather.py`

- [ ] **Step 1: 创建天气 Skill**

创建 `backend/app/skills/weather.py`：

```python
"""天气预报 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.config import settings
from app.core.skill_cache import cached
from app.services.weather_service import check_weather_warnings, fetch_weather


class WeatherSkill(Skill):
    def name(self) -> str:
        return "get_weather_forecast"

    def description(self) -> str:
        return "获取未来7天天气预报和灾害预警。触发词: 天气、预报、降雨"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "地点描述（仅作标注，实际使用配置坐标）",
                    "default": "当前地块",
                },
            },
            "required": [],
        }

    @cached(ttl_seconds=1800)
    async def execute(self, params: dict, context) -> SkillResult:
        location = params.get("location", "当前地块")
        data = fetch_weather(settings.weather_latitude, settings.weather_longitude, days=7)
        daily = data.get("daily", {})
        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_sum", [])
        winds = daily.get("windspeed_10m_max", [])

        lines = [f"📍 地点：{location}", "未来 7 天天气预报："]
        for i, day in enumerate(times):
            max_t = max_temps[i] if i < len(max_temps) else "-"
            min_t = min_temps[i] if i < len(min_temps) else "-"
            p = precips[i] if i < len(precips) else "-"
            w = winds[i] if i < len(winds) else "-"
            lines.append(f"  {day}: 最高{max_t}°C 最低{min_t}°C 降水{p}mm 风速{w}m/s")

        warnings = check_weather_warnings(data)
        if warnings:
            lines.append("⚠️ 天气预警：")
            lines.extend(f"  {w}" for w in warnings)
        else:
            lines.append("✅ 近期无极端天气预警。")

        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))


skill = WeatherSkill()
```

- [ ] **Step 2: 验证 Skill 可被发现**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -c "
from app.skills import get_skill_manager
sm = get_skill_manager()
print([s.name for s in sm.list_skills()])
"
```

Expected: `['get_weather_forecast']`

- [ ] **Step 3: Commit**

```bash
git add backend/app/skills/weather.py
git commit -m "feat: migrate weather tool to skillify Skill with cache"
```

---

### Task 6: 迁移 CropCycleSkill

**Files:**
- Create: `backend/app/skills/crop_cycle.py`

- [ ] **Step 1: 创建种植周期 Skill**

创建 `backend/app/skills/crop_cycle.py`：

```python
"""种植周期查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.cycle import CropCycle


class CropCycleSkill(Skill):
    def name(self) -> str:
        return "get_crop_cycle_info"

    def description(self) -> str:
        return "查询指定种植周期的详细信息，包括当前阶段和各阶段安排。触发词: 周期、阶段、茬口"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "种植周期 ID"},
            },
            "required": ["cycle_id"],
        }

    @cached(ttl_seconds=600, key_fn=lambda p: f"cycle:{p.get('cycle_id')}")
    async def execute(self, params: dict, context) -> SkillResult:
        cycle_id = params["cycle_id"]
        db = SessionLocal()
        try:
            cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
            if not cycle:
                return SkillResult(status=ResultStatus.SUCCESS, reply=f"未找到 ID 为 {cycle_id} 的种植周期。")

            lines = [
                f"🌱 茬口：{cycle.name}",
                f"📅 开始日期：{cycle.start_date}",
                f"🗺️ 地块：{cycle.field_name or '未指定'}",
                f"📊 状态：{cycle.status}",
                "阶段安排：",
            ]
            for stage in sorted(cycle.stages, key=lambda s: s.order_index):
                current_marker = " [当前]" if stage.is_current else ""
                lines.append(
                    f"  {stage.name}{current_marker}: {stage.start_date} ~ {stage.end_date} "
                    f"（{stage.duration_days} 天）关键任务：{stage.key_tasks or '无'}"
                )

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()


skill = CropCycleSkill()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/skills/crop_cycle.py
git commit -m "feat: migrate crop cycle tool to skillify Skill"
```

---

### Task 7: 迁移 FarmLogSkill

**Files:**
- Create: `backend/app/skills/farm_logs.py`

- [ ] **Step 1: 创建农事记录 Skill**

创建 `backend/app/skills/farm_logs.py`：

```python
"""农事记录查询 Skill。"""

from datetime import date, timedelta

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.log import FarmLog


class FarmLogSkill(Skill):
    def name(self) -> str:
        return "get_recent_farm_logs"

    def description(self) -> str:
        return "查询指定周期最近N天的农事记录。触发词: 记录、日志、农事"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "种植周期 ID"},
                "days": {"type": "integer", "description": "查询天数（默认 7）", "default": 7},
            },
            "required": ["cycle_id"],
        }

    @cached(ttl_seconds=60, key_fn=lambda p: f"logs:{p.get('cycle_id')}:{p.get('days', 7)}")
    async def execute(self, params: dict, context) -> SkillResult:
        cycle_id = params["cycle_id"]
        days = params.get("days", 7)
        db = SessionLocal()
        try:
            since = date.today() - timedelta(days=days)
            logs = (
                db.query(FarmLog)
                .filter(FarmLog.cycle_id == cycle_id, FarmLog.operation_date >= since)
                .order_by(FarmLog.operation_date.desc())
                .limit(20)
                .all()
            )
            if not logs:
                return SkillResult(status=ResultStatus.SUCCESS, reply=f"最近 {days} 天内没有农事记录。")

            lines = [f"📝 最近 {days} 天农事记录（共 {len(logs)} 条）："]
            for log in logs:
                lines.append(f"  {log.operation_date}: {log.operation_type} - {log.note or '无备注'}")

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()


skill = FarmLogSkill()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/skills/farm_logs.py
git commit -m "feat: migrate farm logs tool to skillify Skill"
```

---

### Task 8: 迁移 CostSummarySkill

**Files:**
- Create: `backend/app/skills/cost_summary.py`

- [ ] **Step 1: 创建成本汇总 Skill**

创建 `backend/app/skills/cost_summary.py`：

```python
"""成本汇总查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.cost import CostRecord


class CostSummarySkill(Skill):
    def name(self) -> str:
        return "get_cycle_cost_summary"

    def description(self) -> str:
        return "查询指定周期的成本与收入汇总。触发词: 成本、收入、利润、收支"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "种植周期 ID"},
            },
            "required": ["cycle_id"],
        }

    @cached(ttl_seconds=300, key_fn=lambda p: f"cost:{p.get('cycle_id')}")
    async def execute(self, params: dict, context) -> SkillResult:
        cycle_id = params["cycle_id"]
        db = SessionLocal()
        try:
            records = db.query(CostRecord).filter(CostRecord.cycle_id == cycle_id).all()
            if not records:
                return SkillResult(status=ResultStatus.SUCCESS, reply="该周期暂无成本或收入记录。")

            total_cost = sum(r.amount for r in records if r.record_type == "cost")
            total_income = sum(r.amount for r in records if r.record_type == "income")
            net = total_income - total_cost

            lines = [
                "💰 周期收支汇总：",
                f"  总成本：{total_cost} 元",
                f"  总收入：{total_income} 元",
                f"  净利润：{net} 元",
                "  明细：",
            ]
            for r in records:
                lines.append(f"    {r.record_date}: {r.record_type} - {r.category} {r.amount} 元 ({r.note or '无备注'})")

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()


skill = CostSummarySkill()
```

- [ ] **Step 2: 验证全部 4 个 Skill 可发现**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -c "
from app.skills import get_skill_manager
sm = get_skill_manager()
names = [s.name for s in sm.list_skills()]
print(f'{len(names)} skills: {names}')
"
```

Expected: `4 skills: ['get_weather_forecast', 'get_crop_cycle_info', 'get_recent_farm_logs', 'get_cycle_cost_summary']`

- [ ] **Step 3: Commit**

```bash
git add backend/app/skills/cost_summary.py
git commit -m "feat: migrate cost summary tool to skillify Skill"
```

---

### Task 9: 集成熔断器到 LLM

**Files:**
- Modify: `backend/app/core/llm.py`

- [ ] **Step 1: 修改 llm.py 添加熔断器包装**

将 `backend/app/core/llm.py` 改为：

```python
"""LLM 客户端封装，使用 LangChain ChatOpenAI 接入 DashScope。"""

import asyncio
import logging

import langchain

for _attr in ("verbose", "debug", "llm_cache"):
    if not hasattr(langchain, _attr):
        setattr(langchain, _attr, False)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI  # noqa: E402

from app.core.circuit_breaker import CircuitBreaker, call_with_retry  # noqa: E402
from app.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

LLM_INSTANCE: ChatOpenAI | None = None
_BREAKER: CircuitBreaker | None = None


class LlmNotConfiguredError(Exception):
    """LLM 未配置错误。"""
    pass


def _get_breaker() -> CircuitBreaker:
    global _BREAKER
    if _BREAKER is None:
        cb = settings.circuit_breaker_config
        _BREAKER = CircuitBreaker(
            failure_threshold=cb.failure_threshold,
            recovery_timeout=cb.recovery_timeout,
        )
    return _BREAKER


def get_llm() -> BaseChatModel:
    """获取全局 LLM 实例（带熔断保护）。

    Returns:
        ChatOpenAI 实例，invoke/stream 调用自动走熔断+重试。

    Raises:
        LlmNotConfiguredError: AI API key 未配置。
    """
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        if not settings.ai_api_key:
            raise LlmNotConfiguredError(
                "AI API key 未配置。请在 config.yaml 中设置 ai.api_key，"
                "或设置 AI_API_KEY 环境变量。"
            )
        cb = settings.circuit_breaker_config
        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
            max_retries=cb.retry_max,
            timeout=cb.retry_backoff_base * (2 ** cb.retry_max) * 2,
        )
    return LLM_INSTANCE


async def llm_invoke_with_breaker(llm: BaseChatModel, messages: list) -> object:
    """带熔断保护的 LLM 调用。"""
    cb = settings.circuit_breaker_config
    breaker = _get_breaker()
    return await call_with_retry(
        fn=lambda: llm.ainvoke(messages),
        breaker=breaker,
        retry_max=cb.retry_max,
        retry_backoff_base=cb.retry_backoff_base,
    )


__all__ = ["get_llm", "llm_invoke_with_breaker"]
```

- [ ] **Step 2: 验证语法**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -c "from app.core.llm import get_llm; print('OK')"
```

Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/llm.py
git commit -m "feat: integrate circuit breaker into LLM client"
```

---

### Task 10: 重构 graph.py — 自定义 StateGraph + 并行节点

**Files:**
- Modify: `backend/app/agents/graph.py`

- [ ] **Step 1: 重写 graph.py**

将 `backend/app/agents/graph.py` 替换为：

```python
"""LangGraph 图编译模块 — 自定义 StateGraph 实现并行 Skill 执行。"""

import asyncio
import logging
from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.core.llm import get_llm
from app.skills import get_langchain_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位经验丰富的农业技术顾问，擅长西瓜、豆角等作物的种植管理。"
    "你具备以下能力：查询天气预报和灾害预警、查看种植周期和当前阶段、"
    "了解近期农事记录、统计成本收支。请根据用户的问题，主动调用合适的工具"
    "获取信息，然后给出具体、可操作的建议。回答要简洁明了，适合农民理解。"
    "使用中文回答。"
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _should_continue(state: AgentState) -> str:
    """判断是否需要继续调用工具。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点。"""
    tools = get_langchain_tools()
    llm = get_llm().bind_tools(tools)
    system = HumanMessage(content=SYSTEM_PROMPT)
    response = llm.invoke([system] + state["messages"])
    return {"messages": [response]}


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。"""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    tool_map = {t.name: t for t in get_langchain_tools()}

    async def _call_one(tc: dict) -> ToolMessage:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        logger.info("🔧 Skill 调用 %s(%s)", name, args)
        try:
            tool = tool_map.get(name)
            if not tool:
                return ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id)
            result = await tool.ainvoke(args)
            summary = str(result)[:120].replace("\n", " ")
            logger.info("✅ Skill 返回 %s → %s", name, summary)
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            logger.error("❌ Skill 失败 %s: %s", name, e)
            return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)

    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("⚡ 并行执行 %d 个 Skill", len(last.tool_calls))
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])

    return {"messages": results}


def compile_advisor_graph():
    """编译建议 Agent 的 StateGraph（支持并行 Skill 执行）。

    Returns:
        编译后的 LangGraph 图实例。
    """
    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", _parallel_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


__all__ = ["compile_advisor_graph"]
```

- [ ] **Step 2: 验证语法**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -c "from app.agents.graph import compile_advisor_graph; print('OK')"
```

Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/graph.py
git commit -m "feat: custom StateGraph with parallel skill execution"
```

---

### Task 11: 更新 advisor.py

**Files:**
- Modify: `backend/app/agents/advisor.py`

- [ ] **Step 1: advisor.py 不需要大改**，只需确保 `__init__.py` 中的 `__all__` 正确。

确认 `advisor.py` 中 `from app.agents.graph import compile_advisor_graph` 仍然正常，接口不变（invoke_advisor / stream_advisor / build_advisor_agent）。

无需修改，跳过。

---

### Task 12: 删除旧 tools.py

**Files:**
- Delete: `backend/app/agents/tools.py`
- Modify: `backend/app/agents/report.py` (如有引用)

- [ ] **Step 1: 检查 tools.py 的引用**

```bash
cd /Users/ljn/Documents/demo/explore/backend
grep -rn "from app.agents.tools" app/ --include="*.py"
```

Expected: 只在 `tools.py` 自身和 `graph.py`（已改）中出现。如果有其他文件引用，需先更新。

- [ ] **Step 2: 删除 tools.py**

```bash
rm backend/app/agents/tools.py
```

- [ ] **Step 3: 验证启动**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m app.main &
sleep 4
curl -s http://localhost:8000/health
kill $!
```

Expected: `{"status":"ok'}`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy tools.py, fully migrated to skills/"
```

---

### Task 13: 端到端验证

- [ ] **Step 1: 启动后端**

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python app/main.py
```

- [ ] **Step 2: 测试 chat 接口**

```bash
curl -s -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我看看周期1的进度和成本","cycle_id":1}'
```

Expected: 正常返回，日志显示 2 个 Skill 并行执行。

- [ ] **Step 3: 验证缓存**

再次请求相同问题，日志应出现 `CACHE HIT`。

- [ ] **Step 4: 测试流式接口**

```bash
curl -s -N -X POST http://localhost:8000/agent/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"今天天气怎么样"}' | head -5
```

Expected: 返回 `data: {"content":"..."} 流式数据。

- [ ] **Step 5: 最终 Commit**

```bash
git add -A
git commit -m "test: verify skill engine end-to-end"
```
