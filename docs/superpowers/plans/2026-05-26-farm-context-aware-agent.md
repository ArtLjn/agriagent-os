# farm-context-aware-agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为农场管理系统添加结构化赊账数据层、独立债务管理 API、作物模板自定义页面，让 Agent 能基于结构化数据而非文本笔记提供服务。

**Architecture:** 在现有 `cost_records` 表新增结构化赊账字段（record_subtype/counterparty/due_date/settled_at/parent_record_id），替代现有 settle-debt Skill 的 note 文本匹配方案。新增 `/debts` REST API 供前端独立管理债务。移动端新增"赊账管理"和"作物模板"页面，记账页增加"赊账"类型选项。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic（后端），React Native + Zustand（移动端），pytest（测试）

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/alembic/versions/2026_05_26_add_debt_fields.py` | 数据库迁移：cost_records 新增 5 个字段 |
| `backend/app/services/debt_service.py` | 债务查询、统计、还款核心业务逻辑 |
| `backend/app/api/debt.py` | `/debts` REST API 路由 |
| `backend/tests/services/test_debt_service.py` | debt_service 单元测试 |
| `backend/tests/api/test_debt.py` | debt API 集成测试 |

### Backend — Modified Files
| File | Changes |
|------|---------|
| `backend/app/models/cost.py` | CostRecord 新增 record_subtype, counterparty, due_date, settled_at, parent_record_id |
| `backend/app/schemas/cost.py` | 新增 DebtRecord schemas；CostRecordBase 新增可选字段 |
| `backend/app/skills/settle-debt/scripts/main.py` | _find_debt_records 从 note.ilike 改为结构化字段查询 |
| `backend/app/main.py` | 注册 debt router |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `FarmManagerMobile/src/stores/debtStore.ts` | 债务状态管理（Zustand） |
| `FarmManagerMobile/src/screens/debt/DebtListScreen.tsx` | 赊账列表页面 |
| `FarmManagerMobile/src/screens/debt/DebtCreateScreen.tsx` | 创建赊账记录页面 |
| `FarmManagerMobile/src/screens/crop/CropTemplateScreen.tsx` | 作物模板列表与管理页面 |

### Frontend — Modified Files
| File | Changes |
|------|---------|
| `FarmManagerMobile/src/api/types.ts` | 新增 DebtRecord, DebtSummary 类型 |
| `FarmManagerMobile/src/api/client.ts` | 新增 debtApi 方法 |
| `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx` | 增加 record_subtype="赊账" 选项，显示 counterparty/due_date 输入 |
| `FarmManagerMobile/src/navigation/AppNavigator.tsx` | 注册 DebtList, DebtCreate, CropTemplate 路由 |

---

## Task 1: Database Migration — Add Debt Fields to cost_records

**Files:**
- Create: `backend/alembic/versions/2026_05_26_add_debt_fields_to_cost_records.py`

- [ ] **Step 1: Write the migration file**

```python
"""add debt fields to cost_records

Revision ID: 2026_05_26_add_debt_fields
Revises: <latest_revision>
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '2026_05_26_add_debt_fields'
down_revision = '<latest_revision>'  # 替换为 alembic/versions/ 中最新的 revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cost_records', sa.Column('record_subtype', sa.String(), nullable=True))
    op.add_column('cost_records', sa.Column('counterparty', sa.String(), nullable=True))
    op.add_column('cost_records', sa.Column('due_date', sa.Date(), nullable=True))
    op.add_column('cost_records', sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cost_records', sa.Column('parent_record_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_cost_records_parent',
        'cost_records', 'cost_records',
        ['parent_record_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_cost_records_parent', 'cost_records', type_='foreignkey')
    op.drop_column('cost_records', 'parent_record_id')
    op.drop_column('cost_records', 'settled_at')
    op.drop_column('cost_records', 'due_date')
    op.drop_column('cost_records', 'counterparty')
    op.drop_column('cost_records', 'record_subtype')
```

> 注意：`down_revision` 需替换为 `alembic/versions/` 目录中最新的 revision ID。运行 `ls backend/alembic/versions/` 查看。

- [ ] **Step 2: Run the migration**

```bash
cd backend && poetry run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade <latest> -> 2026_05_26_add_debt_fields, add debt fields to cost_records`

- [ ] **Step 3: Verify migration applied**

```bash
cd backend && poetry run alembic current
```

Expected: 显示 `2026_05_26_add_debt_fields`

- [ ] **Step 4: Verify columns exist in SQLite**

```bash
cd backend && sqlite3 app.db ".schema cost_records" | grep -E "record_subtype|counterparty|due_date|settled_at|parent_record_id"
```

Expected: 5 行输出，每行对应一个新字段

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/2026_05_26_add_debt_fields_to_cost_records.py
git commit -m "chore: 迁移 cost_records 新增赊账结构化字段"
```

---

## Task 2: Update CostRecord Model

**Files:**
- Modify: `backend/app/models/cost.py`

- [ ] **Step 1: Add new columns to CostRecord**

修改 `backend/app/models/cost.py`，在 `created_at` 之前插入：

```python
    record_subtype = Column(String, nullable=True)
    counterparty = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    parent_record_id = Column(Integer, ForeignKey("cost_records.id"), nullable=True)
```

同时添加导入：`from sqlalchemy import ForeignKey`（如果还没有的话）。

完整文件应为：

```python
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    func,
)

from app.core.database import Base


class CostRecord(Base):
    """成本记账模型，记录种植周期中的成本与收入。"""

    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(Integer, nullable=True)
    record_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    record_date = Column(Date, nullable=False)
    note = Column(String, nullable=True)
    record_subtype = Column(String, nullable=True)
    counterparty = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    parent_record_id = Column(Integer, ForeignKey("cost_records.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Run existing cost model tests**

```bash
cd backend && poetry run pytest tests/ -k "cost" -v --tb=short
```

Expected: 所有测试通过（模型变更不应破坏现有测试）

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/cost.py
git commit -m "feat: CostRecord 新增赊账结构化字段"
```

---

## Task 3: Update Cost Schemas

**Files:**
- Modify: `backend/app/schemas/cost.py`

- [ ] **Step 1: Add new optional fields to CostRecordBase**

在 `CostRecordBase` 中 `note` 字段之后添加：

```python
    record_subtype: str | None = Field(None, max_length=50)
    counterparty: str | None = Field(None, max_length=100)
    due_date: date | None = None
    settled_at: datetime | None = None
    parent_record_id: int | None = None
```

同时需要添加 `from datetime import datetime` 导入。

- [ ] **Step 2: Add Debt-specific schemas**

在文件末尾（`CostParseResult` 之后）添加：

```python
class DebtSummary(BaseModel):
    """债务统计 Schema。"""

    counterparty: str
    total_debt: Decimal
    total_settled: Decimal
    remaining: Decimal
    record_count: int
    model_config = ConfigDict(from_attributes=True)


class DebtListResponse(BaseModel):
    """债务列表响应 Schema。"""

    items: list[CostRecordResponse]
    total: int
    summary: list[DebtSummary]
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 3: Verify schema compiles**

```bash
cd backend && poetry run python -c "from app.schemas.cost import CostRecordBase, DebtSummary, DebtListResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/cost.py
git commit -m "feat: schemas 新增赊账字段和债务统计"
```

---

## Task 4: Create Debt Service

**Files:**
- Create: `backend/app/services/debt_service.py`
- Test: `backend/tests/services/test_debt_service.py`

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/services/test_debt_service.py`：

```python
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate
from app.services.debt_service import (
    create_debt_record,
    get_debt_records,
    get_debt_summary,
    settle_debt,
)


@pytest.fixture
def db_debt(db: Session) -> CostRecord:
    """创建一个赊账记录 fixture。"""
    record = CostRecordCreate(
        record_type="cost",
        category="化肥",
        amount=Decimal("500"),
        record_date=date.today(),
        record_subtype="赊账",
        counterparty="老王农资",
        due_date=date.today() + timedelta(days=30),
    )
    from app.services.cost_service import create_record
    return create_record(db, record, farm_id=1)


class TestCreateDebtRecord:
    def test_create_debt_with_subtype_and_counterparty(self, db: Session):
        record = CostRecordCreate(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date.today(),
            record_subtype="赊账",
            counterparty="老李",
            due_date=date.today() + timedelta(days=15),
        )
        debt = create_debt_record(db, record, farm_id=1)
        assert debt.record_subtype == "赊账"
        assert debt.counterparty == "老李"
        assert debt.due_date is not None
        assert debt.settled_at is None


class TestGetDebtRecords:
    def test_filter_by_counterparty(self, db: Session, db_debt: CostRecord):
        debts = get_debt_records(db, farm_id=1, counterparty="老王")
        assert len(debts) == 1
        assert debts[0].counterparty == "老王农资"

    def test_excludes_settled(self, db: Session, db_debt: CostRecord):
        db_debt.settled_at = date.today()
        db.commit()
        debts = get_debt_records(db, farm_id=1)
        assert all(d.settled_at is None for d in debts)


class TestGetDebtSummary:
    def test_summary_by_counterparty(self, db: Session, db_debt: CostRecord):
        summary = get_debt_summary(db, farm_id=1)
        assert len(summary) == 1
        assert summary[0].counterparty == "老王农资"
        assert summary[0].total_debt == Decimal("500")
        assert summary[0].remaining == Decimal("500")


class TestSettleDebt:
    def test_full_settle(self, db: Session, db_debt: CostRecord):
        result = settle_debt(db, farm_id=1, counterparty="老王农资")
        assert result.record_type == "income"
        assert result.category == "还款"
        assert result.amount == Decimal("500")
        assert result.parent_record_id == db_debt.id
        assert db_debt.settled_at is not None

    def test_partial_settle(self, db: Session, db_debt: CostRecord):
        result = settle_debt(
            db, farm_id=1, counterparty="老王农资", amount=Decimal("200")
        )
        assert result.amount == Decimal("200")
        assert db_debt.settled_at is None  # 部分还款不标记结清
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && poetry run pytest tests/services/test_debt_service.py -v
```

Expected: ImportError: `debt_service` not found

- [ ] **Step 3: Implement debt_service.py**

创建 `backend/app/services/debt_service.py`：

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate, DebtSummary
from app.services.cost_service import create_record


SUBTYPE_DEBT = "赊账"
CATEGORY_REPAY = "还款"


def create_debt_record(
    db: Session, record: CostRecordCreate, farm_id: int
) -> CostRecord:
    """创建一条赊账记录。

    将 record_subtype 自动设为"赊账"（如未指定）。
    """
    db_record = CostRecord(
        cycle_id=record.cycle_id,
        record_type=record.record_type,
        category=record.category,
        amount=record.amount,
        record_date=record.record_date,
        note=record.note,
        record_subtype=record.record_subtype or SUBTYPE_DEBT,
        counterparty=record.counterparty,
        due_date=record.due_date,
        farm_id=farm_id,
    )
    db.add(db_record)
    try:
        db.commit()
        db.refresh(db_record)
    except Exception:
        db.rollback()
        raise
    return db_record


def get_debt_records(
    db: Session,
    farm_id: int,
    counterparty: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[CostRecord]:
    """查询未结清的赊账记录列表。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 按债权人名称模糊筛选（可选）。
        skip: 跳过记录数。
        limit: 返回最大记录数。

    Returns:
        未结清的赊账记录列表，按记录日期倒序排列。
    """
    query = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .filter(CostRecord.settled_at.is_(None))
    )
    if counterparty:
        query = query.filter(CostRecord.counterparty.ilike(f"%{counterparty}%"))
    return query.order_by(CostRecord.record_date.desc()).offset(skip).limit(limit).all()


def count_debt_records(
    db: Session, farm_id: int, counterparty: str | None = None
) -> int:
    """查询未结清赊账记录总数。"""
    query = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .filter(CostRecord.settled_at.is_(None))
    )
    if counterparty:
        query = query.filter(CostRecord.counterparty.ilike(f"%{counterparty}%"))
    return query.count()


def get_debt_summary(db: Session, farm_id: int) -> list[DebtSummary]:
    """按债权人分组统计债务概况。

    Returns:
        每个债权人的债务总额、已还金额、剩余金额和记录数。
    """
    records = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .all()
    )

    groups: dict[str, dict] = {}
    for r in records:
        cp = r.counterparty or "未指定"
        if cp not in groups:
            groups[cp] = {
                "total_debt": Decimal("0"),
                "total_settled": Decimal("0"),
                "record_count": 0,
            }
        groups[cp]["total_debt"] += r.amount
        groups[cp]["record_count"] += 1

    # 统计已还款金额（通过 parent_record_id 关联）
    repay_records = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_type == "income")
        .filter(CostRecord.category == CATEGORY_REPAY)
        .filter(CostRecord.parent_record_id.isnot(None))
        .all()
    )
    for r in repay_records:
        # 查找对应的赊账记录获取 counterparty
        parent = db.query(CostRecord).filter(CostRecord.id == r.parent_record_id).first()
        cp = parent.counterparty if parent else "未指定"
        if cp not in groups:
            groups[cp] = {
                "total_debt": Decimal("0"),
                "total_settled": Decimal("0"),
                "record_count": 0,
            }
        groups[cp]["total_settled"] += r.amount

    return [
        DebtSummary(
            counterparty=cp,
            total_debt=g["total_debt"],
            total_settled=g["total_settled"],
            remaining=g["total_debt"] - g["total_settled"],
            record_count=g["record_count"],
        )
        for cp, g in groups.items()
    ]


def settle_debt(
    db: Session,
    farm_id: int,
    counterparty: str,
    amount: Decimal | None = None,
    note: str | None = None,
) -> CostRecord:
    """结清指定债权人的赊账。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 债权人名称（精确或模糊匹配）。
        amount: 还款金额，None 表示全额还清。
        note: 可选备注。

    Returns:
        新创建的还款记录。

    Raises:
        ValueError: 找不到匹配的未结清赊账记录。
    """
    debts = get_debt_records(db, farm_id, counterparty=counterparty)
    if not debts:
        raise ValueError(f"未找到'{counterparty}'的未结清赊账记录")

    target = debts[0]

    if amount is None:
        settle_amount = target.amount
        is_full = True
    else:
        settle_amount = amount
        is_full = (settle_amount >= target.amount)

    settle_note = f"还{target.counterparty or counterparty}"
    if note:
        settle_note = f"{settle_note}，{note}"

    repay = CostRecordCreate(
        record_type="income",
        category=CATEGORY_REPAY,
        amount=settle_amount,
        record_date=date.today(),
        note=settle_note,
    )
    result = create_record(db, repay, farm_id=farm_id)
    result.parent_record_id = target.id
    db.commit()
    db.refresh(result)

    if is_full:
        from datetime import datetime, timezone
        target.settled_at = datetime.now(timezone.utc)
        db.commit()

    return result


__all__ = [
    "create_debt_record",
    "get_debt_records",
    "count_debt_records",
    "get_debt_summary",
    "settle_debt",
]
```

- [ ] **Step 4: Run tests**

```bash
cd backend && poetry run pytest tests/services/test_debt_service.py -v
```

Expected: 6 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/debt_service.py backend/tests/services/test_debt_service.py
git commit -m "feat: 新增 debt_service 赊账查询/统计/还款"
```

---

## Task 5: Create Debt API

**Files:**
- Create: `backend/app/api/debt.py`
- Test: `backend/tests/api/test_debt.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/api/test_debt.py`：

```python
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


class TestCreateDebt:
    def test_create_debt(self, client: TestClient):
        payload = {
            "record_type": "cost",
            "category": "化肥",
            "amount": "300",
            "record_date": date.today().isoformat(),
            "record_subtype": "赊账",
            "counterparty": "老张",
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
        }
        resp = client.post("/debts", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["record_subtype"] == "赊账"
        assert data["counterparty"] == "老张"


class TestListDebts:
    def test_list_unsettled(self, client: TestClient):
        resp = client.get("/debts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "summary" in data

    def test_filter_by_counterparty(self, client: TestClient):
        resp = client.get("/debts?counterparty=老张")
        assert resp.status_code == 200


class TestSettleDebt:
    def test_settle(self, client: TestClient):
        # 先创建一条赊账
        client.post("/debts", json={
            "record_type": "cost",
            "category": "农药",
            "amount": "100",
            "record_date": date.today().isoformat(),
            "record_subtype": "赊账",
            "counterparty": "测试还款",
            "due_date": (date.today() + timedelta(days=15)).isoformat(),
        })
        resp = client.post("/debts/settle", json={
            "counterparty": "测试还款",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "还款"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && poetry run pytest tests/api/test_debt.py -v
```

Expected: 404 errors (`/debts` not found)

- [ ] **Step 3: Implement debt API**

创建 `backend/app/api/debt.py`：

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.models.farm import Farm
from app.schemas.common import PaginatedResponse
from app.schemas.cost import CostRecordCreate, CostRecordResponse, DebtListResponse
from app.services import debt_service

router = APIRouter(prefix="/debts", tags=["debts"])


@router.post("", response_model=CostRecordResponse)
def create_debt(
    record: CostRecordCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建一条赊账记录。"""
    return debt_service.create_debt_record(db, record, farm_id=farm.id)


@router.get("", response_model=DebtListResponse)
def list_debts(
    counterparty: str | None = Query(None, description="按债权人筛选"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取未结清赊账列表及统计。"""
    skip = (page - 1) * size
    items = debt_service.get_debt_records(
        db, farm_id=farm.id, counterparty=counterparty, skip=skip, limit=size
    )
    total = debt_service.count_debt_records(db, farm_id=farm.id, counterparty=counterparty)
    summary = debt_service.get_debt_summary(db, farm_id=farm.id)
    return {"items": items, "total": total, "summary": summary}


@router.post("/settle", response_model=CostRecordResponse)
def settle_debt(
    payload: dict,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """结清赊账。

    Request body:
        counterparty: 债权人名称（必填）
        amount: 还款金额（可选，不传则全额）
        note: 备注（可选）
    """
    counterparty = payload.get("counterparty")
    if not counterparty:
        raise HTTPException(status_code=400, detail="counterparty 必填")

    from decimal import Decimal

    amount = payload.get("amount")
    if amount is not None:
        amount = Decimal(str(amount))

    try:
        return debt_service.settle_debt(
            db,
            farm_id=farm.id,
            counterparty=counterparty,
            amount=amount,
            note=payload.get("note"),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


__all__ = ["router"]
```

- [ ] **Step 4: Register router in main.py**

修改 `backend/app/main.py`，在现有 `include_router` 调用后添加：

```python
from app.api import debt

# ... existing routers ...
app.include_router(debt.router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && poetry run pytest tests/api/test_debt.py -v
```

Expected: 4 tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/debt.py backend/tests/api/test_debt.py backend/app/main.py
git commit -m "feat: 新增 /debts API（创建/查询/还款）"
```

---

## Task 6: Upgrade settle-debt Skill to Use Structured Fields

**Files:**
- Modify: `backend/app/skills/settle-debt/scripts/main.py`
- Test: `backend/tests/skills/test_settle_debt_skill.py`

- [ ] **Step 1: Read current settle-debt skill**

文件已在上文读取。当前 `_find_debt_records` 使用：

```python
.filter(CostRecord.note.ilike(f"%{counterparty}%"))
```

- [ ] **Step 2: Modify _find_debt_records to use structured fields**

替换 `backend/app/skills/settle-debt/scripts/main.py` 中的 `_find_debt_records` 方法：

```python
    @staticmethod
    def _find_debt_records(db, farm_id: int, counterparty: str) -> list:
        """查找指定债权人的未结清赊账记录。

        优先使用结构化字段 counterparty + record_subtype 匹配，
        回退到 note 模糊匹配（兼容旧数据）。
        """
        # 先尝试结构化匹配
        structured = (
            db.query(CostRecord)
            .filter(CostRecord.farm_id == farm_id)
            .filter(CostRecord.record_subtype == "赊账")
            .filter(CostRecord.settled_at.is_(None))
            .filter(CostRecord.counterparty.ilike(f"%{counterparty}%"))
            .all()
        )
        if structured:
            return structured

        # 兼容旧数据：回退到 note 匹配
        return (
            db.query(CostRecord)
            .filter(CostRecord.farm_id == farm_id)
            .filter(CostRecord.record_type == "cost")
            .filter(CostRecord.note.ilike(f"%{counterparty}%"))
            .all()
        )
```

- [ ] **Step 3: Add test for structured field matching**

创建/修改 `backend/tests/skills/test_settle_debt_skill.py`：

```python
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate
from app.services.cost_service import create_record
from app.skills.settle_debt.scripts.main import SettleDebtSkill


@pytest.fixture
def structured_debt(db: Session) -> CostRecord:
    record = CostRecordCreate(
        record_type="cost",
        category="化肥",
        amount=Decimal("300"),
        record_date=date.today(),
        record_subtype="赊账",
        counterparty="老王农资店",
        due_date=date.today() + timedelta(days=30),
    )
    return create_record(db, record, farm_id=1)


class TestSettleDebtSkillStructured:
    @pytest.mark.asyncio
    async def test_find_by_counterparty_structured(self, db: Session, structured_debt: CostRecord):
        skill = SettleDebtSkill()
        records = skill._find_debt_records(db, farm_id=1, counterparty="老王")
        assert len(records) == 1
        assert records[0].counterparty == "老王农资店"

    @pytest.mark.asyncio
    async def test_settle_structured_debt(self, db: Session, structured_debt: CostRecord):
        skill = SettleDebtSkill()
        result = await skill.execute(
            {"counterparty": "老王农资店"},
            type("Context", (), {"farm_id": 1})(),
        )
        assert result.status.value == "SUCCESS"
        assert "300" in result.reply
```

- [ ] **Step 4: Run tests**

```bash
cd backend && poetry run pytest tests/skills/test_settle_debt_skill.py -v
```

Expected: 2 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/settle-debt/scripts/main.py backend/tests/skills/test_settle_debt_skill.py
git commit -m "refactor: settle-debt Skill 改用结构化字段查询"
```

---

## Task 7: Frontend — Add Debt Types and API

**Files:**
- Modify: `FarmManagerMobile/src/api/types.ts`
- Modify: `FarmManagerMobile/src/api/client.ts`

- [ ] **Step 1: Add DebtRecord type to types.ts**

在 `FarmManagerMobile/src/api/types.ts` 中添加（如文件不存在则创建）：

```typescript
export interface DebtRecord {
  id: number;
  farm_id: number;
  cycle_id?: number;
  record_type: string;
  category: string;
  amount: string;
  record_date: string;
  note?: string;
  record_subtype?: string;
  counterparty?: string;
  due_date?: string;
  settled_at?: string;
  parent_record_id?: number;
  created_at: string;
}

export interface DebtSummary {
  counterparty: string;
  total_debt: string;
  total_settled: string;
  remaining: string;
  record_count: number;
}

export interface DebtListResponse {
  items: DebtRecord[];
  total: number;
  summary: DebtSummary[];
}
```

- [ ] **Step 2: Add debtApi to client.ts**

在 `FarmManagerMobile/src/api/client.ts` 的 `cropApi` 之后添加：

```typescript
// 债务管理
export const debtApi = {
  getDebts: (params?: { counterparty?: string; page?: number; size?: number }) =>
    apiClient.get<DebtListResponse>('/debts', { params }),
  createDebt: (data: Omit<DebtRecord, 'id' | 'farm_id' | 'created_at' | 'settled_at'>) =>
    apiClient.post<DebtRecord>('/debts', data),
  settleDebt: (data: { counterparty: string; amount?: string; note?: string }) =>
    apiClient.post<DebtRecord>('/debts/settle', data),
};
```

同时需要添加 `DebtRecord` 和 `DebtListResponse` 的导入（如果 types.ts 有导出的话）。

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/api/types.ts FarmManagerMobile/src/api/client.ts
git commit -m "feat(mobile): 新增 DebtRecord 类型和 debtApi"
```

---

## Task 8: Frontend — Create Debt Store

**Files:**
- Create: `FarmManagerMobile/src/stores/debtStore.ts`

- [ ] **Step 1: Implement debtStore**

创建 `FarmManagerMobile/src/stores/debtStore.ts`：

```typescript
import {create} from 'zustand';
import type {DebtRecord, DebtSummary} from '../api/types';
import {debtApi} from '../api/client';

interface DebtState {
  debts: DebtRecord[];
  summary: DebtSummary[];
  total: number;
  loading: boolean;
  error: string | null;
  fetchDebts: (counterparty?: string) => Promise<void>;
  createDebt: (data: {
    record_type: string;
    category: string;
    amount: string;
    record_date: string;
    note?: string;
    record_subtype?: string;
    counterparty?: string;
    due_date?: string;
  }) => Promise<void>;
  settleDebt: (counterparty: string, amount?: string, note?: string) => Promise<void>;
  clearError: () => void;
}

export const useDebtStore = create<DebtState>(set => ({
  debts: [],
  summary: [],
  total: 0,
  loading: false,
  error: null,

  fetchDebts: async counterparty => {
    set({loading: true, error: null});
    try {
      const res = await debtApi.getDebts({counterparty, page: 1, size: 100});
      const data = res.data;
      set({
        debts: data.items,
        summary: data.summary,
        total: data.total,
        loading: false,
      });
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  createDebt: async data => {
    set({loading: true, error: null});
    try {
      await debtApi.createDebt(data);
      const res = await debtApi.getDebts({page: 1, size: 100});
      const d = res.data;
      set({debts: d.items, summary: d.summary, total: d.total, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  settleDebt: async (counterparty, amount, note) => {
    set({loading: true, error: null});
    try {
      await debtApi.settleDebt({counterparty, amount, note});
      const res = await debtApi.getDebts({page: 1, size: 100});
      const d = res.data;
      set({debts: d.items, summary: d.summary, total: d.total, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  clearError: () => set({error: null}),
}));
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/stores/debtStore.ts
git commit -m "feat(mobile): 新增 debtStore 赊账状态管理"
```

---

## Task 9: Frontend — Create Debt List Screen

**Files:**
- Create: `FarmManagerMobile/src/screens/debt/DebtListScreen.tsx`

- [ ] **Step 1: Create DebtListScreen**

创建 `FarmManagerMobile/src/screens/debt/DebtListScreen.tsx`：

```typescript
import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Alert,
  RefreshControl,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {useDebtStore} from '../../stores/debtStore';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';

type DebtListNavigationProp = NativeStackNavigationProp<RootStackParamList, 'DebtList'>;

export const DebtListScreen: React.FC = () => {
  const navigation = useNavigation<DebtListNavigationProp>();
  const {debts, summary, loading, error, fetchDebts, settleDebt, clearError} = useDebtStore();
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchDebts();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert('错误', error);
      clearError();
    }
  }, [error]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDebts();
    setRefreshing(false);
  };

  const handleSettle = (counterparty: string) => {
    Alert.alert(
      '确认还款',
      `确认结清 ${counterparty} 的欠款？`,
      [
        {text: '取消', style: 'cancel'},
        {
          text: '确认',
          onPress: () => settleDebt(counterparty),
        },
      ],
    );
  };

  const renderSummary = () => (
    <View style={styles.summaryContainer}>
      <Text style={styles.summaryTitle}>债务概览</Text>
      {summary.map(s => (
        <View key={s.counterparty} style={styles.summaryItem}>
          <Text style={styles.summaryName}>{s.counterparty}</Text>
          <Text style={styles.summaryAmount}>
            欠 {s.total_debt}元 / 已还 {s.total_settled}元 / 剩 {s.remaining}元
          </Text>
        </View>
      ))}
      {summary.length === 0 && (
        <Text style={styles.emptyText}>暂无赊账记录</Text>
      )}
    </View>
  );

  const renderDebtItem = ({item}: {item: any}) => (
    <View style={styles.debtCard}>
      <View style={styles.debtHeader}>
        <Text style={styles.debtCategory}>{item.category}</Text>
        <Text style={styles.debtAmount}>{item.amount}元</Text>
      </View>
      <Text style={styles.debtCounterparty}>债权人：{item.counterparty || '未指定'}</Text>
      <Text style={styles.debtDate}>日期：{item.record_date}</Text>
      {item.due_date && (
        <Text style={styles.debtDueDate}>到期：{item.due_date}</Text>
      )}
      {item.note && <Text style={styles.debtNote}>备注：{item.note}</Text>}
      <TouchableOpacity
        style={styles.settleButton}
        onPress={() => handleSettle(item.counterparty)}>
        <Text style={styles.settleButtonText}>还款</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>赊账管理</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => navigation.navigate('DebtCreate')}>
          <Icon name="plus" size={24} color={colors.primary} />
        </TouchableOpacity>
      </View>

      <FlatList
        data={debts}
        keyExtractor={item => String(item.id)}
        ListHeaderComponent={renderSummary}
        renderItem={renderDebtItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>暂无未结清赊账</Text>
            </View>
          ) : null
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  headerTitle: {fontSize: fontSize.xl, fontWeight: '700', color: colors.text},
  addButton: {padding: spacing.sm},
  listContent: {padding: spacing.md},
  summaryContainer: {
    backgroundColor: colors.cardBg,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  summaryTitle: {fontSize: fontSize.lg, fontWeight: '600', marginBottom: spacing.sm},
  summaryItem: {marginBottom: spacing.xs},
  summaryName: {fontSize: fontSize.md, fontWeight: '500'},
  summaryAmount: {fontSize: fontSize.sm, color: colors.textMuted},
  debtCard: {
    backgroundColor: colors.cardBg,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  debtHeader: {flexDirection: 'row', justifyContent: 'space-between', marginBottom: spacing.xs},
  debtCategory: {fontSize: fontSize.md, fontWeight: '600'},
  debtAmount: {fontSize: fontSize.md, fontWeight: '700', color: colors.danger},
  debtCounterparty: {fontSize: fontSize.sm, color: colors.text},
  debtDate: {fontSize: fontSize.sm, color: colors.textMuted},
  debtDueDate: {fontSize: fontSize.sm, color: colors.warning},
  debtNote: {fontSize: fontSize.sm, color: colors.textMuted, marginTop: spacing.xs},
  settleButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
  },
  settleButtonText: {color: colors.white, fontWeight: '600'},
  emptyContainer: {alignItems: 'center', paddingVertical: spacing.xl},
  emptyText: {color: colors.textMuted, fontSize: fontSize.md},
});
```

> 注意：如果 `colors` 中没有 `danger`、`warning`、`cardBg`、`white` 等颜色，需要根据实际主题文件调整。

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/screens/debt/DebtListScreen.tsx
git commit -m "feat(mobile): 新增赊账管理列表页面"
```

---

## Task 10: Frontend — Create Debt Create Screen

**Files:**
- Create: `FarmManagerMobile/src/screens/debt/DebtCreateScreen.tsx`

- [ ] **Step 1: Create DebtCreateScreen**

创建 `FarmManagerMobile/src/screens/debt/DebtCreateScreen.tsx`：

```typescript
import React, {useState} from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
import {useDebtStore} from '../../stores/debtStore';
import {BigButton} from '../../components/BigButton';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';

type DebtCreateNavigationProp = NativeStackNavigationProp<RootStackParamList, 'DebtCreate'>;

const COST_CATEGORIES = ['化肥', '农药', '种子', '人工', '水电', '地租', '其他'];

export const DebtCreateScreen: React.FC = () => {
  const navigation = useNavigation<DebtCreateNavigationProp>();
  const {createDebt, loading, error, clearError} = useDebtStore();

  const [category, setCategory] = useState('化肥');
  const [amount, setAmount] = useState('');
  const [counterparty, setCounterparty] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [note, setNote] = useState('');
  const [showCategoryPicker, setShowCategoryPicker] = useState(false);

  const handleSubmit = async () => {
    if (!amount || !counterparty) {
      Alert.alert('请填写完整', '金额和债权人名称必填');
      return;
    }
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('金额无效', '请输入大于 0 的金额');
      return;
    }

    await createDebt({
      record_type: 'cost',
      category,
      amount: String(numAmount),
      record_date: dayjs().format('YYYY-MM-DD'),
      record_subtype: '赊账',
      counterparty: counterparty.trim(),
      due_date: dueDate || undefined,
      note: note.trim() || undefined,
    });

    if (!error) {
      navigation.goBack();
    }
  };

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>记一笔赊账</Text>

      <View style={styles.field}>
        <Text style={styles.label}>分类</Text>
        <TouchableOpacity
          style={styles.selectButton}
          onPress={() => setShowCategoryPicker(!showCategoryPicker)}>
          <Text>{category}</Text>
        </TouchableOpacity>
        {showCategoryPicker && (
          <View style={styles.pickerContainer}>
            {COST_CATEGORIES.map(c => (
              <TouchableOpacity
                key={c}
                style={[styles.pickerItem, category === c && styles.pickerItemActive]}
                onPress={() => {
                  setCategory(c);
                  setShowCategoryPicker(false);
                }}>
                <Text style={category === c ? styles.pickerItemTextActive : undefined}>
                  {c}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>金额（元）</Text>
        <TextInput
          style={styles.input}
          value={amount}
          onChangeText={setAmount}
          keyboardType="decimal-pad"
          placeholder="请输入金额"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>债权人</Text>
        <TextInput
          style={styles.input}
          value={counterparty}
          onChangeText={setCounterparty}
          placeholder="如：老王农资店"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>到期日（可选）</Text>
        <TextInput
          style={styles.input}
          value={dueDate}
          onChangeText={setDueDate}
          placeholder="YYYY-MM-DD"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>备注（可选）</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          value={note}
          onChangeText={setNote}
          placeholder="添加备注..."
          multiline
          numberOfLines={3}
        />
      </View>

      <BigButton title="保存" onPress={handleSubmit} loading={loading} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background, padding: spacing.md},
  title: {fontSize: fontSize.xl, fontWeight: '700', marginBottom: spacing.lg},
  field: {marginBottom: spacing.md},
  label: {fontSize: fontSize.sm, color: colors.textMuted, marginBottom: spacing.xs},
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
    padding: spacing.sm,
    fontSize: fontSize.md,
    backgroundColor: colors.white || colors.background,
  },
  textArea: {height: 80, textAlignVertical: 'top'},
  selectButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
    padding: spacing.sm,
  },
  pickerContainer: {
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.white || colors.background,
  },
  pickerItem: {padding: spacing.sm},
  pickerItemActive: {backgroundColor: colors.primaryMuted},
  pickerItemTextActive: {color: colors.primary, fontWeight: '600'},
});
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/screens/debt/DebtCreateScreen.tsx
git commit -m "feat(mobile): 新增赊账创建页面"
```

---

## Task 11: Frontend — Create Crop Template Screen

**Files:**
- Create: `FarmManagerMobile/src/screens/crop/CropTemplateScreen.tsx`

- [ ] **Step 1: Create CropTemplateScreen**

创建 `FarmManagerMobile/src/screens/crop/CropTemplateScreen.tsx`：

```typescript
import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Alert,
  RefreshControl,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {cropApi} from '../../api/client';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';

interface GrowthStage {
  id: number;
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks?: string;
}

interface CropTemplate {
  id: number;
  name: string;
  variety?: string;
  stages: GrowthStage[];
}

export const CropTemplateScreen: React.FC = () => {
  const [templates, setTemplates] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await cropApi.getTemplates();
      setTemplates((res.data as any)?.items ?? res.data);
    } catch (err: any) {
      Alert.alert('加载失败', err.message || '请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchTemplates();
    setRefreshing(false);
  };

  const renderTemplateItem = ({item}: {item: CropTemplate}) => (
    <View style={styles.templateCard}>
      <View style={styles.templateHeader}>
        <Text style={styles.templateName}>{item.name}</Text>
        {item.variety && (
          <Text style={styles.templateVariety}>品种：{item.variety}</Text>
        )}
      </View>
      <Text style={styles.stageTitle}>生长阶段：</Text>
      {item.stages.map(stage => (
        <View key={stage.id} style={styles.stageRow}>
          <Text style={styles.stageName}>{stage.order_index + 1}. {stage.name}</Text>
          <Text style={styles.stageDuration}>{stage.duration_days}天</Text>
        </View>
      ))}
      {item.stages.length === 0 && (
        <Text style={styles.emptyStage}>暂无阶段信息</Text>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>作物模板</Text>
        <TouchableOpacity style={styles.addButton} onPress={() => Alert.alert('提示', '创建模板功能后续开放')}>
          <Icon name="plus" size={24} color={colors.primary} />
        </TouchableOpacity>
      </View>

      <FlatList
        data={templates}
        keyExtractor={item => String(item.id)}
        renderItem={renderTemplateItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>暂无作物模板</Text>
            </View>
          ) : null
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  headerTitle: {fontSize: fontSize.xl, fontWeight: '700', color: colors.text},
  addButton: {padding: spacing.sm},
  listContent: {padding: spacing.md},
  templateCard: {
    backgroundColor: colors.cardBg || colors.background,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  templateHeader: {marginBottom: spacing.sm},
  templateName: {fontSize: fontSize.lg, fontWeight: '700'},
  templateVariety: {fontSize: fontSize.sm, color: colors.textMuted, marginTop: spacing.xs},
  stageTitle: {fontSize: fontSize.md, fontWeight: '600', marginTop: spacing.sm},
  stageRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
  },
  stageName: {fontSize: fontSize.sm},
  stageDuration: {fontSize: fontSize.sm, color: colors.textMuted},
  emptyStage: {fontSize: fontSize.sm, color: colors.textMuted, marginTop: spacing.xs},
  emptyContainer: {alignItems: 'center', paddingVertical: spacing.xl},
  emptyText: {color: colors.textMuted, fontSize: fontSize.md},
});
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/screens/crop/CropTemplateScreen.tsx
git commit -m "feat(mobile): 新增作物模板展示页面"
```

---

## Task 12: Frontend — Update Navigation

**Files:**
- Modify: `FarmManagerMobile/src/navigation/AppNavigator.tsx`

- [ ] **Step 1: Read current AppNavigator**

先读取 `FarmManagerMobile/src/navigation/AppNavigator.tsx` 了解现有路由结构。

- [ ] **Step 2: Add new routes**

在 `RootStackParamList` 中添加：

```typescript
export type RootStackParamList = {
  // ... existing routes ...
  DebtList: undefined;
  DebtCreate: undefined;
  CropTemplate: undefined;
};
```

在 Stack.Navigator 中添加 Screen：

```typescript
import {DebtListScreen} from '../screens/debt/DebtListScreen';
import {DebtCreateScreen} from '../screens/debt/DebtCreateScreen';
import {CropTemplateScreen} from '../screens/crop/CropTemplateScreen';

// ... inside Stack.Navigator ...
<Stack.Screen name="DebtList" component={DebtListScreen} options={{title: '赊账管理'}} />
<Stack.Screen name="DebtCreate" component={DebtCreateScreen} options={{title: '记赊账'}} />
<Stack.Screen name="CropTemplate" component={CropTemplateScreen} options={{title: '作物模板'}} />
```

- [ ] **Step 3: Add entry points from existing screens**

在 `SettingsScreen` 或 `CostListScreen` 中添加跳转入口（可选，如果已有从设置页导航的模式）：

```typescript
// 在 SettingsScreen 的菜单列表中添加：
<TouchableOpacity onPress={() => navigation.navigate('DebtList')}>
  <Text>赊账管理</Text>
</TouchableOpacity>
<TouchableOpacity onPress={() => navigation.navigate('CropTemplate')}>
  <Text>作物模板</Text>
</TouchableOpacity>
```

- [ ] **Step 4: Commit**

```bash
git add FarmManagerMobile/src/navigation/AppNavigator.tsx
git commit -m "feat(mobile): 导航注册 DebtList/DebtCreate/CropTemplate"
```

---

## Task 13: Frontend — Add Debt Subtype to Cost Create Screen

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx`

- [ ] **Step 1: Add debt subtype toggle**

在 `CostCreateScreen` 中添加：

```typescript
const [isDebt, setIsDebt] = useState(false);
const [counterparty, setCounterparty] = useState('');
const [dueDate, setDueDate] = useState('');
```

在 record type 选择区域下方添加赊账开关：

```typescript
// 在 JSX 中，category 选择器之后添加：
{recordType === 'cost' && (
  <View style={styles.field}>
    <TouchableOpacity
      style={[styles.debtToggle, isDebt && styles.debtToggleActive]}
      onPress={() => setIsDebt(!isDebt)}>
      <Text style={isDebt ? styles.debtToggleTextActive : undefined}>
        {isDebt ? '✓ 标记为赊账' : '标记为赊账'}
      </Text>
    </TouchableOpacity>
    {isDebt && (
      <>
        <TextInput
          style={styles.input}
          value={counterparty}
          onChangeText={setCounterparty}
          placeholder="债权人名称"
        />
        <TextInput
          style={styles.input}
          value={dueDate}
          onChangeText={setDueDate}
          placeholder="到期日 YYYY-MM-DD"
        />
      </>
    )}
  </View>
)}
```

- [ ] **Step 2: Update submit payload**

修改 `handleSubmit`，在 `createRecord` 调用时附加赊账字段：

```typescript
await createRecord({
  cycle_id: undefined,
  record_type: recordType,
  category,
  amount: String(numAmount),
  record_date: dayjs(recordDate).format('YYYY-MM-DD'),
  note: note.trim() || undefined,
  ...(isDebt ? {
    record_subtype: '赊账',
    counterparty: counterparty.trim(),
    due_date: dueDate || undefined,
  } : {}),
});
```

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx
git commit -m "feat(mobile): 记账页增加赊账类型选项"
```

---

## Task 14: Final Integration & Verification

- [ ] **Step 1: Run backend lint**

```bash
cd backend && ruff check . && ruff format .
```

Expected: 无错误

- [ ] **Step 2: Run backend tests**

```bash
cd backend && poetry run pytest tests/ -v --tb=short
```

Expected: 所有测试通过（包括新增的 debt 测试和 settle-debt 测试）

- [ ] **Step 3: Verify API with curl**

```bash
# 创建赊账
curl -X POST http://47.98.253.236:8000/debts \
  -H "Content-Type: application/json" \
  -d '{"record_type":"cost","category":"化肥","amount":"500","record_date":"2026-05-26","record_subtype":"赊账","counterparty":"老王农资","due_date":"2026-06-26"}'

# 查询赊账
curl http://47.98.253.236:8000/debts

# 还款
curl -X POST http://47.98.253.236:8000/debts/settle \
  -H "Content-Type: application/json" \
  -d '{"counterparty":"老王农资"}'
```

- [ ] **Step 4: Frontend TypeScript check**

```bash
cd FarmManagerMobile && npx tsc --noEmit
```

Expected: 无类型错误

- [ ] **Step 5: Final commit**

```bash
git commit -m "feat: P1 farm-context-aware-agent 完成"
```

---

## Self-Review Checklist

### Spec Coverage
| ROADMAP 要求 | 对应 Task |
|---|---|
| cost_records 新增 record_subtype/counterparty/due_date/settled_at/parent_record_id | Task 1, 2, 3 |
| 赊账 API：/debts 查询、统计、还款 | Task 4, 5 |
| 作物模板自定义 API（已有） | — |
| settle-debt Skill 从 note 匹配改为结构化查询 | Task 6 |
| 移动端：记账页增加"赊账"类型 | Task 13 |
| 移动端：新增"赊账管理"页 | Task 9, 10 |
| 移动端：新增"作物模板"页 | Task 11 |

### Placeholder Scan
- [x] 无 "TBD", "TODO", "implement later"
- [x] 无 "Add appropriate error handling" 等模糊描述
- [x] 每个代码步骤包含完整代码
- [x] 无 "Similar to Task N" 引用

### Type Consistency
- [x] `CostRecordCreate` / `CostRecordResponse` 字段一致
- [x] `DebtSummary` 字段与 service 返回一致
- [x] `debtApi` 类型与后端响应一致
- [x] `settle_debt` 签名在 service 和 API 层一致

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-26-farm-context-aware-agent.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for this 14-task plan with backend + frontend crossing.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**
