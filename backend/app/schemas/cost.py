from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


RECORD_TYPE_ENUM = {"cost", "income"}


class CostRecordBase(BaseModel):
    """成本记账基础 Schema。"""

    cycle_id: int | None = None
    record_type: str
    category: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=0, le=10_000_000)
    record_date: date
    note: str | None = Field(None, max_length=500)
    record_subtype: str | None = Field(None, max_length=50)
    counterparty: str | None = Field(None, max_length=100)
    due_date: date | None = None
    settled_at: datetime | None = None
    parent_record_id: int | None = None

    @field_validator("record_type")
    @classmethod
    def _validate_record_type(cls, v: str) -> str:
        if v not in RECORD_TYPE_ENUM:
            raise ValueError(f"record_type 必须是 {RECORD_TYPE_ENUM} 之一")
        return v

    @field_validator("amount")
    @classmethod
    def _validate_amount_precision(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("amount 最多保留两位小数")
        return v


class CostRecordCreate(CostRecordBase):
    """创建成本记账记录请求 Schema。"""

    pass


class CostRecordResponse(CostRecordBase):
    """成本记账记录响应 Schema。"""

    id: int
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class CostRecordUpdate(BaseModel):
    """更新成本记账记录请求 Schema。"""

    cycle_id: int | None = None
    record_type: str | None = None
    category: str | None = Field(None, min_length=1, max_length=50)
    amount: Decimal | None = Field(None, gt=0, le=10_000_000)
    record_date: date | None = None
    note: str | None = Field(None, max_length=500)
    record_subtype: str | None = Field(None, max_length=50)
    counterparty: str | None = Field(None, max_length=100)
    due_date: date | None = None
    settled_at: datetime | None = None
    parent_record_id: int | None = None

    @field_validator("record_type")
    @classmethod
    def _validate_record_type(cls, v: str | None) -> str | None:
        if v is not None and v not in RECORD_TYPE_ENUM:
            raise ValueError(f"record_type 必须是 {RECORD_TYPE_ENUM} 之一")
        return v

    @field_validator("amount")
    @classmethod
    def _validate_amount_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("amount 最多保留两位小数")
        return v


class CycleProfit(BaseModel):
    """种植周期利润统计 Schema。"""

    cycle_id: int
    total_cost: Decimal
    total_income: Decimal
    net_profit: Decimal
    model_config = ConfigDict(from_attributes=True)


class YearlySummary(BaseModel):
    """年度收支汇总 Schema。"""

    year: int
    total_cost: Decimal
    total_income: Decimal
    net_profit: Decimal
    by_category: dict[str, Decimal]
    model_config = ConfigDict(from_attributes=True)


class CostParseRequest(BaseModel):
    """AI 解析记账描述请求。"""

    description: str = Field(..., min_length=1, max_length=500)


class CostParseResponse(BaseModel):
    """AI 解析记账描述响应。"""

    record_type: str
    category: str
    amount: str
    record_date: str
    note: str | None = None

    @field_validator("record_type")
    @classmethod
    def _validate_record_type(cls, v: str) -> str:
        if v not in RECORD_TYPE_ENUM:
            raise ValueError(f"record_type 必须是 {RECORD_TYPE_ENUM} 之一")
        return v

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, v: str) -> str:
        try:
            d = Decimal(v)
        except Exception:
            raise ValueError("amount 必须是有效的数字字符串")
        if d <= 0:
            raise ValueError("amount 必须大于 0")
        if d > 10_000_000:
            raise ValueError("amount 不能超过 10,000,000")
        return v

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
