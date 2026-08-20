# Simplify Ledger Settlement Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing lightweight ledger distinguish occurred amount, settled amount, and unsettled balance without introducing a full accounting system.

**Architecture:** Keep `cost_records` as the single ledger table and add minimal settlement fields. Backend services become the source of truth for settlement defaults, debt settlement, labor cost settlement sync, and summary calculations; mobile UI consumes those fields for clearer totals and labels.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Pydantic, pytest, React Native, TypeScript, Zustand, Jest.

---

## File Structure

**Backend model and schema**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/models/cost.py`
  Add `settled_amount`, `settlement_status`, and `unsettled_amount` property.
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/schemas/cost.py`
  Add settlement fields to create/update/response schemas, validators, and summary response models.
- Create: `/Users/ljn/Documents/demo/explore/backend/alembic/versions/e7b2c4d6f8a3_add_cost_settlement_status.py`
  Idempotent migration after `e7b2c4d6f8a2`.

**Backend services and APIs**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/cost_service.py`
  Centralize settlement defaults, status calculation, summary aggregation, and old repayment exclusion.
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/debt_service.py`
  Create unsettled payable/receivable records and update original records on settlement.
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/api/debt.py`
  Keep current payload shape; return updated original `CostRecord`; keep `/debts` route names for compatibility while business labels distinguish payable and receivable by `record_type`.
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/labor_service.py`
  Sync labor cost record `settled_amount` from labor paid amount.
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/report_data_service.py`
  Exclude legacy repayment records from income totals.

**Backend tests**
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/test_cost.py`
  Test settlement defaults and summaries.
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_debt.py`
  Test debt creation, full settlement, partial settlement, and no ordinary income repayment.
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_planting_operations.py`
  Test labor cost settlement fields.

**Mobile types, utilities, and UI**
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/api/types.ts`
  Add settlement fields to `CostRecord`.
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/utils/recordDisplay.ts`
  Add settlement helpers and filters.
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/utils/__tests__/recordDisplay.test.ts`
  Test settlement helper output.
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/components/RecordItem.tsx`
  Display unpaid/partial labels and remaining amount.
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/components/RecordDetailModal.tsx`
  Display settled and unsettled amounts.
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/CostListScreen.tsx`
  Change summary cards to occurred/settled/unsettled wording.

---

### Task 1: Backend Settlement Fields and Defaults

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/models/cost.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/schemas/cost.py`
- Create: `/Users/ljn/Documents/demo/explore/backend/alembic/versions/e7b2c4d6f8a3_add_cost_settlement_status.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/test_cost.py`

- [ ] **Step 1: Write failing API tests for settlement defaults**

Append these tests to `/Users/ljn/Documents/demo/explore/backend/tests/test_cost.py`:

```python
def test_create_settled_cost_record_defaults_settlement_fields(cycle_id):
    payload = {
        "cycle_id": cycle_id,
        "record_type": "cost",
        "category": "肥料",
        "amount": "100.00",
        "record_date": "2025-03-10",
    }

    response = client.post("/costs", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "100.00"
    assert data["settled_amount"] == "100.00"
    assert data["unsettled_amount"] == "0.00"
    assert data["settlement_status"] == "settled"


def test_create_record_rejects_settled_amount_greater_than_amount(cycle_id):
    payload = {
        "cycle_id": cycle_id,
        "record_type": "cost",
        "category": "肥料",
        "amount": "100.00",
        "settled_amount": "120.00",
        "record_date": "2025-03-10",
    }

    response = client.post("/costs", json=payload)

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/test_cost.py::test_create_settled_cost_record_defaults_settlement_fields tests/test_cost.py::test_create_record_rejects_settled_amount_greater_than_amount -v
```

Expected: first test fails because `settled_amount` is missing from the response; second may fail because the schema does not validate the new field yet.

- [ ] **Step 3: Add model fields and derived unsettled amount**

In `/Users/ljn/Documents/demo/explore/backend/app/models/cost.py`, update imports and `CostRecord`:

```python
class CostRecord(Base):
    """成本记账模型，记录种植周期中的成本与收入。"""

    __tablename__ = "cost_records"
    __table_args__ = (
        UniqueConstraint(
            "farm_id",
            "source_type",
            "source_id",
            "source_active_key",
            name="uq_cost_records_active_source",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    record_type = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    category_id = Column(Integer, ForeignKey("cost_categories.id"), nullable=True)
    category_name_snapshot = Column(String(50), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    settled_amount = Column(Numeric(10, 2), nullable=False, default=0)
    settlement_status = Column(String(20), nullable=False, default="settled")
    record_date = Column(Date, nullable=False)
    note = Column(String(500), nullable=True)
    record_subtype = Column(String(50), nullable=True)
    counterparty = Column(String(100), nullable=True)
    due_date = Column(Date, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    parent_record_id = Column(Integer, ForeignKey("cost_records.id"), nullable=True)
    source_type = Column(String(50), nullable=True)
    source_id = Column(Integer, nullable=True)
    source_active_key = Column(String(20), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category_ref = relationship("CostCategory", foreign_keys=[category_id])

    @property
    def unsettled_amount(self):
        """返回尚未结算金额。"""
        return max((self.amount or 0) - (self.settled_amount or 0), 0)
```

Keep the existing `source_label` property and `_sync_source_active_key` listener below this block.

- [ ] **Step 4: Add schema fields and validators**

In `/Users/ljn/Documents/demo/explore/backend/app/schemas/cost.py`, add constants below `RECORD_TYPE_ENUM`:

```python
SETTLEMENT_STATUS_ENUM = {"unsettled", "partial", "settled"}
```

Add fields to `CostRecordBase` after `amount`:

```python
    settled_amount: Decimal | None = Field(None, ge=0, le=10_000_000)
    settlement_status: str | None = Field(None, max_length=20)
```

Add validators to `CostRecordBase`:

```python
    @field_validator("settlement_status")
    @classmethod
    def _validate_settlement_status(cls, v: str | None) -> str | None:
        if v is not None and v not in SETTLEMENT_STATUS_ENUM:
            raise ValueError(f"settlement_status 必须是 {SETTLEMENT_STATUS_ENUM} 之一")
        return v

    @field_validator("settled_amount")
    @classmethod
    def _validate_settled_amount_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("settled_amount 最多保留两位小数")
        return v
```

Override `CostRecordCreate` to validate `settled_amount <= amount`:

```python
class CostRecordCreate(CostRecordBase):
    """创建成本记账记录请求 Schema。"""

    @field_validator("settled_amount")
    @classmethod
    def _validate_settled_not_over_amount(
        cls, v: Decimal | None, info
    ) -> Decimal | None:
        amount = info.data.get("amount")
        if v is not None and amount is not None and v > amount:
            raise ValueError("settled_amount 不能大于 amount")
        return v
```

Add fields to `CostRecordResponse`:

```python
    settled_amount: Decimal
    settlement_status: str
    unsettled_amount: Decimal
```

Add the same optional fields and validators to `CostRecordUpdate`:

```python
    settled_amount: Decimal | None = Field(None, ge=0, le=10_000_000)
    settlement_status: str | None = Field(None, max_length=20)
```

```python
    @field_validator("settled_amount")
    @classmethod
    def _validate_settled_amount_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("settled_amount 最多保留两位小数")
        return v

    @field_validator("settlement_status")
    @classmethod
    def _validate_settlement_status(cls, v: str | None) -> str | None:
        if v is not None and v not in SETTLEMENT_STATUS_ENUM:
            raise ValueError(f"settlement_status 必须是 {SETTLEMENT_STATUS_ENUM} 之一")
        return v
```

- [ ] **Step 5: Add Alembic migration**

Create `/Users/ljn/Documents/demo/explore/backend/alembic/versions/e7b2c4d6f8a3_add_cost_settlement_status.py`:

```python
"""add cost settlement status

Revision ID: e7b2c4d6f8a3
Revises: e7b2c4d6f8a2
Create Date: 2026-06-05 16:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "e7b2c4d6f8a3"
down_revision: Union[str, None] = "e7b2c4d6f8a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "cost_records" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("cost_records")}
    if "settled_amount" not in columns:
        op.add_column(
            "cost_records",
            sa.Column(
                "settled_amount",
                sa.Numeric(10, 2),
                nullable=False,
                server_default="0",
            ),
        )
    if "settlement_status" not in columns:
        op.add_column(
            "cost_records",
            sa.Column(
                "settlement_status",
                sa.String(length=20),
                nullable=False,
                server_default="settled",
            ),
        )

    bind.execute(
        text(
            """
            UPDATE cost_records
            SET settled_amount = amount,
                settlement_status = 'settled'
            WHERE deleted_at IS NULL
              AND (
                  record_subtype IS NULL
                  OR record_subtype != '赊账'
                  OR settled_at IS NOT NULL
              )
            """
        )
    )
    bind.execute(
        text(
            """
            UPDATE cost_records
            SET settled_amount = 0,
                settlement_status = 'unsettled'
            WHERE deleted_at IS NULL
              AND record_subtype = '赊账'
              AND settled_at IS NULL
            """
        )
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "cost_records" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("cost_records")}
    if "settlement_status" in columns:
        op.drop_column("cost_records", "settlement_status")
    if "settled_amount" in columns:
        op.drop_column("cost_records", "settled_amount")
```

- [ ] **Step 6: Default settlement fields in cost creation**

In `/Users/ljn/Documents/demo/explore/backend/app/services/cost_service.py`, add helper functions near constants:

```python
SETTLED = "settled"
PARTIAL = "partial"
UNSETTLED = "unsettled"


def _quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def settlement_status_for(amount: Decimal, settled_amount: Decimal) -> str:
    amount = _quantize_money(amount)
    settled_amount = _quantize_money(settled_amount)
    if settled_amount <= 0:
        return UNSETTLED
    if settled_amount >= amount:
        return SETTLED
    return PARTIAL


def default_settled_amount(record: CostRecordCreate) -> Decimal:
    if record.settled_amount is not None:
        return _quantize_money(record.settled_amount)
    if record.record_subtype == "赊账":
        return Decimal("0.00")
    return _quantize_money(record.amount)
```

In `create_record`, before `db_record = CostRecord(...)`, add:

```python
    settled_amount = default_settled_amount(record)
    settlement_status = record.settlement_status or settlement_status_for(
        record.amount,
        settled_amount,
    )
```

Add fields to `CostRecord(...)`:

```python
        settled_amount=settled_amount,
        settlement_status=settlement_status,
```

- [ ] **Step 7: Run tests and verify Task 1 passes**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/test_cost.py::test_create_settled_cost_record_defaults_settlement_fields tests/test_cost.py::test_create_record_rejects_settled_amount_greater_than_amount -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/models/cost.py backend/app/schemas/cost.py backend/app/services/cost_service.py backend/alembic/versions/e7b2c4d6f8a3_add_cost_settlement_status.py backend/tests/test_cost.py
git commit -m "feat: add ledger settlement fields"
```

---

### Task 2: Payable and Receivable Settlement Updates Original Ledger Record

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/debt_service.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_debt.py`

- [ ] **Step 1: Replace debt API tests with settlement-state expectations**

In `/Users/ljn/Documents/demo/explore/backend/tests/api/test_debt.py`, update `TestCreateDebt.test_create_debt` assertions:

```python
        assert data["record_subtype"] == "赊账"
        assert data["counterparty"] == "老张"
        assert Decimal(data["amount"]) == Decimal("300")
        assert Decimal(data["settled_amount"]) == Decimal("0")
        assert Decimal(data["unsettled_amount"]) == Decimal("300")
        assert data["settlement_status"] == "unsettled"
```

Update `TestSettleDebt.test_settle_full` assertions:

```python
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "农药"
        assert Decimal(data["amount"]) == Decimal("100")
        assert Decimal(data["settled_amount"]) == Decimal("100")
        assert Decimal(data["unsettled_amount"]) == Decimal("0")
        assert data["settlement_status"] == "settled"
        assert data["settled_at"] is not None
```

Update `TestSettleDebt.test_settle_partial` assertions:

```python
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "种子"
        assert Decimal(data["amount"]) == Decimal("500")
        assert Decimal(data["settled_amount"]) == Decimal("200")
        assert Decimal(data["unsettled_amount"]) == Decimal("300")
        assert data["settlement_status"] == "partial"
        assert data["settled_at"] is None
```

Add this test to `TestSettleDebt`:

```python
    def test_settle_debt_does_not_create_income_record(self):
        """还款只更新原赊账，不创建普通收入记录。"""
        client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "农药",
                "amount": "80",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "不进收入测试",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        )

        resp = client.post(
            "/debts/settle",
            json={"counterparty": "不进收入测试", "amount": "80"},
        )
        records = client.get("/costs").json()["items"]

        assert resp.status_code == 200
        assert [
            item
            for item in records
            if item["record_type"] == "income" and item["category"] == "还款"
        ] == []
```

Add this receivable settlement test to `TestSettleDebt`:

```python
    def test_settle_receivable_income_updates_original_record(self):
        """收入未收款在收款时更新原收入账单，不新增收支记录。"""
        created = client.post(
            "/debts",
            json={
                "record_type": "income",
                "category": "销售",
                "amount": "200",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "收瓜商",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        ).json()

        resp = client.post(
            "/debts/settle",
            json={"counterparty": "收瓜商"},
        )
        records = client.get("/costs").json()["items"]

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert data["record_type"] == "income"
        assert data["category"] == "销售"
        assert Decimal(data["settled_amount"]) == Decimal("200")
        assert Decimal(data["unsettled_amount"]) == Decimal("0")
        assert data["settlement_status"] == "settled"
        assert [
            item
            for item in records
            if item["id"] != created["id"] and item["parent_record_id"] == created["id"]
        ] == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/api/test_debt.py -v
```

Expected: settlement tests fail because `settle_debt` still creates an income repayment record.

- [ ] **Step 3: Update payable/receivable creation to default unsettled**

In `/Users/ljn/Documents/demo/explore/backend/app/services/debt_service.py`, import helpers:

```python
from app.services.cost_service import (
    UNSETTLED,
    _find_category,
    _quantize_money,
    settlement_status_for,
)
```

In `create_debt_record`, add fields to `CostRecord(...)`. Use the same fields for `record_type="cost"` payables and `record_type="income"` receivables so old mobile payloads with `record_subtype="赊账"` remain compatible:

```python
        settled_amount=Decimal("0.00"),
        settlement_status=UNSETTLED,
```

- [ ] **Step 4: Rewrite settle_debt to update the original record**

Replace `settle_debt` body after the query with this direct update of the original unsettled payable/receivable record:

```python
    if debt is None:
        raise ValueError(f"未找到 {counterparty} 的未结清账单")

    current_settled = Decimal(str(debt.settled_amount or 0))
    remaining = Decimal(str(debt.amount)) - current_settled
    settlement_amount = remaining if amount is None else _quantize_money(amount)
    if settlement_amount <= 0:
        raise ValueError("结算金额必须大于 0")
    if settlement_amount > remaining:
        settlement_amount = _quantize_money(remaining)

    debt.settled_amount = _quantize_money(current_settled + settlement_amount)
    debt.settlement_status = settlement_status_for(debt.amount, debt.settled_amount)
    if debt.settlement_status == "settled":
        debt.settled_at = datetime.now(timezone.utc)
    else:
        debt.settled_at = None

    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(debt)
    except Exception:
        db.rollback()
        raise
    return debt
```

Remove `repay_category` and `repay_record` creation from this function.

- [ ] **Step 5: Run debt tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/api/test_debt.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/debt_service.py backend/tests/api/test_debt.py
git commit -m "fix: settle debt on original ledger record"
```

---

### Task 3: Settlement-Aware Summaries and Legacy Repayment Exclusion

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/schemas/cost.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/cost_service.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/report_data_service.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/test_cost.py`

- [ ] **Step 1: Add failing summary tests**

Append to `/Users/ljn/Documents/demo/explore/backend/tests/test_cost.py`:

```python
def test_yearly_summary_separates_occurred_settled_and_unsettled(cycle_id):
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "肥料",
            "amount": "100.00",
            "record_date": "2025-03-10",
        },
    )
    client.post(
        "/debts",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "农药",
            "amount": "80.00",
            "record_date": "2025-03-11",
            "record_subtype": "赊账",
            "counterparty": "农资店",
            "due_date": "2025-04-01",
        },
    )
    client.post(
        "/debts",
        json={
            "cycle_id": cycle_id,
            "record_type": "income",
            "category": "销售",
            "amount": "200.00",
            "record_date": "2025-06-11",
            "record_subtype": "赊账",
            "counterparty": "收瓜商",
            "due_date": "2025-07-01",
        },
    )

    response = client.get("/costs/summary/2025")

    assert response.status_code == 200
    data = response.json()
    assert data["total_cost"] == "180.00"
    assert data["settled_cost"] == "100.00"
    assert data["unsettled_cost"] == "80.00"
    assert data["total_income"] == "200.00"
    assert data["settled_income"] == "0.00"
    assert data["unsettled_income"] == "200.00"


def test_legacy_repayment_record_is_excluded_from_income_summary(cycle_id):
    debt = client.post(
        "/debts",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "农药",
            "amount": "80.00",
            "record_date": "2025-03-11",
            "record_subtype": "赊账",
            "counterparty": "旧还款农资店",
            "due_date": "2025-04-01",
        },
    ).json()
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "income",
            "category": "还款",
            "amount": "80.00",
            "record_date": "2025-03-12",
            "parent_record_id": debt["id"],
            "counterparty": "旧还款农资店",
        },
    )

    response = client.get("/costs/summary/2025")

    assert response.status_code == 200
    data = response.json()
    assert data["total_income"] == "0"
    assert data["net_profit"] == "-80.00"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/test_cost.py::test_yearly_summary_separates_occurred_settled_and_unsettled tests/test_cost.py::test_legacy_repayment_record_is_excluded_from_income_summary -v
```

Expected: FAIL because summary response fields do not exist and old repayment records are still included.

- [ ] **Step 3: Extend summary schemas**

In `/Users/ljn/Documents/demo/explore/backend/app/schemas/cost.py`, update `CycleProfit`:

```python
class CycleProfit(BaseModel):
    """种植周期利润统计 Schema。"""

    cycle_id: int
    total_cost: Decimal
    total_income: Decimal
    net_profit: Decimal
    settled_cost: Decimal = Decimal("0")
    settled_income: Decimal = Decimal("0")
    unsettled_cost: Decimal = Decimal("0")
    unsettled_income: Decimal = Decimal("0")
    labor_cost: Decimal = Decimal("0")
    labor_entry_cost: Decimal = Decimal("0")
    operation_labor_cost: Decimal = Decimal("0")
    model_config = ConfigDict(from_attributes=True)
```

Update `YearlySummary`:

```python
class YearlySummary(BaseModel):
    """年度收支汇总 Schema。"""

    year: int
    total_cost: Decimal
    total_income: Decimal
    net_profit: Decimal
    settled_cost: Decimal = Decimal("0")
    settled_income: Decimal = Decimal("0")
    unsettled_cost: Decimal = Decimal("0")
    unsettled_income: Decimal = Decimal("0")
    by_category: dict[str, Decimal]
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Add repayment exclusion and settlement aggregation helpers**

In `/Users/ljn/Documents/demo/explore/backend/app/services/cost_service.py`, add below constants:

```python
REPAY_CATEGORY = "还款"
```

Add helpers:

```python
def is_legacy_repayment(record: CostRecord) -> bool:
    return (
        record.record_type == "income"
        and record.category == REPAY_CATEGORY
        and record.parent_record_id is not None
    )


def _active_business_records(records: list[CostRecord]) -> list[CostRecord]:
    return [record for record in records if not is_legacy_repayment(record)]


def _settled_amount(record: CostRecord) -> Decimal:
    return Decimal(str(record.settled_amount or 0))


def _unsettled_amount(record: CostRecord) -> Decimal:
    return max(Decimal(str(record.amount or 0)) - _settled_amount(record), Decimal("0"))
```

Update `get_cycle_profit` after loading records:

```python
    records = _active_business_records(records)
```

Compute settlement totals before return:

```python
    settled_cost = sum(
        (_settled_amount(r) for r in records if r.record_type == "cost"),
        Decimal("0"),
    )
    settled_income = sum(
        (_settled_amount(r) for r in records if r.record_type == "income"),
        Decimal("0"),
    )
    unsettled_cost = sum(
        (_unsettled_amount(r) for r in records if r.record_type == "cost"),
        Decimal("0"),
    )
    unsettled_income = sum(
        (_unsettled_amount(r) for r in records if r.record_type == "income"),
        Decimal("0"),
    )
```

Add these fields to `CycleProfit(...)`:

```python
        settled_cost=settled_cost,
        settled_income=settled_income,
        unsettled_cost=unsettled_cost,
        unsettled_income=unsettled_income,
```

Update `get_yearly_summary` loop:

```python
    records = _active_business_records(records)
    total_cost = Decimal("0")
    total_income = Decimal("0")
    settled_cost = Decimal("0")
    settled_income = Decimal("0")
    unsettled_cost = Decimal("0")
    unsettled_income = Decimal("0")
    by_category: dict[str, Decimal] = {}

    for r in records:
        if r.record_type == "cost":
            total_cost += r.amount
            settled_cost += _settled_amount(r)
            unsettled_cost += _unsettled_amount(r)
        elif r.record_type == "income":
            total_income += r.amount
            settled_income += _settled_amount(r)
            unsettled_income += _unsettled_amount(r)
        cat = f"{r.record_type}:{r.category}"
        by_category[cat] = by_category.get(cat, Decimal("0")) + r.amount
```

Add fields to `YearlySummary(...)`:

```python
        settled_cost=settled_cost,
        settled_income=settled_income,
        unsettled_cost=unsettled_cost,
        unsettled_income=unsettled_income,
```

- [ ] **Step 5: Exclude old repayment records from report data**

In `/Users/ljn/Documents/demo/explore/backend/app/services/report_data_service.py`, import:

```python
from app.services.cost_service import is_legacy_repayment
```

After loading `costs`, add:

```python
    costs = [record for record in costs if not is_legacy_repayment(record)]
```

Replace the total cost and total income DB aggregate queries with in-memory sums:

```python
    total_cost = sum(
        (record.amount for record in costs if record.record_type == "cost"),
        Decimal("0"),
    )
    total_income = sum(
        (record.amount for record in costs if record.record_type == "income"),
        Decimal("0"),
    )
```

- [ ] **Step 6: Run summary tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/test_cost.py::test_yearly_summary_separates_occurred_settled_and_unsettled tests/test_cost.py::test_legacy_repayment_record_is_excluded_from_income_summary tests/test_cost.py::test_cycle_profit -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/schemas/cost.py backend/app/services/cost_service.py backend/app/services/report_data_service.py backend/tests/test_cost.py
git commit -m "fix: separate ledger occurred and settled summaries"
```

---

### Task 4: Labor Cost Records Sync Settlement Status

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/labor_service.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_planting_operations.py`

- [ ] **Step 1: Add failing labor settlement assertions**

In `/Users/ljn/Documents/demo/explore/backend/tests/api/test_planting_operations.py`, update `test_create_work_order_with_labor_generates_cost_record` after `assert costs[0]["amount"] == "800.00"`:

```python
    assert costs[0]["settled_amount"] == "200.00"
    assert costs[0]["unsettled_amount"] == "600.00"
    assert costs[0]["settlement_status"] == "partial"
```

Update `test_save_wage_generates_single_traceable_labor_cost` after `assert cost["amount"] == "360.00"`:

```python
    assert cost["settled_amount"] == "100.00"
    assert cost["unsettled_amount"] == "260.00"
    assert cost["settlement_status"] == "partial"
```

Update `test_duplicate_wage_save_updates_source_cost_without_duplicate_expense` after `assert costs["items"][0]["amount"] == "400.00"`:

```python
    assert costs["items"][0]["settled_amount"] == "150.00"
    assert costs["items"][0]["unsettled_amount"] == "250.00"
    assert costs["items"][0]["settlement_status"] == "partial"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/api/test_planting_operations.py::test_create_work_order_with_labor_generates_cost_record tests/api/test_planting_operations.py::test_save_wage_generates_single_traceable_labor_cost tests/api/test_planting_operations.py::test_duplicate_wage_save_updates_source_cost_without_duplicate_expense -v
```

Expected: FAIL because synced labor cost records do not set `settled_amount`.

- [ ] **Step 3: Sync settled amount for operation work orders**

In `/Users/ljn/Documents/demo/explore/backend/app/services/labor_service.py`, import helper:

```python
from app.services.cost_service import _find_category, settlement_status_for
```

In `sync_work_order_labor_cost_record`, compute total paid after `total_payable`:

```python
    total_paid = sum(
        (entry.paid_amount for entry in work_order.labor_entries),
        Decimal("0"),
    )
```

Update `_apply_labor_cost_record(...)` call:

```python
        settled_amount=total_paid,
```

- [ ] **Step 4: Sync settled amount for single wage entries**

In `sync_labor_entry_cost_record`, update `_apply_labor_cost_record(...)` call:

```python
        settled_amount=entry.paid_amount,
```

Change `_apply_labor_cost_record` signature:

```python
def _apply_labor_cost_record(
    record: CostRecord,
    cycle_id: int | None,
    category: CostCategory | None,
    amount: Decimal,
    settled_amount: Decimal,
    record_date,
    note: str,
    subtype: str,
) -> None:
```

Inside `_apply_labor_cost_record`, add:

```python
    record.settled_amount = settled_amount
    record.settlement_status = settlement_status_for(amount, settled_amount)
```

- [ ] **Step 5: Ensure labor payment settlement refreshes source records**

In `/Users/ljn/Documents/demo/explore/backend/app/services/planting_service.py`, the existing `settle_labor_payment` already calls `sync_work_order_labor_cost_record` for affected entries. No new code is required here if Task 4 tests pass.

- [ ] **Step 6: Run labor tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/api/test_planting_operations.py::test_create_work_order_with_labor_generates_cost_record tests/api/test_planting_operations.py::test_save_wage_generates_single_traceable_labor_cost tests/api/test_planting_operations.py::test_duplicate_wage_save_updates_source_cost_without_duplicate_expense -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/labor_service.py backend/tests/api/test_planting_operations.py
git commit -m "fix: sync labor settlement status to ledger"
```

---

### Task 5: Mobile Settlement Display Helpers and UI

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/api/types.ts`
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/utils/recordDisplay.ts`
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/utils/__tests__/recordDisplay.test.ts`
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/components/RecordItem.tsx`
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/components/RecordDetailModal.tsx`
- Modify: `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/CostListScreen.tsx`

- [ ] **Step 1: Add failing utility tests**

Append to `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/utils/__tests__/recordDisplay.test.ts`:

```typescript
import {
  getLedgerSummary,
  getSettlementLabel,
  getUnsettledAmount,
} from "../recordDisplay";
```

If the file already has a grouped import from `../recordDisplay`, merge these names into that import instead of creating a duplicate import.

Append tests:

```typescript
  it("汇总发生额、已结金额和未结金额", () => {
    const records: CostRecord[] = [
      {
        ...baseRecord,
        id: 1,
        record_type: "cost",
        amount: "100.00",
        settled_amount: "100.00",
        settlement_status: "settled",
      },
      {
        ...baseRecord,
        id: 2,
        record_type: "cost",
        amount: "80.00",
        settled_amount: "30.00",
        settlement_status: "partial",
      },
      {
        ...baseRecord,
        id: 3,
        record_type: "income",
        amount: "200.00",
        settled_amount: "0.00",
        settlement_status: "unsettled",
      },
    ];

    expect(getLedgerSummary(records)).toEqual({
      occurredCost: 180,
      occurredIncome: 200,
      settledCost: 130,
      settledIncome: 0,
      unsettledCost: 50,
      unsettledIncome: 200,
    });
  });

  it("生成结算状态文案", () => {
    expect(
      getSettlementLabel({
        ...baseRecord,
        record_type: "cost",
        amount: "80.00",
        settled_amount: "30.00",
        settlement_status: "partial",
      })
    ).toBe("已付 ¥30 · 未付 ¥50");

    expect(
      getSettlementLabel({
        ...baseRecord,
        record_type: "income",
        amount: "200.00",
        settled_amount: "0.00",
        settlement_status: "unsettled",
      })
    ).toBe("未收 ¥200");

    expect(getUnsettledAmount(baseRecord)).toBe(120);
  });
```

- [ ] **Step 2: Run utility tests and verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/FarmManagerMobile
npm test -- --runTestsByPath src/screens/cost/utils/__tests__/recordDisplay.test.ts
```

Expected: FAIL because the helper functions are missing.

- [ ] **Step 3: Add settlement fields to mobile type**

In `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/api/types.ts`, update `CostRecord`:

```typescript
export interface CostRecord {
  id: number;
  cycle_id: number | null;
  record_type: string;
  category: string;
  amount: string;
  settled_amount?: string;
  settlement_status?: "unsettled" | "partial" | "settled" | string;
  unsettled_amount?: string;
  record_date: string;
  note: string | null;
  record_subtype?: string;
  counterparty?: string;
  due_date?: string;
  settled_at?: string;
  parent_record_id?: number;
  source_type?: string | null;
  source_id?: number | null;
  source_label?: string | null;
  created_at?: string;
  createdAt?: string;
}
```

- [ ] **Step 4: Add settlement utilities**

In `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/utils/recordDisplay.ts`, export `toAmountNumber` by changing:

```typescript
function toAmountNumber(amount: string): number {
```

to:

```typescript
export function toAmountNumber(amount: string | number | undefined | null): number {
```

and update the body:

```typescript
  const parsed = Number(String(amount ?? "0").replace(/,/g, ""));
```

Add below `formatRecordAmount`:

```typescript
export interface LedgerSummary {
  occurredCost: number;
  occurredIncome: number;
  settledCost: number;
  settledIncome: number;
  unsettledCost: number;
  unsettledIncome: number;
}

export function getSettledAmount(record: CostRecord): number {
  if (record.settled_amount !== undefined && record.settled_amount !== null) {
    return toAmountNumber(record.settled_amount);
  }
  if (record.settlement_status === "unsettled") {
    return 0;
  }
  return toAmountNumber(record.amount);
}

export function getUnsettledAmount(record: CostRecord): number {
  if (record.unsettled_amount !== undefined && record.unsettled_amount !== null) {
    return toAmountNumber(record.unsettled_amount);
  }
  return Math.max(toAmountNumber(record.amount) - getSettledAmount(record), 0);
}

export function getLedgerSummary(records: CostRecord[]): LedgerSummary {
  return records.reduce<LedgerSummary>(
    (summary, record) => {
      const amount = toAmountNumber(record.amount);
      const settled = getSettledAmount(record);
      const unsettled = getUnsettledAmount(record);
      if (record.record_type === "income") {
        summary.occurredIncome += amount;
        summary.settledIncome += settled;
        summary.unsettledIncome += unsettled;
      } else {
        summary.occurredCost += amount;
        summary.settledCost += settled;
        summary.unsettledCost += unsettled;
      }
      return summary;
    },
    {
      occurredCost: 0,
      occurredIncome: 0,
      settledCost: 0,
      settledIncome: 0,
      unsettledCost: 0,
      unsettledIncome: 0,
    }
  );
}

export function getSettlementLabel(record: CostRecord): string | null {
  const status = record.settlement_status;
  if (!status || status === "settled") {
    return null;
  }
  const settled = getSettledAmount(record);
  const unsettled = getUnsettledAmount(record);
  const settledVerb = record.record_type === "income" ? "已收" : "已付";
  const unsettledVerb = record.record_type === "income" ? "未收" : "未付";
  if (status === "partial") {
    return `${settledVerb} ${formatRecordAmount(String(settled))} · ${unsettledVerb} ${formatRecordAmount(String(unsettled))}`;
  }
  return `${unsettledVerb} ${formatRecordAmount(String(unsettled))}`;
}
```

- [ ] **Step 5: Update RecordItem metadata**

In `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/components/RecordItem.tsx`, add import:

```typescript
  getSettlementLabel,
```

Add:

```typescript
  const settlementLabel = getSettlementLabel(item);
```

Insert `settlementLabel` into `metaParts` before `item.source_label`:

```typescript
    settlementLabel,
```

- [ ] **Step 6: Update detail modal settlement rows**

In `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/components/RecordDetailModal.tsx`, add imports:

```typescript
  formatRecordAmount,
  getSettledAmount,
  getUnsettledAmount,
  getSettlementLabel,
```

Add after `sourceLabel`:

```typescript
  const settlementLabel = getSettlementLabel(record);
  const settledAmount = getSettledAmount(record);
  const unsettledAmount = getUnsettledAmount(record);
```

Inside `<View style={styles.details}>`, after the date row, add:

```tsx
            {settlementLabel ? (
              <>
                <View style={styles.detailRow}>
                  <View style={styles.detailLeft}>
                    <Icon
                      name="check-circle-outline"
                      size={18}
                      color={colors.textSecondary}
                    />
                    <Text style={styles.detailLabel}>
                      {isCost ? "已付" : "已收"}
                    </Text>
                  </View>
                  <Text style={styles.detailValue}>
                    {formatRecordAmount(String(settledAmount))}
                  </Text>
                </View>
                <View style={styles.detailRow}>
                  <View style={styles.detailLeft}>
                    <Icon
                      name="clock-alert-outline"
                      size={18}
                      color={colors.textSecondary}
                    />
                    <Text style={styles.detailLabel}>
                      {isCost ? "未付" : "未收"}
                    </Text>
                  </View>
                  <Text style={styles.detailValue}>
                    {formatRecordAmount(String(unsettledAmount))}
                  </Text>
                </View>
              </>
            ) : null}
```

- [ ] **Step 7: Update CostListScreen summary calculation**

In `/Users/ljn/Documents/demo/explore/FarmManagerMobile/src/screens/cost/CostListScreen.tsx`, import:

```typescript
  getLedgerSummary,
```

Change `AssetCard` props:

```typescript
const AssetCard: React.FC<{
  occurredIncome: number;
  occurredCost: number;
  settledIncome: number;
  settledCost: number;
  unsettledIncome: number;
  unsettledCost: number;
}> = ({
  occurredIncome,
  occurredCost,
  settledIncome,
  settledCost,
  unsettledIncome,
  unsettledCost,
}) => {
  const cashBalance = settledIncome - settledCost;
```

Use `cashBalance` for the main amount and label it `本月已结余`. Change sub labels to:

```tsx
          <Text style={assetStyles.subLabel}>发生收入</Text>
          <Text style={[assetStyles.subAmount, { color: colors.income }]}>
            +{occurredIncome.toFixed(2)}
          </Text>
```

```tsx
          <Text style={assetStyles.subLabel}>发生支出</Text>
          <Text style={[assetStyles.subAmount, { color: colors.expense }]}>
            -{occurredCost.toFixed(2)}
          </Text>
```

Add a small row below the existing sub row:

```tsx
      <View style={assetStyles.subRow}>
        <View style={assetStyles.subItem}>
          <Text style={assetStyles.subLabel}>未收</Text>
          <Text style={[assetStyles.subAmount, { color: colors.income }]}>
            +{unsettledIncome.toFixed(2)}
          </Text>
        </View>
        <View style={assetStyles.subDivider} />
        <View style={assetStyles.subItem}>
          <Text style={assetStyles.subLabel}>未付</Text>
          <Text style={[assetStyles.subAmount, { color: colors.expense }]}>
            -{unsettledCost.toFixed(2)}
          </Text>
        </View>
      </View>
```

Replace current `stats` calculation:

```typescript
    const summary = getLedgerSummary(monthRecords);
    return summary;
```

Update usage:

```tsx
            <AssetCard
              occurredIncome={stats.occurredIncome}
              occurredCost={stats.occurredCost}
              settledIncome={stats.settledIncome}
              settledCost={stats.settledCost}
              unsettledIncome={stats.unsettledIncome}
              unsettledCost={stats.unsettledCost}
            />
```

- [ ] **Step 8: Run mobile utility tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/FarmManagerMobile
npm test -- --runTestsByPath src/screens/cost/utils/__tests__/recordDisplay.test.ts
```

Expected: PASS.

- [ ] **Step 9: Commit Task 5**

```bash
cd /Users/ljn/Documents/demo/explore
git add FarmManagerMobile/src/api/types.ts FarmManagerMobile/src/screens/cost/utils/recordDisplay.ts FarmManagerMobile/src/screens/cost/utils/__tests__/recordDisplay.test.ts FarmManagerMobile/src/screens/cost/components/RecordItem.tsx FarmManagerMobile/src/screens/cost/components/RecordDetailModal.tsx FarmManagerMobile/src/screens/cost/CostListScreen.tsx
git commit -m "feat: show ledger settlement status on mobile"
```

---

### Task 6: Final Verification and OpenSpec Task Sync

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/openspec/changes/simplify-ledger-settlement-status/tasks.md`

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/python -m pytest tests/test_cost.py tests/api/test_debt.py tests/api/test_planting_operations.py -v
```

Expected: PASS.

- [ ] **Step 2: Run focused mobile tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/FarmManagerMobile
npm test -- --runTestsByPath src/screens/cost/utils/__tests__/recordDisplay.test.ts src/stores/__tests__/costStore.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run lint/format checks**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
./.venv/bin/ruff check .
./.venv/bin/ruff format . --check
```

Expected: PASS. If formatting fails, run `./.venv/bin/ruff format .`, then re-run `./.venv/bin/ruff check .` and `./.venv/bin/ruff format . --check`.

Run:

```bash
cd /Users/ljn/Documents/demo/explore/FarmManagerMobile
npm run lint
```

Expected: PASS or only pre-existing unrelated warnings documented in the final report.

- [ ] **Step 4: Update OpenSpec task checkboxes**

In `/Users/ljn/Documents/demo/explore/openspec/changes/simplify-ledger-settlement-status/tasks.md`, mark completed implementation items with `[x]`. Use this exact style:

```markdown
- [x] 1.1 为 `cost_records` 增加 `settled_amount` 和 `settlement_status` 字段，并补充模型、schema、迁移脚本
```

Do not mark a task complete unless the corresponding tests or verification command passed.

- [ ] **Step 5: Check changed files**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git status --short
```

Expected: only files touched by this plan and OpenSpec task checkbox updates are listed.

- [ ] **Step 6: Commit verification updates**

```bash
cd /Users/ljn/Documents/demo/explore
git add openspec/changes/simplify-ledger-settlement-status/tasks.md
git commit -m "chore: mark ledger settlement tasks complete"
```

---

## Self-Review

**Spec coverage:**  
- `ledger-settlement-status` creation defaults are covered in Task 1 and Task 2.  
- Settlement updates on original payable and receivable records are covered in Task 2.  
- Occurred/settled/unsettled summaries and legacy repayment exclusion are covered in Task 3.  
- Labor settlement alignment is covered in Task 4.  
- Ledger UI summary and labels are covered in Task 5.  
- Verification and OpenSpec task sync are covered in Task 6.

**Placeholder scan:**  
No `TBD`, `TODO`, `implement later`, or vague “add appropriate handling” instructions remain. Every code-changing step includes concrete snippets or exact assertions.

**Type consistency:**  
The settlement field names are consistent across backend and mobile: `settled_amount`, `settlement_status`, `unsettled_amount`. Status values are `unsettled`, `partial`, and `settled`.
