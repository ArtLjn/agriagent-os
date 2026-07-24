# 05 — Python 编码规范

> 状态：草稿 | 维护：BlockShip | 关联：权威 [.claude/rules/python-style.md](../../../.claude/rules/python-style.md)

---

## 1. 文件与方法限制

| 维度 | 上限 |
| --- | --- |
| 生产 Python 单文件 | ≤ 1000 行；500-1000 行进入观察区间，按职责混杂度评审 |
| 单方法 | 建议 ≤ 50 行；超过 80 行需说明或拆成步骤函数 |
| 单类 | ≤ 200 行 |
| 方法参数 | ≤ 5 个（超过用 Pydantic model / dataclass） |
| 单行 | ≤ 120 字符 |

CI 用 `ruff` 检查。

## 2. 项目结构

### 2.1 分层架构

```
bootstrap/routes
    ↓
domains/*/routes、platforms/*/routes、application/*
    ↓
domains/*/service、agent/*、context/*、memory/*、prompt/*、skills/*
    ↓
shared/、infra/
```

### 2.2 领域化与平台化

```
backend/app/
├── domains/
│   ├── users/
│   ├── farm/
│   ├── planting/
│   ├── finance/
│   ├── weather/
│   └── conversation/
└── platforms/
    ├── admin/
    ├── data_flywheel/
    ├── evaluation/
    └── simulation/
```

每个业务领域自包含 routes / service / dependencies / schemas / models / errors 等真实职责。不得新增 `app.modules`、`app.services`、`app.models` 等旧入口。

### 2.3 Agent 平台

```
backend/app/
├── application/  # chat/session/advice/report/smart_fill use case
├── agent/        # Router / Runtime / Executor / Reflector / Guardrails
├── prompt/       # Prompt 工程
├── context/      # Context 工程
├── memory/       # Memory 工程
├── platforms/    # admin / data_flywheel / evaluation / simulation
└── observability.py # 观测事件
```

详见 [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)。

### 2.4 配置集中

`backend/app/shared/config.py` 统一管理 Pydantic Settings，支持 YAML 与环境变量覆盖，业务代码只读不写。

### 2.5 公共工具

`backend/app/shared/` 放配置、数据库、日志、安全、时间、schema、LLM client manager；`backend/app/infra/` 放 Mongo、trace、limiter、repository runtime、RAG client 等适配。

## 3. 设计模式

| 场景 | 模式 |
| --- | --- |
| if/elif 超 3 个分支 | 策略模式（dict 派发或 Protocol） |
| 对象创建复杂 | 工厂模式 |
| 多对象通知 | 观察者模式 |
| 共享昂贵资源 | 单例模式 |

## 4. 类型注解

强制使用类型注解：

```python
def create_cost(
    db: Session,
    schema: CostCreate,
    farm_id: int,
) -> Cost:
    ...
```

**禁止**：
- 裸 dict / list 返回值（用 TypedDict 或 Pydantic）
- `Any` 类型（除非性能关键路径）
- 缺类型注解的 public 方法

## 5. Pydantic 模型

```python
from pydantic import BaseModel, Field, ConfigDict

class CostCreate(BaseModel):
    amount: int = Field(gt=0, le=1_000_000_000, description="金额（分）")
    category: str = Field(min_length=1, max_length=50)
    record_date: date
    note: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")
```

**规则**：
- API 入参必填字段校验（gt / ge / le / min_length / max_length）
- 拒绝未预期字段（`extra="forbid"`）
- description 必填（生成 OpenAPI 文档）

## 6. 异步

```python
# ✅ async/await
async def fetch_cost(db: Session, cost_id: int) -> Cost | None:
    return await db.scalar(select(Cost).where(Cost.id == cost_id))

# ✅ AsyncSession（推荐）
async with AsyncSession(engine) as db:
    ...

# ❌ 同步阻塞 async 流程
def heavy_io():
    time.sleep(5)
```

外部 IO（LLM、HTTP、DB）必须 async。

## 7. 错误处理

```python
class CostError(Exception):
    code: str
    message: str

class AmountExceededError(CostError):
    code = "COST_001"
    message = "金额超过上限"

# Service 层抛业务异常
if amount > 1_000_000_000:
    raise AmountExceededError()

# API 层统一捕获
@app.exception_handler(CostError)
async def cost_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"code": exc.code, "message": exc.message}
    )
```

**禁止**：
- 裸 `raise Exception`
- 业务异常用 HTTPException（应自定义业务异常 + handler）
- 异常信息含 traceback 给客户端

## 8. 日志

```python
import logging

logger = logging.getLogger(__name__)

logger.info(
    "cost_record_created",
    extra={
        "trace_id": trace_id,
        "farm_id": farm_id,
        "cost_id": cost.id,
        "amount": cost.amount,
    }
)
```

**规则**：
- 全部走 `logging.getLogger(__name__)`
- 生产 INFO 及以上，开发 DEBUG
- 日志带 trace_id / session_id / farm_id
- 结构化（key-value）格式
- 不打印敏感字段（password、token、API key）

**禁止**：
- `print()` 调试
- `logger.debug()` 写生产
- 日志未脱敏

## 9. IDE 检查规范（PyCharm 提示对齐）

| 提示 | 处理 |
| --- | --- |
| Method may be 'static' | 加 `@staticmethod` |
| Method may be 'class' | 加 `@classmethod` |
| Unused import / local variable | 删除 |
| Argument is not used | 加 `_` 前缀 |
| Shadows name from outer scope | 改名 |
| String concatenation in loop | 用 `"".join()` |
| Resource not closed | 用 `with` |

## 10. 测试规范

### 10.1 框架

- 主：pytest
- 异步：pytest-asyncio
- Mock：pytest-mock
- 参数化：pytest.mark.parametrize

### 10.2 目录

`tests/` 镜像源码：

```
backend/tests/
├── api/
│   ├── test_agent.py
│   └── test_cost.py
├── services/              # 历史测试目录仍有保留，新增优先按 domains/platforms 分类
│   └── test_cost_service.py
├── skills/
│   └── test_create_cost_record.py
├── agent/
│   └── runtime/
│       └── test_runtime_loop.py
└── conftest.py
```

### 10.3 测试结构

```python
class TestCreateCostRecord:
    """Arrange-Act-Assert 模式。"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_normal_creates_record(self, mock_db):
        # Arrange
        schema = CostCreate(amount=200, category="化肥", record_date=date.today())
        # Act
        result = create_cost(mock_db, schema, farm_id=1)
        # Assert
        assert result.amount == 200
        mock_db.add.assert_called_once()
```

### 10.4 覆盖要求

- 正常路径 + 异常路径 + 边界值
- pytest.raises 测异常
- 外部依赖必须 mock
- 不 mock 被测对象本身

## 11. Lint

```bash
ruff check .
ruff format .
```

CI 阻塞 lint 失败。

### 11.1 关键规则

- E / F：PEP8 + pyflakes
- I：isort（import 排序）
- N：命名规范
- UP：pyupgrade
- B：bugbear（常见 bug）
- SIM：简化
- ANN：类型注解（部分启用）

## 12. 导入规范

```python
# 标准库
import datetime
from pathlib import Path

# 第三方
import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

# 本项目
from app.shared.config import settings
from app.domains.finance.cost_models import CostRecord
from app.domains.finance.cost_service import create_cost
```

**禁止**：
- `from x import *`
- 循环导入
- 未使用导入

## 13. 注释

```python
# ❌ 解释 WHAT（代码自明）
i += 1  # 加 1

# ✅ 解释 WHY（非显然）
# 用分而非元：避免浮点误差（如 0.1 + 0.2 != 0.3）
amount_cents: int = 200
```

默认不写注释。仅在 WHY 非显然时写一行。

## 14. 相关文档

- [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)
- [04_相关规范/03_数据库与迁移规范](./03_数据库与迁移规范.md)
- [04_相关规范/06_防污染与文档同步规范](./06_防污染与文档同步规范.md)
- 权威：[../../../.claude/rules/python-style.md](../../../.claude/rules/python-style.md)
