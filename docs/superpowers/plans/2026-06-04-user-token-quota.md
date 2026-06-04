# User Token Quota Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 token 统计从农场日限额升级为用户级月/周配额，并保持真实用量只来自 provider usage。

**Architecture:** `TokenDailyStats` 保留 `farm_id` 并新增 `user_id`，真实账本只由 `TraceCollector.record(node_type="llm_call")` 写入。配额检查以认证用户 `user_id` 为主体，Admin API 和前端通过用户维度展示月/周用量。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、LangChain AIMessage、pytest、React、TypeScript、Ant Design。

---

## 文件结构

后端数据与配置：
- 修改 `backend/app/models/user.py`：新增用户月/周 token 限额字段。
- 修改 `backend/app/models/token_stats.py`：新增 `user_id` 字段，更新唯一约束。
- 修改 `backend/app/core/settings/models.py`：将 token quota 配置改为月/周默认限额和 `warn|reject`。
- 修改 `backend/config.yaml.example`：增加 `token_quota` 示例。
- 修改 `backend/app/api/admin_config.py`：返回新的 token quota 配置。

后端配额与统计：
- 修改 `backend/app/services/quota_service.py`：实现周期计算、用户限额读取、月/周检查。
- 修改 `backend/app/infra/trace_context.py`：TraceInfo 增加 `user_id` 和 `call_type`。
- 修改 `backend/app/agent/runtime/messages.py`：新增 usage 归一化函数。
- 修改 `backend/app/infra/trace_collector.py`：只在真实 provider usage 存在时累计统计。
- 修改 `backend/app/infra/trace_dao.py`：按 `user_id + farm_id + date + model + call_type` 累计。

Agent 主链路：
- 修改 `backend/app/services/agent_service.py`：传递 `user_id` 到 advisor。
- 修改 `backend/app/agent/advisor.py`：`invoke_advisor` / `stream_advisor` 接收并写入 `init_trace` 和 graph state。
- 修改 `backend/app/agent/runtime/nodes.py`：使用 `check_user_quota`，按 `QuotaCheckResult` 返回超限消息。

Admin API：
- 修改 `backend/app/schemas/admin_user.py`：新增配额响应和请求 schema。
- 修改 `backend/app/api/admin_users.py`：新增单用户配额查询/修改、配额概览。
- 修改 `backend/app/api/admin_stats.py`：新增 `user_id`/`farm_id` 过滤和管理员鉴权。

前端：
- 修改 `admin-web/src/api/admin.ts`：更新 token stats 和 config 类型。
- 修改 `admin-web/src/api/users.ts`：新增 quota API。
- 修改 `admin-web/src/pages/TokenDashboard/index.tsx`：用户筛选、月/周进度、去掉硬编码 `QUOTA_LIMIT`。
- 修改 `admin-web/src/pages/Users/index.tsx`：用户列表和详情展示配额。
- 修改 `admin-web/src/pages/ConfigKeys/index.tsx`：展示月/周默认限额和 `reject`。

测试：
- 修改 `backend/tests/services/test_quota_service.py`。
- 修改 `backend/tests/core/test_trace_context.py`。
- 修改 `backend/tests/core/test_trace_collector.py`。
- 修改 `backend/tests/core/test_trace_dao.py`。
- 修改 `backend/tests/api/test_admin_stats.py`。
- 修改 `backend/tests/api/test_admin_users.py`。
- 修改 `backend/tests/api/test_admin_config.py`。
- 修改或新增 `backend/tests/agent/test_token_usage_extraction.py`。

## Task 1: 数据模型与配置

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/token_stats.py`
- Modify: `backend/app/core/settings/models.py`
- Modify: `backend/config.yaml.example`
- Modify: `backend/app/api/admin_config.py`
- Test: `backend/tests/api/test_admin_config.py`

- [ ] **Step 1: 写配置 API 失败测试**

在 `backend/tests/api/test_admin_config.py` 的 `TestGetConfig` 中追加：

```python
def test_config_returns_monthly_and_weekly_quota(self, client) -> None:
    resp = client.get("/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_quota"]["monthly_limit"] == 3000000
    assert data["token_quota"]["weekly_limit"] == 750000
    assert data["token_quota"]["over_quota_action"] == "reject"
    assert "daily_limit" not in data["token_quota"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && pytest tests/api/test_admin_config.py::TestGetConfig::test_config_returns_monthly_and_weekly_quota -v
```

Expected: FAIL，响应中仍只有 `daily_limit` 或默认 action 仍为 `warn`。

- [ ] **Step 3: 修改 User 模型**

在 `backend/app/models/user.py` 的 import 改为包含 `Integer`：

```python
from sqlalchemy import Column, DateTime, Integer, String, func
```

在 `User` 类中 `status` 后添加：

```python
    token_monthly_limit = Column(Integer, nullable=True)
    token_weekly_limit = Column(Integer, nullable=True)
```

- [ ] **Step 4: 修改 TokenDailyStats 模型**

将 `backend/app/models/token_stats.py` 中约束和字段改为：

```python
class TokenDailyStats(Base):
    """按日汇总的 Token 用量统计。"""

    __tablename__ = "token_daily_stats"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "farm_id",
            "date",
            "model",
            "call_type",
            name="uq_token_stats",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=True, index=True)
    farm_id = Column(Integer, nullable=False, index=True)
    date = Column(String(10), nullable=False)
    model = Column(String(100), nullable=False)
    call_type = Column(String(20), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    request_count = Column(Integer, default=0)
    estimated_cost_cny = Column(Numeric(10, 6), default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

- [ ] **Step 5: 修改 TokenQuotaConfig**

在 `backend/app/core/settings/models.py` 中替换 `TokenQuotaConfig`：

```python
class TokenQuotaConfig(BaseModel):
    monthly_limit: int = 3000000
    weekly_limit: int = 750000
    over_quota_action: str = "reject"
```

- [ ] **Step 6: 修改 admin_config 返回值**

在 `backend/app/api/admin_config.py` 的 `token_quota` 返回值替换为：

```python
        "token_quota": {
            "monthly_limit": settings.token_quota.monthly_limit,
            "weekly_limit": settings.token_quota.weekly_limit,
            "over_quota_action": settings.token_quota.over_quota_action,
        },
```

- [ ] **Step 7: 更新配置示例**

在 `backend/config.yaml.example` 的 `rate_limiting` 前添加：

```yaml
token_quota:
  monthly_limit: 3000000
  weekly_limit: 750000
  over_quota_action: "reject"  # warn / reject
```

- [ ] **Step 8: 跑配置测试**

Run:

```bash
cd backend && pytest tests/api/test_admin_config.py::TestGetConfig::test_config_returns_monthly_and_weekly_quota -v
```

Expected: PASS。

- [ ] **Step 9: 提交**

```bash
git add backend/app/models/user.py backend/app/models/token_stats.py backend/app/core/settings/models.py backend/config.yaml.example backend/app/api/admin_config.py backend/tests/api/test_admin_config.py
git commit -m "feat: add user token quota model config"
```

## Task 2: 配额服务

**Files:**
- Modify: `backend/app/services/quota_service.py`
- Test: `backend/tests/services/test_quota_service.py`

- [ ] **Step 1: 写配额服务测试**

用下面内容替换 `backend/tests/services/test_quota_service.py`：

```python
"""Tests for app.services.quota_service。"""

from datetime import date
from unittest.mock import MagicMock, patch

from app.models.farm import Farm
from app.models.user import User
from app.services.quota_service import (
    QuotaCheckResult,
    check_quota,
    check_user_quota,
    get_period_usage,
    get_user_quota_limits,
    get_week_range,
    get_month_range,
)


def test_get_month_range_returns_natural_month() -> None:
    start, end = get_month_range(date(2026, 6, 4))
    assert start == date(2026, 6, 1)
    assert end == date(2026, 6, 30)


def test_get_week_range_starts_monday() -> None:
    start, end = get_week_range(date(2026, 6, 4))
    assert start == date(2026, 6, 1)
    assert end == date(2026, 6, 7)


def test_get_user_quota_limits_uses_custom_values() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=500,
        token_weekly_limit=100,
    )
    db.query.return_value.filter.return_value.first.return_value = user

    limits = get_user_quota_limits("u1", db)

    assert limits.monthly_limit == 500
    assert limits.weekly_limit == 100


def test_get_period_usage_sums_user_tokens() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = 123

    usage = get_period_usage(
        user_id="u1",
        start=date(2026, 6, 1),
        end=date(2026, 6, 7),
        db=db,
    )

    assert usage == 123


def test_check_user_quota_rejects_missing_user_id() -> None:
    db = MagicMock()

    result = check_user_quota(None, db)

    assert isinstance(result, QuotaCheckResult)
    assert result.allowed is False
    assert result.exceeded_period == "identity"


def test_check_user_quota_allows_under_limits() -> None:
    db = MagicMock()
    user = User(id="u1", phone="1", password_hash="h", nickname="n")
    db.query.return_value.filter.return_value.first.return_value = user
    with patch("app.services.quota_service.get_period_usage", side_effect=[10, 20]):
        result = check_user_quota("u1", db, today=date(2026, 6, 4))

    assert result.allowed is True
    assert result.exceeded_period is None
    assert result.monthly_usage == 10
    assert result.weekly_usage == 20


def test_check_user_quota_rejects_weekly_over_limit() -> None:
    db = MagicMock()
    user = User(
        id="u1",
        phone="1",
        password_hash="h",
        nickname="n",
        token_monthly_limit=1000,
        token_weekly_limit=100,
    )
    db.query.return_value.filter.return_value.first.return_value = user
    with patch("app.services.quota_service.get_period_usage", side_effect=[50, 100]):
        result = check_user_quota("u1", db, today=date(2026, 6, 4))

    assert result.allowed is False
    assert result.exceeded_period == "week"


@patch("app.services.quota_service.SessionLocal")
def test_check_quota_wraps_farm_user_lookup(mock_session_local) -> None:
    db = MagicMock()
    mock_session_local.return_value = db
    db.query.return_value.filter.return_value.first.return_value = Farm(
        id=1,
        name="f",
        user_id="u1",
    )
    with patch("app.services.quota_service.check_user_quota") as check_user:
        check_user.return_value = QuotaCheckResult(allowed=True)
        assert check_quota(1) is True
        check_user.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && pytest tests/services/test_quota_service.py -v
```

Expected: FAIL，缺少 `QuotaCheckResult`、周期函数和 `check_user_quota`。

- [ ] **Step 3: 实现配额服务**

用下面内容替换 `backend/app/services/quota_service.py`：

```python
"""Token 配额检查服务。"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infra.database import SessionLocal
from app.infra.settings import settings
from app.models.farm import Farm
from app.models.token_stats import TokenDailyStats
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class QuotaLimits:
    monthly_limit: int
    weekly_limit: int


@dataclass
class QuotaCheckResult:
    allowed: bool
    exceeded_period: str | None = None
    monthly_usage: int = 0
    monthly_limit: int = 0
    weekly_usage: int = 0
    weekly_limit: int = 0
    reset_at: str | None = None


def get_month_range(today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    start = current.replace(day=1)
    if current.month == 12:
        next_month = current.replace(year=current.year + 1, month=1, day=1)
    else:
        next_month = current.replace(month=current.month + 1, day=1)
    return start, next_month - timedelta(days=1)


def get_week_range(today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    start = current - timedelta(days=current.weekday())
    return start, start + timedelta(days=6)


def get_user_quota_limits(user_id: str, db: Session) -> QuotaLimits:
    user = db.query(User).filter(User.id == user_id).first()
    monthly = user.token_monthly_limit if user and user.token_monthly_limit else None
    weekly = user.token_weekly_limit if user and user.token_weekly_limit else None
    return QuotaLimits(
        monthly_limit=monthly or settings.token_quota.monthly_limit,
        weekly_limit=weekly or settings.token_quota.weekly_limit,
    )


def get_period_usage(user_id: str, start: date, end: date, db: Session) -> int:
    total = (
        db.query(func.coalesce(func.sum(TokenDailyStats.total_tokens), 0))
        .filter(
            TokenDailyStats.user_id == user_id,
            TokenDailyStats.date >= start.isoformat(),
            TokenDailyStats.date <= end.isoformat(),
        )
        .scalar()
    )
    return int(total or 0)


def check_user_quota(
    user_id: str | None,
    db: Session,
    today: date | None = None,
) -> QuotaCheckResult:
    if not user_id:
        return QuotaCheckResult(allowed=False, exceeded_period="identity")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return QuotaCheckResult(allowed=False, exceeded_period="identity")

    current = today or date.today()
    month_start, month_end = get_month_range(current)
    week_start, week_end = get_week_range(current)
    limits = get_user_quota_limits(user_id, db)
    monthly_usage = get_period_usage(user_id, month_start, month_end, db)
    weekly_usage = get_period_usage(user_id, week_start, week_end, db)

    result = QuotaCheckResult(
        allowed=True,
        monthly_usage=monthly_usage,
        monthly_limit=limits.monthly_limit,
        weekly_usage=weekly_usage,
        weekly_limit=limits.weekly_limit,
    )
    if monthly_usage >= limits.monthly_limit:
        result.allowed = False
        result.exceeded_period = "month"
        result.reset_at = month_end.isoformat()
    elif weekly_usage >= limits.weekly_limit:
        result.allowed = False
        result.exceeded_period = "week"
        result.reset_at = week_end.isoformat()
    return result


def check_quota(farm_id: int) -> bool:
    db = SessionLocal()
    try:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        result = check_user_quota(farm.user_id if farm else None, db)
        if not result.allowed:
            logger.warning(
                "Token 配额超限 | farm=%s user=%s period=%s action=%s",
                farm_id,
                farm.user_id if farm else "-",
                result.exceeded_period,
                settings.token_quota.over_quota_action,
            )
        return result.allowed
    finally:
        db.close()


__all__ = [
    "QuotaCheckResult",
    "QuotaLimits",
    "check_quota",
    "check_user_quota",
    "get_month_range",
    "get_period_usage",
    "get_user_quota_limits",
    "get_week_range",
]
```

- [ ] **Step 4: 跑配额服务测试**

Run:

```bash
cd backend && pytest tests/services/test_quota_service.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/quota_service.py backend/tests/services/test_quota_service.py
git commit -m "feat: add user quota service"
```

## Task 3: Trace 和真实 usage 统计

**Files:**
- Modify: `backend/app/infra/trace_context.py`
- Modify: `backend/app/agent/runtime/messages.py`
- Modify: `backend/app/infra/trace_collector.py`
- Modify: `backend/app/infra/trace_dao.py`
- Test: `backend/tests/core/test_trace_context.py`
- Test: `backend/tests/core/test_trace_collector.py`
- Test: `backend/tests/core/test_trace_dao.py`
- Create: `backend/tests/agent/test_token_usage_extraction.py`

- [ ] **Step 1: 写 usage 归一化测试**

创建 `backend/tests/agent/test_token_usage_extraction.py`：

```python
"""Token usage 提取测试。"""

from langchain_core.messages import AIMessage

from app.agent.runtime.messages import extract_token_usage


def test_extracts_usage_metadata() -> None:
    msg = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        },
    )

    result = extract_token_usage(msg)

    assert result == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "usage_source": "usage_metadata",
    }


def test_extracts_response_metadata_token_usage() -> None:
    msg = AIMessage(
        content="ok",
        response_metadata={
            "token_usage": {
                "prompt_tokens": 11,
                "completion_tokens": 6,
                "total_tokens": 17,
            }
        },
    )

    result = extract_token_usage(msg)

    assert result == {
        "prompt_tokens": 11,
        "completion_tokens": 6,
        "total_tokens": 17,
        "usage_source": "provider",
    }


def test_missing_usage_returns_none() -> None:
    msg = AIMessage(content="ok")

    assert extract_token_usage(msg) is None
```

- [ ] **Step 2: 写 trace context 测试**

在 `backend/tests/core/test_trace_context.py` 中追加：

```python
def test_init_with_user_id_and_call_type(self) -> None:
    trace = init_trace(
        farm_id=1,
        session_id="sess",
        request_id="req12345",
        user_id="u1",
        call_type="stream_chat",
    )
    assert trace.user_id == "u1"
    assert trace.call_type == "stream_chat"
```

- [ ] **Step 3: 写 collector 统计测试**

在 `backend/tests/core/test_trace_collector.py` 中替换 `test_record_accumulates_token_stats`：

```python
def test_record_accumulates_token_stats(self) -> None:
    """record 同时调用 token 统计累加。"""
    init_trace(farm_id=1, user_id="u1", call_type="chat")
    from app.infra.trace_collector import TraceCollector

    collector = TraceCollector.__new__(TraceCollector)
    collector._dao = MagicMock()
    collector._dao.record = MagicMock()
    collector._dao.accumulate_token_stats = MagicMock()
    collector.record(
        node_type="llm_call",
        node_name="llm",
        input_data="test",
        output_data="ok",
        token_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "usage_source": "provider",
        },
    )
    collector._dao.accumulate_token_stats.assert_called_once_with(
        farm_id=1,
        user_id="u1",
        date_str=__import__("datetime").date.today().isoformat(),
        model="llm",
        call_type="chat",
        prompt_tokens=100,
        completion_tokens=50,
    )
```

再追加：

```python
def test_record_missing_usage_does_not_accumulate(self) -> None:
    init_trace(farm_id=1, user_id="u1", call_type="chat")
    from app.infra.trace_collector import TraceCollector

    collector = TraceCollector.__new__(TraceCollector)
    collector._dao = MagicMock()
    collector._dao.record = MagicMock()
    collector._dao.accumulate_token_stats = MagicMock()
    collector.record(
        node_type="llm_call",
        node_name="llm",
        token_usage={"usage_source": "missing"},
    )
    collector._dao.accumulate_token_stats.assert_not_called()
```

- [ ] **Step 4: 运行 trace 测试确认失败**

Run:

```bash
cd backend && pytest tests/agent/test_token_usage_extraction.py tests/core/test_trace_context.py tests/core/test_trace_collector.py -v
```

Expected: FAIL，缺少新函数和新字段。

- [ ] **Step 5: 修改 TraceInfo**

在 `backend/app/infra/trace_context.py` 中将 dataclass 和 init 函数改为：

```python
@dataclass
class TraceInfo:
    """一次对话请求的追踪上下文。"""

    request_id: str
    session_id: str
    farm_id: int
    created_at: float
    user_id: str | None = None
    call_type: str = "chat"


def init_trace(
    farm_id: int,
    session_id: str = "",
    request_id: str = "",
    user_id: str | None = None,
    call_type: str = "chat",
) -> TraceInfo:
    """初始化追踪上下文，生成唯一 request_id。"""
    trace = TraceInfo(
        request_id=request_id or uuid.uuid4().hex[:8],
        session_id=session_id,
        farm_id=farm_id,
        created_at=time.time(),
        user_id=user_id,
        call_type=call_type,
    )
    _trace_ctx.set(trace)
    _round_ctx.set(0)
    return trace
```

- [ ] **Step 6: 新增 usage 提取函数**

在 `backend/app/agent/runtime/messages.py` 中保留 `_extract_tokens_used`，并新增：

```python
def extract_token_usage(response: AIMessage) -> dict | None:
    """从 LangChain AIMessage 中归一化 provider token usage。"""
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    if usage_metadata:
        prompt = int(usage_metadata.get("input_tokens") or 0)
        completion = int(usage_metadata.get("output_tokens") or 0)
        total = int(usage_metadata.get("total_tokens") or prompt + completion)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "usage_source": "usage_metadata",
        }

    metadata = response.response_metadata or {}
    token_usage = metadata.get("token_usage") or metadata.get("usage") or {}
    if token_usage:
        prompt = int(token_usage.get("prompt_tokens") or 0)
        completion = int(token_usage.get("completion_tokens") or 0)
        total = int(token_usage.get("total_tokens") or prompt + completion)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "usage_source": "provider",
        }

    return None
```

并将 `__all__` 加上 `"extract_token_usage"`。

- [ ] **Step 7: 修改 TraceDAO 累加签名**

在 `backend/app/infra/trace_dao.py` 中将 `accumulate_token_stats` 签名和查询过滤改为：

```python
    def accumulate_token_stats(
        self,
        farm_id: int,
        user_id: str | None,
        date_str: str,
        model: str,
        call_type: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """累加 Token 日用量统计（UPSERT 逻辑）。"""
        total = prompt_tokens + completion_tokens
        db = SessionLocal()
        try:
            existing = (
                db.query(TokenDailyStats)
                .filter(
                    TokenDailyStats.user_id == user_id,
                    TokenDailyStats.farm_id == farm_id,
                    TokenDailyStats.date == date_str,
                    TokenDailyStats.model == model,
                    TokenDailyStats.call_type == call_type,
                )
                .first()
            )
            if existing:
                existing.prompt_tokens += prompt_tokens
                existing.completion_tokens += completion_tokens
                existing.total_tokens += total
                existing.request_count += 1
            else:
                db.add(
                    TokenDailyStats(
                        user_id=user_id,
                        farm_id=farm_id,
                        date=date_str,
                        model=model,
                        call_type=call_type,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total,
                        request_count=1,
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("累加 token 统计失败")
        finally:
            db.close()
```

- [ ] **Step 8: 修改 TraceCollector**

在 `backend/app/infra/trace_collector.py` 的累计逻辑替换为：

```python
        if (
            token_usage
            and node_type == "llm_call"
            and token_usage.get("usage_source") in {"provider", "usage_metadata"}
        ):
            dao.accumulate_token_stats(
                farm_id=trace.farm_id,
                user_id=trace.user_id,
                date_str=date.today().isoformat(),
                model=node_name,
                call_type=trace.call_type,
                prompt_tokens=token_usage.get("prompt_tokens", 0),
                completion_tokens=token_usage.get("completion_tokens", 0),
            )
        elif token_usage and node_type == "llm_call":
            logger.warning(
                "LLM usage 缺失，跳过 TokenDailyStats 累计 | request=%s source=%s",
                trace.request_id,
                token_usage.get("usage_source", "missing"),
            )
```

- [ ] **Step 9: 跑 trace 测试**

Run:

```bash
cd backend && pytest tests/agent/test_token_usage_extraction.py tests/core/test_trace_context.py tests/core/test_trace_collector.py tests/core/test_trace_dao.py -v
```

Expected: PASS。

- [ ] **Step 10: 提交**

```bash
git add backend/app/infra/trace_context.py backend/app/agent/runtime/messages.py backend/app/infra/trace_collector.py backend/app/infra/trace_dao.py backend/tests/agent/test_token_usage_extraction.py backend/tests/core/test_trace_context.py backend/tests/core/test_trace_collector.py backend/tests/core/test_trace_dao.py
git commit -m "feat: record provider token usage by user"
```

## Task 4: Agent 用户透传和配额拦截

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/app/agent/advisor.py`
- Modify: `backend/app/agent/runtime/nodes.py`
- Test: `backend/tests/api/test_agent_api.py`

- [ ] **Step 1: 写 Agent 透传测试**

在 `backend/tests/api/test_agent_api.py` 添加或补充一个测试，patch `invoke_advisor`：

```python
from unittest.mock import AsyncMock, patch


def test_chat_passes_current_user_to_advisor(client, auth_headers):
    with patch("app.services.agent_service.invoke_advisor", new=AsyncMock(return_value="ok")) as advisor:
        resp = client.post(
            "/agent/chat",
            json={"message": "你好"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert advisor.await_args.kwargs["user_id"] == "test-user-001"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && pytest tests/api/test_agent_api.py::test_chat_passes_current_user_to_advisor -v
```

Expected: FAIL，`invoke_advisor` 未收到 `user_id`。

- [ ] **Step 3: 修改 agent_service 调用**

在 `backend/app/services/agent_service.py` 中调用 `invoke_advisor` 时增加：

```python
        user_id=user_id,
```

在 `stream_chat_with_agent` 调用 `stream_advisor` 时也传：

```python
        user_id=user_id,
```

- [ ] **Step 4: 修改 advisor 签名和 trace**

在 `backend/app/agent/advisor.py` 中给 `invoke_advisor` 和 `stream_advisor` 增加参数：

```python
    user_id: str | None = None,
    call_type: str = "chat",
```

将 `init_trace(...)` 改为：

```python
    init_trace(
        farm_id=farm_id,
        session_id=session_id,
        request_id=request_id,
        user_id=user_id,
        call_type=call_type,
    )
```

graph 输入增加：

```python
                "user_id": user_id,
                "session_id": session_id,
```

- [ ] **Step 5: 修改 runtime 配额检查**

在 `backend/app/agent/runtime/nodes.py` 中 import 改为：

```python
from app.services.quota_service import check_user_quota
from app.core.database import SessionLocal
```

将旧的 `check_quota(farm_id=farm_id)` 逻辑替换为：

```python
    user_id = state.get("user_id")
    db = SessionLocal()
    try:
        quota = check_user_quota(user_id if isinstance(user_id, str) else None, db)
    finally:
        db.close()

    if not quota.allowed:
        action = settings.token_quota.over_quota_action
        if action == "reject":
            if quota.exceeded_period == "month":
                return {
                    "messages": [
                        AIMessage(content="本月用量已达上限，配额将在下月重置。")
                    ]
                }
            if quota.exceeded_period == "week":
                return {
                    "messages": [
                        AIMessage(content="本周用量已达上限，配额将在下周一重置。")
                    ]
                }
            return {"messages": [AIMessage(content="缺少可信用户上下文，无法继续处理。")]}
        logger.warning("Token 配额超限，warn 模式继续调用 | period=%s", quota.exceeded_period)
```

- [ ] **Step 6: 修改 LLM usage 提取**

在 `backend/app/agent/runtime/nodes.py` 的 token 提取处改用：

```python
    token_usage = extract_token_usage(response)
    tokens = token_usage["total_tokens"] if token_usage else None
```

并在 import 中加入：

```python
    extract_token_usage,
```

- [ ] **Step 7: 跑 Agent 测试**

Run:

```bash
cd backend && pytest tests/api/test_agent_api.py -v
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add backend/app/services/agent_service.py backend/app/agent/advisor.py backend/app/agent/runtime/nodes.py backend/tests/api/test_agent_api.py
git commit -m "feat: enforce user token quota in agent"
```

## Task 5: Admin API

**Files:**
- Modify: `backend/app/schemas/admin_user.py`
- Modify: `backend/app/api/admin_users.py`
- Modify: `backend/app/api/admin_stats.py`
- Test: `backend/tests/api/test_admin_users.py`
- Test: `backend/tests/api/test_admin_stats.py`

- [ ] **Step 1: 写 admin stats 测试**

在 `backend/tests/api/test_admin_stats.py` 增加管理员覆盖，并测试全量查询：

```python
from app.api.deps import get_current_user
from app.models.user import User


@pytest.fixture
def admin_user_override():
    admin = User(
        id="admin-001",
        phone="18800000000",
        password_hash="h",
        nickname="管理员",
        role="admin",
        status="active",
    )
    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: admin
    yield admin
    if original:
        app.dependency_overrides[get_current_user] = original
    else:
        app.dependency_overrides.pop(get_current_user, None)
```

将请求改为带 `admin_user_override`，并新增：

```python
def test_summary_supports_user_filter(client, admin_user_override) -> None:
    mock_db = _mock_db()
    mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("qwen", "chat", 10, 5, 15, 1),
    ]

    def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    try:
        resp = client.get("/admin/stats/tokens?user_id=u1&days=7")
        assert resp.status_code == 200
        assert resp.json()["total_tokens"] == 15
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: 写用户配额 API 测试**

在 `backend/tests/api/test_admin_users.py` 追加：

```python
def test_get_user_quota(client, admin_user, admin_headers, target_user):
    resp = client.get(f"/admin/users/{target_user.id}/quota", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["monthly_limit"] == 3000000
    assert data["weekly_limit"] == 750000
    assert data["status"] in {"normal", "warning", "exceeded"}


def test_update_user_quota(client, admin_user, admin_headers, target_user):
    resp = client.put(
        f"/admin/users/{target_user.id}/quota",
        json={"token_monthly_limit": 5000000, "token_weekly_limit": 1200000},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["monthly_limit"] == 5000000
    assert data["weekly_limit"] == 1200000


def test_get_quota_overview(client, admin_user, admin_headers, target_user):
    resp = client.get("/admin/users/quota-overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
```

- [ ] **Step 3: 运行 API 测试确认失败**

Run:

```bash
cd backend && pytest tests/api/test_admin_stats.py tests/api/test_admin_users.py -v
```

Expected: FAIL，缺少 quota endpoints 和 stats filter。

- [ ] **Step 4: 新增 schema**

在 `backend/app/schemas/admin_user.py` 追加：

```python
class UserQuotaStatus(BaseModel):
    monthly_limit: int
    monthly_usage: int
    monthly_remaining: int
    monthly_start: str
    monthly_end: str
    weekly_limit: int
    weekly_usage: int
    weekly_remaining: int
    weekly_start: str
    weekly_end: str
    status: str


class UpdateUserQuotaRequest(BaseModel):
    token_monthly_limit: int | None = Field(None, ge=0)
    token_weekly_limit: int | None = Field(None, ge=0)


class UserQuotaOverviewItem(BaseModel):
    user_id: str
    nickname: str
    phone: str
    monthly_limit: int
    monthly_usage: int
    monthly_percent: float
    weekly_limit: int
    weekly_usage: int
    weekly_percent: float
    status: str


class UserQuotaOverviewResponse(PaginatedResponse[UserQuotaOverviewItem]):
    pass
```

- [ ] **Step 5: 实现 admin_users quota endpoints**

在 `backend/app/api/admin_users.py` 增加 helper 和路由：

```python
from app.services.quota_service import (
    get_month_range,
    get_period_usage,
    get_user_quota_limits,
    get_week_range,
)
```

```python
def _build_quota_status(user_id: str, db: Session) -> UserQuotaStatus:
    month_start, month_end = get_month_range()
    week_start, week_end = get_week_range()
    limits = get_user_quota_limits(user_id, db)
    monthly_usage = get_period_usage(user_id, month_start, month_end, db)
    weekly_usage = get_period_usage(user_id, week_start, week_end, db)
    monthly_percent = monthly_usage / limits.monthly_limit if limits.monthly_limit else 0
    weekly_percent = weekly_usage / limits.weekly_limit if limits.weekly_limit else 0
    status = "normal"
    if monthly_percent >= 1 or weekly_percent >= 1:
        status = "exceeded"
    elif monthly_percent >= 0.8 or weekly_percent >= 0.8:
        status = "warning"
    return UserQuotaStatus(
        monthly_limit=limits.monthly_limit,
        monthly_usage=monthly_usage,
        monthly_remaining=max(0, limits.monthly_limit - monthly_usage),
        monthly_start=month_start.isoformat(),
        monthly_end=month_end.isoformat(),
        weekly_limit=limits.weekly_limit,
        weekly_usage=weekly_usage,
        weekly_remaining=max(0, limits.weekly_limit - weekly_usage),
        weekly_start=week_start.isoformat(),
        weekly_end=week_end.isoformat(),
        status=status,
    )
```

```python
@router.get("/quota-overview", response_model=UserQuotaOverviewResponse)
def get_quota_overview(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserQuotaOverviewResponse:
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset((page - 1) * size).limit(size).all()
    items = []
    for user in users:
        quota = _build_quota_status(user.id, db)
        monthly_percent = quota.monthly_usage / quota.monthly_limit if quota.monthly_limit else 0
        weekly_percent = quota.weekly_usage / quota.weekly_limit if quota.weekly_limit else 0
        if status and quota.status != status:
            continue
        items.append(
            UserQuotaOverviewItem(
                user_id=user.id,
                nickname=user.nickname,
                phone=user.phone,
                monthly_limit=quota.monthly_limit,
                monthly_usage=quota.monthly_usage,
                monthly_percent=monthly_percent,
                weekly_limit=quota.weekly_limit,
                weekly_usage=quota.weekly_usage,
                weekly_percent=weekly_percent,
                status=quota.status,
            )
        )
    return UserQuotaOverviewResponse(items=items, total=total)


@router.get("/{user_id}/quota", response_model=UserQuotaStatus)
def get_user_quota(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserQuotaStatus:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _build_quota_status(user_id, db)


@router.put("/{user_id}/quota", response_model=UserQuotaStatus)
def update_user_quota(
    user_id: str,
    req: UpdateUserQuotaRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserQuotaStatus:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.token_monthly_limit = req.token_monthly_limit
    user.token_weekly_limit = req.token_weekly_limit
    db.commit()
    return _build_quota_status(user_id, db)
```

- [ ] **Step 6: 修改 admin_stats**

给 `token_summary` 和 `token_daily` 增加：

```python
    user_id: str | None = Query(None),
    farm_id: int | None = Query(None),
    _admin: User = Depends(require_admin),
```

构建查询时使用：

```python
    query = db.query(...).filter(TokenDailyStats.date >= start_date)
    if user_id:
        query = query.filter(TokenDailyStats.user_id == user_id)
    if farm_id is not None:
        query = query.filter(TokenDailyStats.farm_id == farm_id)
```

`token_daily` 同样按 `user_id` 和 `farm_id` 可选过滤。

- [ ] **Step 7: 跑 Admin API 测试**

Run:

```bash
cd backend && pytest tests/api/test_admin_stats.py tests/api/test_admin_users.py -v
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add backend/app/schemas/admin_user.py backend/app/api/admin_users.py backend/app/api/admin_stats.py backend/tests/api/test_admin_users.py backend/tests/api/test_admin_stats.py
git commit -m "feat: add admin user quota APIs"
```

## Task 6: 前端管理页面

**Files:**
- Modify: `admin-web/src/api/admin.ts`
- Modify: `admin-web/src/api/users.ts`
- Modify: `admin-web/src/pages/TokenDashboard/index.tsx`
- Modify: `admin-web/src/pages/Users/index.tsx`
- Modify: `admin-web/src/pages/ConfigKeys/index.tsx`

- [ ] **Step 1: 更新 admin API 类型**

在 `admin-web/src/api/admin.ts` 将 `TokenQuotaConfig` 改为：

```ts
export interface TokenQuotaConfig {
  monthly_limit: number;
  weekly_limit: number;
  over_quota_action: "warn" | "reject";
}
```

更新 token stats 请求参数：

```ts
export interface TokenStatsParams {
  days?: number;
  user_id?: string;
  farm_id?: number;
}

export async function getTokenSummary(params: TokenStatsParams = {}): Promise<TokenSummary> {
  const res = await apiClient.get<TokenSummary>('/admin/stats/tokens', { params });
  return res.data;
}

export async function getDailyTokenStats(
  date: string,
  params: Pick<TokenStatsParams, 'user_id' | 'farm_id'> = {},
): Promise<DailyTokenStats> {
  const res = await apiClient.get<DailyTokenStats>('/admin/stats/tokens/daily', {
    params: { date, ...params },
  });
  return res.data;
}
```

- [ ] **Step 2: 更新 users API 类型**

在 `admin-web/src/api/users.ts` 追加：

```ts
export interface UserQuotaStatus {
  monthly_limit: number;
  monthly_usage: number;
  monthly_remaining: number;
  monthly_start: string;
  monthly_end: string;
  weekly_limit: number;
  weekly_usage: number;
  weekly_remaining: number;
  weekly_start: string;
  weekly_end: string;
  status: "normal" | "warning" | "exceeded";
}

export interface UpdateUserQuotaRequest {
  token_monthly_limit: number | null;
  token_weekly_limit: number | null;
}

export interface UserQuotaOverviewItem {
  user_id: string;
  nickname: string;
  phone: string;
  monthly_limit: number;
  monthly_usage: number;
  monthly_percent: number;
  weekly_limit: number;
  weekly_usage: number;
  weekly_percent: number;
  status: "normal" | "warning" | "exceeded";
}

export interface UserQuotaOverviewResponse {
  items: UserQuotaOverviewItem[];
  total: number;
}
```

在 `usersApi` 追加：

```ts
  getQuota: (userId: string) =>
    apiClient.get<UserQuotaStatus>(`/admin/users/${userId}/quota`),

  updateQuota: (userId: string, data: UpdateUserQuotaRequest) =>
    apiClient.put<UserQuotaStatus>(`/admin/users/${userId}/quota`, data),

  getQuotaOverview: (params?: { page?: number; size?: number; status?: string }) =>
    apiClient.get<UserQuotaOverviewResponse>("/admin/users/quota-overview", { params }),
```

- [ ] **Step 3: TokenDashboard 改造**

在 `admin-web/src/pages/TokenDashboard/index.tsx`：
- 删除 `const QUOTA_LIMIT = 10000;`
- 新增用户选择状态：

```ts
const [selectedUserId, setSelectedUserId] = useState<string | undefined>();
```

请求改为：

```ts
Promise.all([
  getTokenSummary({ days, user_id: selectedUserId }),
  getDailyTokenStats(todayStr, { user_id: selectedUserId }),
])
```

展示月/周进度时使用后端 quota API 数据；如果未选择用户，展示全局默认配额文案。最小实现可以先把卡片标题改成：

```tsx
<div style={{ color: TEXT_DIM, fontSize: 14, marginBottom: 8 }}>月配额使用</div>
```

和：

```tsx
<div style={{ color: TEXT_DIM, fontSize: 14, marginBottom: 8 }}>周配额使用</div>
```

- [ ] **Step 4: Users 页面改造**

在 `admin-web/src/pages/Users/index.tsx` 中加载列表后并行请求 quota overview：

```ts
const quotaRes = await usersApi.getQuotaOverview({ page, size });
const quotaMap = new Map(quotaRes.data.items.map((item) => [item.user_id, item]));
setUsers(res.data.items.map((user) => ({ ...user, quota: quotaMap.get(user.id) })));
```

给 `UserListItem` 扩展可选字段：

```ts
quota?: UserQuotaOverviewItem;
```

新增表格列：

```tsx
{
  title: "月用量/月限额",
  key: "monthly_quota",
  width: 180,
  render: (_, record) => record.quota ? (
    <Progress
      percent={Math.round(record.quota.monthly_percent * 100)}
      size="small"
      status={record.quota.status === "exceeded" ? "exception" : "normal"}
      format={() => `${record.quota!.monthly_usage}/${record.quota!.monthly_limit}`}
    />
  ) : "-",
},
{
  title: "周用量/周限额",
  key: "weekly_quota",
  width: 180,
  render: (_, record) => record.quota ? (
    <Progress
      percent={Math.round(record.quota.weekly_percent * 100)}
      size="small"
      status={record.quota.status === "exceeded" ? "exception" : "normal"}
      format={() => `${record.quota!.weekly_usage}/${record.quota!.weekly_limit}`}
    />
  ) : "-",
},
```

详情弹窗打开时调用：

```ts
const quotaRes = await usersApi.getQuota(userId);
```

并展示月/周限额、已用、剩余、周期起止。

- [ ] **Step 5: ConfigKeys 页面改造**

在 `admin-web/src/pages/ConfigKeys/index.tsx` 替换 Token 配额展示：

```tsx
<Descriptions.Item label="月默认限额">
  {config.token_quota.monthly_limit.toLocaleString()}
</Descriptions.Item>
<Descriptions.Item label="周默认限额">
  {config.token_quota.weekly_limit.toLocaleString()}
</Descriptions.Item>
<Descriptions.Item label="超额动作">
  <Tag color={config.token_quota.over_quota_action === "reject" ? "error" : "warning"}>
    {config.token_quota.over_quota_action}
  </Tag>
</Descriptions.Item>
```

- [ ] **Step 6: 构建前端**

Run:

```bash
cd admin-web && pnpm build
```

Expected: PASS，TypeScript 无错误。

- [ ] **Step 7: 提交**

```bash
git add admin-web/src/api/admin.ts admin-web/src/api/users.ts admin-web/src/pages/TokenDashboard/index.tsx admin-web/src/pages/Users/index.tsx admin-web/src/pages/ConfigKeys/index.tsx
git commit -m "feat: add user token quota admin UI"
```

## Task 7: 全量验证与 OpenSpec 收尾

**Files:**
- Modify: `openspec/changes/user-token-quota/tasks.md`

- [ ] **Step 1: 运行 OpenSpec 校验**

Run:

```bash
openspec validate user-token-quota --strict
```

Expected: `Change 'user-token-quota' is valid`。

- [ ] **Step 2: 运行后端测试**

Run:

```bash
cd backend && pytest -v
```

Expected: PASS。

- [ ] **Step 3: 运行前端构建**

Run:

```bash
cd admin-web && pnpm build
```

Expected: PASS。

- [ ] **Step 4: 运行 lint**

Run:

```bash
ruff check . && ruff format .
```

Expected: PASS 或格式化完成后无剩余 lint error。

- [ ] **Step 5: 更新 OpenSpec tasks**

在 `openspec/changes/user-token-quota/tasks.md` 中把已完成项全部改为 `[x]`。

- [ ] **Step 6: 提交收尾**

```bash
git add openspec/changes/user-token-quota/tasks.md
git commit -m "docs: mark user token quota tasks complete"
```

## 自查

Spec 覆盖：
- 用户级 token 统计：Task 1、Task 3、Task 5。
- Provider usage 真实账本：Task 3。
- 月/周双周期配额：Task 2、Task 4。
- 全局默认配额：Task 1、Task 2、Task 6。
- 超限拒绝和 warn 模式：Task 2、Task 4。
- 管理员查询/修改用户配额：Task 5、Task 6。
- Token Dashboard 用户筛选和配置同步：Task 6。

占位符扫描：
- 本计划没有 `TBD`、`TODO`、`implement later`。
- 每个任务都包含测试、实现代码或明确替换片段、运行命令和提交命令。

类型一致性：
- 后端统一使用 `monthly_limit`、`weekly_limit`、`over_quota_action`。
- 前端 `TokenQuotaConfig` 与后端 `admin_config` 返回字段一致。
- 统计维度统一为 `user_id + farm_id + date + model + call_type`。
