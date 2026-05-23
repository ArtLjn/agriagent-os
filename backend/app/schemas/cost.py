from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class CostRecordBase(BaseModel):
    """成本记账基础 Schema。"""

    cycle_id: int | None = None
    record_type: str
    category: str
    amount: Decimal
    record_date: date
    note: str | None = None


class CostRecordCreate(CostRecordBase):
    """创建成本记账记录请求 Schema。"""

    pass


class CostRecordResponse(CostRecordBase):
    """成本记账记录响应 Schema。"""

    id: int
    model_config = ConfigDict(from_attributes=True)


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
