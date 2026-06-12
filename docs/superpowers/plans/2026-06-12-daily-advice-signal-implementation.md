# Daily Advice Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `GET /agent/daily` return a low-noise mixed-mode daily advice list: future 3-day Top 3 action items, with operating-state data such as undated unpaid labor kept out of AI advice.

**Architecture:** Add a structured daily-advice signal pipeline beside the existing `farm_context_service`: collect source signals, build `DailyAdviceCandidate` objects, rank and suppress them, then pass only selected candidates to the existing LLM prompt for final copywriting. Keep `GET /agent/daily` and `DailyAdviceResponse` unchanged for clients.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, pytest, existing `AgentRecord` cache, existing weather service.

---

## Files

| File | Responsibility |
| --- | --- |
| `backend/app/services/daily_advice_signals.py` | New structured signal collection, candidate model, ranking, fingerprinting, and prompt context rendering. |
| `backend/app/services/agent_service.py` | Use ranked daily advice candidates before invoking the advisor; write candidate diagnostics into `AgentRecord.meta`; keep backward-compatible fallback. |
| `backend/prompts/daily_advice.j2` | Instruct LLM to only rewrite supplied candidates and avoid ordinary operating-state reminders. |
| `backend/tests/services/test_daily_advice_signals.py` | New unit tests for candidate ranking, suppression, signal collection, and rendering. |
| `backend/tests/test_agent_service.py` | Integration tests that `get_daily_advice` passes candidate context and stores diagnostics. |
| `backend/tests/services/test_farm_context_service.py` | Update expectations only if legacy summary behavior changes; prefer not touching it in this plan. |

## Design Rules To Preserve

- Homepage AI advice returns Top 3; detail-capable context may contain up to Top 5 candidates.
- Weather, operations, crop stages, and due finance can enter advice.
- Undated unpaid labor does not enter AI advice.
- Undated debts do not enter AI advice.
- Monthly cost does not enter AI advice.
- Recent operations are used for suppression, not as direct advice.
- LLM should not decide business priority from raw status; backend ranks candidates first.

---

### Task 1: Candidate Model, Ranking, Suppression, And Rendering

**Files:**
- Create: `backend/app/services/daily_advice_signals.py`
- Test: `backend/tests/services/test_daily_advice_signals.py`

- [ ] **Step 1: Write failing tests for pure ranking and rendering**

Create `backend/tests/services/test_daily_advice_signals.py` with these tests at the top:

```python
"""Daily advice signal pipeline tests."""

from datetime import date, timedelta

from app.services.daily_advice_signals import (
    DailyAdviceCandidate,
    DailyAdviceCategory,
    rank_daily_advice_candidates,
    render_candidate_context,
)


def _candidate(
    *,
    key: str,
    category: DailyAdviceCategory,
    priority: int,
    due_date: date | None = None,
    title: str = "候选建议",
    detail: str = "候选详情",
) -> DailyAdviceCandidate:
    return DailyAdviceCandidate(
        id=key,
        category=category,
        title_hint=title,
        detail_hint=detail,
        priority=priority,
        due_date=due_date,
        source_type="test",
        source_id=None,
        dedupe_key=key,
        reason="测试原因",
    )


def test_rank_keeps_p1_before_p2_and_limits_homepage_to_three():
    today = date.today()
    candidates = [
        _candidate(key="p3", category="setup", priority=3, title="补记录"),
        _candidate(key="p2", category="operation", priority=2, title="明天作业"),
        _candidate(key="p1", category="weather", priority=1, title="高温预警"),
        _candidate(key="p2b", category="crop_stage", priority=2, title="巡田"),
    ]

    ranked = rank_daily_advice_candidates(candidates, today=today, limit=3)

    assert [item.id for item in ranked] == ["p1", "p2", "p2b"]


def test_rank_limits_weather_and_finance_categories():
    today = date.today()
    candidates = [
        _candidate(key="weather-1", category="weather", priority=1, title="高温"),
        _candidate(key="weather-2", category="weather", priority=1, title="暴雨"),
        _candidate(key="finance-1", category="finance", priority=1, title="逾期账款"),
        _candidate(key="finance-2", category="finance", priority=2, title="临期账款"),
        _candidate(key="operation-1", category="operation", priority=2, title="采收"),
    ]

    ranked = rank_daily_advice_candidates(candidates, today=today, limit=5)

    assert [item.id for item in ranked] == [
        "weather-1",
        "finance-1",
        "operation-1",
    ]


def test_rank_deduplicates_by_dedupe_key():
    today = date.today()
    candidates = [
        _candidate(key="hot-1", category="weather", priority=1, title="今天高温"),
        DailyAdviceCandidate(
            id="hot-2",
            category="weather",
            title_hint="明天高温",
            detail_hint="连续高温",
            priority=1,
            due_date=today + timedelta(days=1),
            source_type="weather",
            source_id=None,
            dedupe_key="weather:heat",
            reason="重复天气",
        ),
    ]
    candidates[0].dedupe_key = "weather:heat"

    ranked = rank_daily_advice_candidates(candidates, today=today, limit=5)

    assert len(ranked) == 1
    assert ranked[0].id == "hot-1"


def test_render_candidate_context_contains_only_ranked_candidates():
    today = date.today()
    candidates = [
        _candidate(
            key="weather",
            category="weather",
            priority=1,
            due_date=today,
            title="高温错峰采收",
            detail="今天最高温 36 度，避开中午高温时段",
        ),
        _candidate(
            key="operation",
            category="operation",
            priority=2,
            due_date=today + timedelta(days=2),
            title="安排巡田",
            detail="未来 3 天进入伸蔓期，检查水肥",
        ),
    ]

    context = render_candidate_context(candidates)

    assert "高温错峰采收" in context
    assert "安排巡田" in context
    assert "priority=1" in context
    assert "source=weather" in context
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/services/test_daily_advice_signals.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.daily_advice_signals'`.

- [ ] **Step 3: Implement candidate model, ranker, and renderer**

Create `backend/app/services/daily_advice_signals.py`:

```python
"""Structured signal pipeline for daily advice."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

DailyAdviceCategory = Literal[
    "weather",
    "operation",
    "crop_stage",
    "finance",
    "setup",
    "record",
]

_CATEGORY_LIMITS: dict[DailyAdviceCategory, int] = {
    "weather": 1,
    "finance": 1,
    "operation": 2,
    "crop_stage": 2,
    "setup": 1,
    "record": 1,
}

_CATEGORY_ORDER: dict[DailyAdviceCategory, int] = {
    "weather": 0,
    "operation": 1,
    "crop_stage": 2,
    "finance": 3,
    "setup": 4,
    "record": 5,
}


@dataclass(slots=True)
class DailyAdviceCandidate:
    """A structured action candidate before LLM copywriting."""

    id: str
    category: DailyAdviceCategory
    title_hint: str
    detail_hint: str
    priority: int
    due_date: date | None
    source_type: str
    source_id: int | None
    dedupe_key: str
    reason: str

    def to_meta(self) -> dict:
        """Return JSON-serializable diagnostics for trace/cache meta."""
        payload = asdict(self)
        payload["due_date"] = self.due_date.isoformat() if self.due_date else None
        return payload


def rank_daily_advice_candidates(
    candidates: list[DailyAdviceCandidate],
    *,
    today: date | None = None,
    limit: int = 3,
) -> list[DailyAdviceCandidate]:
    """Sort and suppress candidates for the daily advice surface."""
    today = today or date.today()
    sorted_candidates = sorted(candidates, key=lambda item: _sort_key(item, today))
    selected: list[DailyAdviceCandidate] = []
    category_counts: dict[DailyAdviceCategory, int] = {}
    seen_dedupe: set[str] = set()

    for candidate in sorted_candidates:
        if candidate.dedupe_key in seen_dedupe:
            continue
        category_limit = _CATEGORY_LIMITS[candidate.category]
        if category_counts.get(candidate.category, 0) >= category_limit:
            continue
        selected.append(candidate)
        seen_dedupe.add(candidate.dedupe_key)
        category_counts[candidate.category] = category_counts.get(candidate.category, 0) + 1
        if len(selected) >= limit:
            break

    return selected


def render_candidate_context(candidates: list[DailyAdviceCandidate]) -> str:
    """Render ranked candidates into compact prompt context."""
    if not candidates:
        return "今日无明确高优先级行动候选。"
    lines = ["【今日行动候选】"]
    for index, candidate in enumerate(candidates, start=1):
        due_text = candidate.due_date.isoformat() if candidate.due_date else "无明确日期"
        lines.append(
            f"{index}. priority={candidate.priority}; "
            f"category={candidate.category}; source={candidate.source_type}; "
            f"due={due_text}; title={candidate.title_hint}; "
            f"detail={candidate.detail_hint}; reason={candidate.reason}"
        )
    return "\n".join(lines)


def fingerprint_candidates(candidates: list[DailyAdviceCandidate]) -> str:
    """Build a stable fingerprint for selected candidates."""
    payload = [candidate.to_meta() for candidate in candidates]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _sort_key(candidate: DailyAdviceCandidate, today: date) -> tuple:
    due_rank = _due_rank(candidate.due_date, today)
    return (
        candidate.priority,
        due_rank,
        _CATEGORY_ORDER[candidate.category],
        candidate.id,
    )


def _due_rank(due_date: date | None, today: date) -> int:
    if due_date is None:
        return 99
    return (due_date - today).days
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/services/test_daily_advice_signals.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/daily_advice_signals.py backend/tests/services/test_daily_advice_signals.py
git commit -m "feat(agent): 增加今日建议候选排序模型"
```

---

### Task 2: Finance And Operation Signal Collection

**Files:**
- Modify: `backend/app/services/daily_advice_signals.py`
- Modify: `backend/tests/services/test_daily_advice_signals.py`

- [ ] **Step 1: Add failing tests for finance and operation collection**

Append to `backend/tests/services/test_daily_advice_signals.py`:

```python
from decimal import Decimal

from app.models.cost import CostRecord
from app.models.planting import OperationWorkOrder
from app.services.daily_advice_signals import collect_daily_advice_candidates


async def test_collect_excludes_undated_debts_and_unpaid_labor(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        _fake_weather(days=[(date.today(), 25.0, 0.0, 3.0)]),
    )
    db_session.add(
        CostRecord(
            farm_id=1,
            record_type="cost",
            category="人工",
            amount=Decimal("650"),
            settled_amount=Decimal("0"),
            record_date=date.today(),
            note="未标注日期的欠款",
            record_subtype="赊账",
            counterparty="工人",
            due_date=None,
        )
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1)

    assert all(candidate.category != "finance" for candidate in candidates)


async def test_collect_includes_overdue_and_upcoming_due_debts(db_session, monkeypatch):
    today = date.today()
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        _fake_weather(days=[(today, 25.0, 0.0, 3.0)]),
    )
    db_session.add_all(
        [
            CostRecord(
                farm_id=1,
                record_type="cost",
                category="农资",
                amount=Decimal("200"),
                settled_amount=Decimal("0"),
                record_date=today,
                record_subtype="赊账",
                counterparty="农资店",
                due_date=today - timedelta(days=1),
            ),
            CostRecord(
                farm_id=1,
                record_type="cost",
                category="农资",
                amount=Decimal("300"),
                settled_amount=Decimal("0"),
                record_date=today,
                record_subtype="赊账",
                counterparty="种子店",
                due_date=today + timedelta(days=3),
            ),
        ]
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1)
    finance = [candidate for candidate in candidates if candidate.category == "finance"]

    assert len(finance) == 2
    assert {candidate.priority for candidate in finance} == {1, 2}
    assert any("农资店" in candidate.detail_hint for candidate in finance)


async def test_collect_operation_candidates_for_overdue_and_upcoming(db_session, monkeypatch):
    today = date.today()
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        _fake_weather(days=[(today, 25.0, 0.0, 3.0)]),
    )
    db_session.add_all(
        [
            OperationWorkOrder(
                farm_id=1,
                operation_type="采收",
                operation_date=today - timedelta(days=1),
                scope_type="farm",
            ),
            OperationWorkOrder(
                farm_id=1,
                operation_type="巡田",
                operation_date=today + timedelta(days=2),
                scope_type="farm",
            ),
        ]
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1)
    operations = [candidate for candidate in candidates if candidate.category == "operation"]

    assert len(operations) == 2
    assert any(candidate.priority == 1 and "采收" in candidate.title_hint for candidate in operations)
    assert any(candidate.priority == 2 and "巡田" in candidate.title_hint for candidate in operations)


def _fake_weather(*, days):
    async def _fetch_weather(**_kwargs):
        return {
            "daily": {
                "time": [day.isoformat() for day, _temp, _rain, _wind in days],
                "temperature_2m_max": [temp for _day, temp, _rain, _wind in days],
                "precipitation_sum": [rain for _day, _temp, rain, _wind in days],
                "windspeed_10m_max": [wind for _day, _temp, _rain, wind in days],
            }
        }

    return _fetch_weather
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/services/test_daily_advice_signals.py::test_collect_excludes_undated_debts_and_unpaid_labor tests/services/test_daily_advice_signals.py::test_collect_includes_overdue_and_upcoming_due_debts tests/services/test_daily_advice_signals.py::test_collect_operation_candidates_for_overdue_and_upcoming -q
```

Expected: FAIL because `collect_daily_advice_candidates` is not implemented.

- [ ] **Step 3: Implement finance and operation collectors**

In `backend/app/services/daily_advice_signals.py`, add imports:

```python
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.cost import CostRecord, SETTLED
from app.models.planting import OperationWorkOrder
from app.services import weather_service
```

Then add these functions after `fingerprint_candidates`:

```python
_WINDOW_DAYS = 3


async def collect_daily_advice_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date | None = None,
) -> list[DailyAdviceCandidate]:
    """Collect all structured candidates for daily advice."""
    today = today or date.today()
    candidates: list[DailyAdviceCandidate] = []
    candidates.extend(_collect_operation_candidates(db, farm_id=farm_id, today=today))
    candidates.extend(_collect_finance_candidates(db, farm_id=farm_id, today=today))
    return candidates


def _collect_operation_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> list[DailyAdviceCandidate]:
    window_end = today + timedelta(days=_WINDOW_DAYS)
    orders = (
        db.query(OperationWorkOrder)
        .filter(OperationWorkOrder.farm_id == farm_id)
        .filter(OperationWorkOrder.operation_date <= window_end)
        .order_by(OperationWorkOrder.operation_date.asc(), OperationWorkOrder.id.asc())
        .limit(10)
        .all()
    )
    candidates: list[DailyAdviceCandidate] = []
    for order in orders:
        operation_date = order.operation_date
        if operation_date < today:
            priority = 1
            title = f"补处理{order.operation_type}"
            reason = "作业单已逾期"
        elif operation_date <= today + timedelta(days=1):
            priority = 1
            title = f"安排{order.operation_type}"
            reason = "作业单今日或明日到期"
        else:
            priority = 2
            title = f"准备{order.operation_type}"
            reason = "作业单未来 3 天临近"
        candidates.append(
            DailyAdviceCandidate(
                id=f"operation:{order.id}",
                category="operation",
                title_hint=title,
                detail_hint=f"{operation_date.isoformat()} 计划{order.operation_type}",
                priority=priority,
                due_date=operation_date,
                source_type="operation_work_order",
                source_id=order.id,
                dedupe_key=f"operation:{order.operation_type}:{operation_date.isoformat()}",
                reason=reason,
            )
        )
    return candidates


def _collect_finance_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> list[DailyAdviceCandidate]:
    window_end = today + timedelta(days=_WINDOW_DAYS)
    debts = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == "赊账")
        .filter(CostRecord.due_date.isnot(None))
        .filter(CostRecord.due_date <= window_end)
        .filter(
            or_(
                CostRecord.settlement_status.is_(None),
                CostRecord.settlement_status != SETTLED,
            )
        )
        .order_by(CostRecord.due_date.asc(), CostRecord.id.asc())
        .limit(10)
        .all()
    )
    candidates: list[DailyAdviceCandidate] = []
    for debt in debts:
        due_date = debt.due_date
        priority = 1 if due_date <= today else 2
        counterparty = debt.counterparty or debt.note or "未命名对象"
        amount = _money(debt.unsettled_amount)
        reason = "账款已逾期" if due_date <= today else "账款未来 3 天到期"
        candidates.append(
            DailyAdviceCandidate(
                id=f"finance:{debt.id}",
                category="finance",
                title_hint="处理到期账款" if priority == 1 else "留意到期账款",
                detail_hint=f"{counterparty} 剩余 {amount} 元，截止 {due_date.isoformat()}",
                priority=priority,
                due_date=due_date,
                source_type="cost_record",
                source_id=debt.id,
                dedupe_key=f"finance:{debt.id}",
                reason=reason,
            )
        )
    return candidates


def _money(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return str(value.normalize())
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/services/test_daily_advice_signals.py -q
```

Expected: PASS for Task 1 and Task 2 tests.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/daily_advice_signals.py backend/tests/services/test_daily_advice_signals.py
git commit -m "feat(agent): 收集今日建议作业和到期账款信源"
```

---

### Task 3: Weather, Crop Stage, And Recent-Operation Suppression

**Files:**
- Modify: `backend/app/services/daily_advice_signals.py`
- Modify: `backend/tests/services/test_daily_advice_signals.py`

- [ ] **Step 1: Add failing tests for weather, crop stage, and recent-operation suppression**

Append to `backend/tests/services/test_daily_advice_signals.py`:

```python
from app.models.crop import CropTemplate
from app.models.cycle import CropCycle, CycleStage


async def test_collect_weather_high_temperature_as_p1(db_session, monkeypatch):
    today = date.today()
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        _fake_weather(days=[(today, 36.0, 0.0, 4.0)]),
    )

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1)
    weather = [candidate for candidate in candidates if candidate.category == "weather"]

    assert len(weather) == 1
    assert weather[0].priority == 1
    assert "高温" in weather[0].title_hint


async def test_collect_merges_continuous_high_temperature(db_session, monkeypatch):
    today = date.today()
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        _fake_weather(
            days=[
                (today, 36.0, 0.0, 4.0),
                (today + timedelta(days=1), 37.0, 0.0, 4.0),
                (today + timedelta(days=2), 35.0, 0.0, 4.0),
            ]
        ),
    )

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1)
    weather = [candidate for candidate in candidates if candidate.category == "weather"]

    assert len(weather) == 1
    assert "持续高温" in weather[0].detail_hint


async def test_collect_current_crop_stage_candidate(db_session, monkeypatch):
    today = date.today()
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        _fake_weather(days=[(today, 25.0, 0.0, 3.0)]),
    )
    template = CropTemplate(farm_id=1, name="大豆", category="蔬菜")
    db_session.add(template)
    db_session.flush()
    cycle = CropCycle(
        farm_id=1,
        crop_template_id=template.id,
        name="夏季大豆",
        start_date=today - timedelta(days=10),
        status="active",
    )
    db_session.add(cycle)
    db_session.flush()
    db_session.add(
        CycleStage(
            cycle_id=cycle.id,
            name="播种期",
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=2),
            order_index=1,
            duration_days=5,
            key_tasks="关注出苗、保持墒情",
            is_current=True,
        )
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1)
    stages = [candidate for candidate in candidates if candidate.category == "crop_stage"]

    assert len(stages) == 1
    assert "大豆" in stages[0].detail_hint
    assert stages[0].priority == 2


async def test_recent_operation_suppresses_same_crop_stage_action(db_session, monkeypatch):
    today = date.today()
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        _fake_weather(days=[(today, 25.0, 0.0, 3.0)]),
    )
    template = CropTemplate(farm_id=1, name="大豆", category="蔬菜")
    db_session.add(template)
    db_session.flush()
    cycle = CropCycle(
        farm_id=1,
        crop_template_id=template.id,
        name="夏季大豆",
        start_date=today - timedelta(days=10),
        status="active",
    )
    db_session.add(cycle)
    db_session.flush()
    db_session.add(
        CycleStage(
            cycle_id=cycle.id,
            name="播种期",
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=2),
            order_index=1,
            duration_days=5,
            key_tasks="巡田",
            is_current=True,
        )
    )
    db_session.add(
        OperationWorkOrder(
            farm_id=1,
            cycle_id=cycle.id,
            operation_type="巡田",
            operation_date=today - timedelta(days=1),
            scope_type="cycle",
        )
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1)

    assert all("巡田" not in candidate.title_hint for candidate in candidates)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/services/test_daily_advice_signals.py::test_collect_weather_high_temperature_as_p1 tests/services/test_daily_advice_signals.py::test_collect_merges_continuous_high_temperature tests/services/test_daily_advice_signals.py::test_collect_current_crop_stage_candidate tests/services/test_daily_advice_signals.py::test_recent_operation_suppresses_same_crop_stage_action -q
```

Expected: FAIL because weather and crop-stage collectors are not implemented.

- [ ] **Step 3: Implement weather and crop-stage collectors**

In `backend/app/services/daily_advice_signals.py`, add imports:

```python
from app.models.cycle import CropCycle
```

Update `collect_daily_advice_candidates()` to collect recent operations first and append weather/crop candidates:

```python
async def collect_daily_advice_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date | None = None,
) -> list[DailyAdviceCandidate]:
    """Collect all structured candidates for daily advice."""
    today = today or date.today()
    recent_operations = _recent_operation_types(db, farm_id=farm_id, today=today)
    candidates: list[DailyAdviceCandidate] = []
    candidates.extend(await _collect_weather_candidates(today=today))
    candidates.extend(
        _collect_crop_stage_candidates(
            db,
            farm_id=farm_id,
            today=today,
            recent_operations=recent_operations,
        )
    )
    candidates.extend(_collect_operation_candidates(db, farm_id=farm_id, today=today))
    candidates.extend(_collect_finance_candidates(db, farm_id=farm_id, today=today))
    return candidates
```

Add these helpers:

```python
async def _collect_weather_candidates(*, today: date) -> list[DailyAdviceCandidate]:
    try:
        weather = await weather_service.fetch_weather(days=_WINDOW_DAYS)
    except Exception:
        return []
    daily = weather.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    rain = daily.get("precipitation_sum", [])
    wind = daily.get("windspeed_10m_max", [])

    heat_days: list[date] = []
    rain_days: list[date] = []
    wind_days: list[date] = []
    frost_days: list[date] = []
    for index, raw_day in enumerate(times[:_WINDOW_DAYS]):
        try:
            day = date.fromisoformat(raw_day)
        except (TypeError, ValueError):
            continue
        if day < today or day > today + timedelta(days=_WINDOW_DAYS):
            continue
        max_temp = _value_at(max_temps, index)
        precipitation = _value_at(rain, index)
        wind_speed = _value_at(wind, index)
        if max_temp is not None and max_temp >= 35:
            heat_days.append(day)
        if precipitation is not None and precipitation >= 10:
            rain_days.append(day)
        if wind_speed is not None and wind_speed >= 17:
            wind_days.append(day)

    if heat_days:
        return [
            DailyAdviceCandidate(
                id="weather:heat",
                category="weather",
                title_hint="高温错峰作业",
                detail_hint=_weather_detail("持续高温", heat_days)
                if len(heat_days) > 1
                else f"{heat_days[0].isoformat()} 最高温超过 35 度，避开中午高温时段",
                priority=1,
                due_date=heat_days[0],
                source_type="weather",
                source_id=None,
                dedupe_key="weather:heat",
                reason="未来 3 天存在高温风险",
            )
        ]
    if rain_days:
        return [
            DailyAdviceCandidate(
                id="weather:rain",
                category="weather",
                title_hint="降雨调整作业",
                detail_hint=_weather_detail("明显降雨", rain_days),
                priority=1,
                due_date=rain_days[0],
                source_type="weather",
                source_id=None,
                dedupe_key="weather:rain",
                reason="未来 3 天存在明显降雨",
            )
        ]
    if wind_days:
        return [
            DailyAdviceCandidate(
                id="weather:wind",
                category="weather",
                title_hint="大风加固设施",
                detail_hint=_weather_detail("大风", wind_days),
                priority=1,
                due_date=wind_days[0],
                source_type="weather",
                source_id=None,
                dedupe_key="weather:wind",
                reason="未来 3 天存在大风风险",
            )
        ]
    if frost_days:
        return [
            DailyAdviceCandidate(
                id="weather:frost",
                category="weather",
                title_hint="低温防护",
                detail_hint=_weather_detail("低温", frost_days),
                priority=1,
                due_date=frost_days[0],
                source_type="weather",
                source_id=None,
                dedupe_key="weather:frost",
                reason="未来 3 天存在低温风险",
            )
        ]
    return []


def _collect_crop_stage_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
    recent_operations: set[str],
) -> list[DailyAdviceCandidate]:
    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.start_date.desc(), CropCycle.id.asc())
        .limit(5)
        .all()
    )
    candidates: list[DailyAdviceCandidate] = []
    for cycle in cycles:
        stage = _current_stage(cycle)
        if stage is None:
            continue
        task_hint = (stage.key_tasks or "巡田观察").strip()
        operation_key = task_hint.split("、")[0].split("，")[0].strip()
        if operation_key and operation_key in recent_operations:
            continue
        candidates.append(
            DailyAdviceCandidate(
                id=f"crop-stage:{cycle.id}:{stage.id}",
                category="crop_stage",
                title_hint=f"{stage.name}管理",
                detail_hint=f"{cycle.name}处于{stage.name}，建议{task_hint}",
                priority=2,
                due_date=stage.end_date if stage.end_date <= today + timedelta(days=_WINDOW_DAYS) else None,
                source_type="crop_cycle",
                source_id=cycle.id,
                dedupe_key=f"crop-stage:{cycle.id}:{stage.name}",
                reason="当前茬口处于关键阶段",
            )
        )
    if not cycles:
        candidates.append(
            DailyAdviceCandidate(
                id=f"setup:create-cycle:{farm_id}",
                category="setup",
                title_hint="创建种植计划",
                detail_hint="当前无活跃茬口，建议先建立种植周期",
                priority=3,
                due_date=None,
                source_type="system",
                source_id=None,
                dedupe_key=f"setup:create-cycle:{farm_id}",
                reason="没有活跃茬口",
            )
        )
    return candidates


def _recent_operation_types(db: Session, *, farm_id: int, today: date) -> set[str]:
    start = today - timedelta(days=3)
    rows = (
        db.query(OperationWorkOrder.operation_type)
        .filter(OperationWorkOrder.farm_id == farm_id)
        .filter(OperationWorkOrder.operation_date >= start)
        .filter(OperationWorkOrder.operation_date <= today)
        .all()
    )
    return {str(row[0]) for row in rows if row[0]}


def _current_stage(cycle: CropCycle):
    for stage in cycle.stages:
        if stage.is_current:
            return stage
    return cycle.stages[-1] if cycle.stages else None


def _value_at(values: list, index: int):
    return values[index] if index < len(values) else None


def _weather_detail(label: str, days: list[date]) -> str:
    if len(days) > 1:
        return f"未来 3 天{label}，请提前调整采收、打药和户外作业"
    return f"{days[0].isoformat()} 有{label}风险，请提前调整作业"
```

- [ ] **Step 4: Run daily signal tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/services/test_daily_advice_signals.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/daily_advice_signals.py backend/tests/services/test_daily_advice_signals.py
git commit -m "feat(agent): 收集今日建议天气和茬口信源"
```

---

### Task 4: Integrate Ranked Candidates Into Daily Advice Generation

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/prompts/daily_advice.j2`
- Modify: `backend/tests/test_agent_service.py`

- [ ] **Step 1: Add failing integration tests**

In `backend/tests/test_agent_service.py`, add imports near existing imports:

```python
from app.services.daily_advice_signals import DailyAdviceCandidate
```

Add these tests inside `class TestGetDailyAdvice`:

```python
    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    @patch("app.services.agent_service.collect_daily_advice_candidates", new_callable=AsyncMock)
    async def test_get_daily_advice_uses_ranked_candidate_context(
        self,
        mock_collect: AsyncMock,
        mock_invoke: AsyncMock,
        mock_get_composer: MagicMock,
    ) -> None:
        """每日建议应优先使用结构化候选上下文，而不是原始农场摘要。"""
        mock_collect.return_value = [
            DailyAdviceCandidate(
                id="weather:heat",
                category="weather",
                title_hint="高温错峰作业",
                detail_hint="今天最高温 36 度，避开中午",
                priority=1,
                due_date=None,
                source_type="weather",
                source_id=None,
                dedupe_key="weather:heat",
                reason="高温风险",
            )
        ]
        mock_get_composer.return_value.compose.return_value = "daily prompt with candidates"
        mock_invoke.return_value = (
            '{"preview":"高温错峰作业","items":['
            '{"title":"高温错峰","detail":"今天最高温36度，避开中午","priority":1,"icon":"🌡️"}'
            "]}"
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        mock_collect.assert_awaited_once_with(mock_db, farm_id=1)
        variables = mock_get_composer.return_value.compose.call_args.kwargs["variables"]
        assert "今日行动候选" in variables["farm_context"]
        assert "高温错峰作业" in variables["farm_context"]
        assert result.preview == "高温错峰作业"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    @patch("app.services.agent_service.collect_daily_advice_candidates", new_callable=AsyncMock)
    async def test_get_daily_advice_stores_candidate_meta(
        self,
        mock_collect: AsyncMock,
        mock_invoke: AsyncMock,
        mock_get_composer: MagicMock,
    ) -> None:
        """保存每日建议时应记录候选诊断 meta，方便 debug export 排查。"""
        mock_collect.return_value = [
            DailyAdviceCandidate(
                id="operation:1",
                category="operation",
                title_hint="安排采收",
                detail_hint="今天计划采收",
                priority=1,
                due_date=None,
                source_type="operation_work_order",
                source_id=1,
                dedupe_key="operation:采收",
                reason="今日作业",
            )
        ]
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '{"preview":"安排采收","items":['
            '{"title":"安排采收","detail":"今天计划采收","priority":1,"icon":"📋"}'
            "]}"
        )
        mock_db = _make_mock_db()

        await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        record = mock_db.add.call_args.args[0]
        assert record.meta is not None
        assert "selected_candidates" in record.meta
        assert "operation:1" in record.meta
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_agent_service.py::TestGetDailyAdvice::test_get_daily_advice_uses_ranked_candidate_context tests/test_agent_service.py::TestGetDailyAdvice::test_get_daily_advice_stores_candidate_meta -q
```

Expected: FAIL because `agent_service` does not import or use the signal pipeline.

- [ ] **Step 3: Integrate signal pipeline in `agent_service.py`**

In `backend/app/services/agent_service.py`, add imports:

```python
from app.services.daily_advice_signals import (
    collect_daily_advice_candidates,
    fingerprint_candidates,
    rank_daily_advice_candidates,
    render_candidate_context,
)
```

Replace the context-building block inside `get_daily_advice()`:

```python
    # 注入农场上下文，通过 PromptComposer 渲染模板
    context = await farm_context_service.build_summary(db, farm_id)
    prompt = get_composer().compose(
        "daily_advice",
        variables={"farm_context": context, "cycle_id": cycle_id},
    )
```

with:

```python
    candidates = await collect_daily_advice_candidates(db, farm_id=farm_id)
    selected_candidates = rank_daily_advice_candidates(candidates, limit=5)
    if selected_candidates:
        context = render_candidate_context(selected_candidates)
    else:
        context = await farm_context_service.build_summary(db, farm_id)
    prompt = get_composer().compose(
        "daily_advice",
        variables={"farm_context": context, "cycle_id": cycle_id},
    )
```

Replace record creation:

```python
    record = AgentRecord(
        cycle_id=cycle_id, record_type="daily", content=advice, farm_id=farm_id
    )
```

with:

```python
    meta = {
        "selected_candidates": [
            candidate.to_meta() for candidate in selected_candidates[:5]
        ],
        "candidate_fingerprint": fingerprint_candidates(selected_candidates[:5]),
    }
    record = AgentRecord(
        cycle_id=cycle_id,
        record_type="daily",
        content=advice,
        farm_id=farm_id,
        meta=json.dumps(meta, ensure_ascii=False),
    )
```

- [ ] **Step 4: Update daily prompt guardrails**

Replace `backend/prompts/daily_advice.j2` with:

```jinja
基于后端筛选出的今日行动候选，生成今天的农事建议，返回 JSON。

{% if cycle_id %}当前关注周期 ID={{ cycle_id }}。{% endif %}

{% if farm_context %}
{{ farm_context }}
{% endif %}

结构：
{
  "preview": "≤15字今日一句话总结",
  "items": [
    {
      "title": "≤10字结论",
      "detail": "≤40字原因和具体操作建议",
      "priority": 1到3（1=紧急，2=重要，3=提醒）,
      "icon": "一个emoji"
    }
  ]
}

- 只改写「今日行动候选」里的事项，不要新增候选外的普通经营状态。
- 最多 5 条，首页会优先展示前 3 条，按 priority 升序。
- 无到期日欠款、未结人工、本月花费属于经营状态，不要写成今日建议。
- 有天气风险时，优先给出可执行动作，如错峰采收、推迟打药、加固设施。
- 避免重复近期已完成的操作。
```

- [ ] **Step 5: Run targeted integration tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_agent_service.py::TestGetDailyAdvice -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/agent_service.py backend/prompts/daily_advice.j2 backend/tests/test_agent_service.py
git commit -m "feat(agent): 接入今日建议结构化候选"
```

---

### Task 5: Cache Freshness, Regression Tests, And Full Verification

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/tests/test_advice_cache.py`
- Modify: `backend/tests/services/test_daily_advice_signals.py`

- [ ] **Step 1: Add failing cache freshness tests**

Append to `backend/tests/test_advice_cache.py`:

```python
    @pytest.mark.asyncio
    async def test_cache_hit_requires_same_candidate_fingerprint(self, db, mock_composer):
        """当候选 fingerprint 变化时，应重新生成今日建议。"""
        import json
        from app.services.daily_advice_signals import DailyAdviceCandidate

        today = _today_start()
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=_json_items_response("旧建议"),
                created_at=today,
                meta=json.dumps({"candidate_fingerprint": "old"}, ensure_ascii=False),
            )
        )
        db.commit()

        candidate = DailyAdviceCandidate(
            id="weather:heat",
            category="weather",
            title_hint="高温错峰",
            detail_hint="今天高温",
            priority=1,
            due_date=None,
            source_type="weather",
            source_id=None,
            dedupe_key="weather:heat",
            reason="高温",
        )
        with patch(
            "app.services.agent_service.collect_daily_advice_candidates",
            new_callable=AsyncMock,
        ) as mock_collect, patch(
            "app.services.agent_service.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_collect.return_value = [candidate]
            mock_llm.return_value = _json_items_response("新建议")
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].title == "新建议"
```

- [ ] **Step 2: Run cache test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_advice_cache.py::TestDailyAdviceCache::test_cache_hit_requires_same_candidate_fingerprint -q
```

Expected: FAIL because cache hit does not inspect candidate fingerprint.

- [ ] **Step 3: Refactor `get_daily_advice()` to compute candidates before cache hit**

In `backend/app/services/agent_service.py`, move candidate collection before querying cached `AgentRecord`:

```python
    candidates = await collect_daily_advice_candidates(db, farm_id=farm_id)
    selected_candidates = rank_daily_advice_candidates(candidates, limit=5)
    candidate_fingerprint = fingerprint_candidates(selected_candidates[:5])
```

Update cache hit condition inside `if cached:` so it only returns cached content when the fingerprint matches or legacy meta is missing:

```python
            cached_meta = _parse_record_meta(cached.meta)
            cached_fingerprint = cached_meta.get("candidate_fingerprint")
            if cached_fingerprint and cached_fingerprint != candidate_fingerprint:
                logger.info(
                    "每日建议缓存候选 fingerprint 变化，重新生成 | record_id=%s",
                    cached.id,
                )
            else:
                preview, items = _parse_advice_items(cached.content)
                logger.info("缓存命中 | record_id=%s", cached.id)
                return DailyAdviceResponse(
                    cycle_id=cached.cycle_id,
                    preview=preview,
                    items=items[:3],
                    created_at=cached.created_at,
                )
```

Add helper near `_build_notice_response()`:

```python
def _parse_record_meta(raw: str | None) -> dict:
    """Parse AgentRecord meta JSON defensively."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
```

When returning newly generated advice, limit homepage items to 3:

```python
    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        preview=preview,
        items=items[:3],
        created_at=record.created_at,
    )
```

- [ ] **Step 4: Run targeted daily advice tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_advice_cache.py tests/test_agent_service.py::TestGetDailyAdvice tests/services/test_daily_advice_signals.py -q
```

Expected: PASS.

- [ ] **Step 5: Run lint and focused backend verification**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run ruff check app/services/daily_advice_signals.py app/services/agent_service.py tests/services/test_daily_advice_signals.py tests/test_agent_service.py tests/test_advice_cache.py
poetry run pytest tests/services/test_daily_advice_signals.py tests/test_agent_service.py::TestGetDailyAdvice tests/test_advice_cache.py tests/services/test_farm_context_service.py -q
```

Expected: ruff exits 0; pytest exits 0.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/agent_service.py backend/tests/test_advice_cache.py backend/tests/services/test_daily_advice_signals.py
git commit -m "fix(agent): 按候选变化刷新今日建议缓存"
```

---

## Final Verification

After all tasks pass, run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run ruff check app tests
poetry run pytest tests/services/test_daily_advice_signals.py tests/test_agent_service.py::TestGetDailyAdvice tests/test_advice_cache.py tests/services/test_farm_context_service.py tests/test_agent_api.py -q
```

Expected: all checks pass.

Then inspect the final diff:

```bash
cd /Users/ljn/Documents/demo/explore
git status --short
git log --oneline -6
```

Expected: only intentional task commits appear after the plan commit; unrelated pre-existing worktree changes remain untouched.
