"""种植单元、作业单和用工 API Schema。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlantingUnitBase(BaseModel):
    """种植单元基础字段。"""

    cycle_id: int
    name: str = Field(..., min_length=1, max_length=100)
    area_mu: Decimal | None = Field(None, ge=0, le=100000)
    planted_date: date | None = None
    status: str = Field("active", max_length=20)
    note: str | None = Field(None, max_length=500)


class PlantingUnitCreate(PlantingUnitBase):
    """创建种植单元请求。"""


class PlantingUnitUpdate(BaseModel):
    """更新种植单元请求。"""

    name: str | None = Field(None, min_length=1, max_length=100)
    area_mu: Decimal | None = Field(None, ge=0, le=100000)
    planted_date: date | None = None
    status: str | None = Field(None, max_length=20)
    note: str | None = Field(None, max_length=500)


class PlantingUnitResponse(PlantingUnitBase):
    """种植单元响应。"""

    id: int
    farm_id: int
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class WorkerBase(BaseModel):
    """工人基础字段。"""

    name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=30)
    default_pay_type: str = Field("daily", max_length=20)
    default_unit_price: Decimal | None = Field(None, ge=0, le=100000)
    note: str | None = Field(None, max_length=500)
    status: str = Field("active", max_length=20)


class WorkerCreate(WorkerBase):
    """创建工人请求。"""


class WorkerUpdate(BaseModel):
    """更新工人请求。"""

    name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=30)
    default_pay_type: str | None = Field(None, max_length=20)
    default_unit_price: Decimal | None = Field(None, ge=0, le=100000)
    note: str | None = Field(None, max_length=500)
    status: str | None = Field(None, max_length=20)


class WorkerResponse(WorkerBase):
    """工人响应。"""

    id: int
    farm_id: int
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class LaborEntryCreate(BaseModel):
    """作业单用工明细创建请求。"""

    worker_id: int
    pay_type: str = Field("daily", max_length=20)
    quantity: Decimal = Field(Decimal("1"), gt=0, le=100000)
    unit_price: Decimal = Field(..., ge=0, le=100000)
    payable_amount: Decimal | None = Field(None, ge=0, le=10000000)
    paid_amount: Decimal = Field(Decimal("0"), ge=0, le=10000000)
    note: str | None = Field(None, max_length=500)

    @field_validator("quantity", "unit_price", "paid_amount", "payable_amount")
    @classmethod
    def _validate_money_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("金额和数量最多保留两位小数")
        return v


class WageSaveRequest(BaseModel):
    """独立记工资保存请求。"""

    cycle_id: int
    operation_type: str = Field(..., min_length=1, max_length=50)
    worker_id: int | None = None
    worker_name: str | None = Field(None, min_length=1, max_length=100)
    crop_name: str | None = Field(None, max_length=100)
    pay_type: str = Field("daily", max_length=20)
    quantity: Decimal = Field(Decimal("1"), gt=0, le=100000)
    unit_price: Decimal = Field(..., ge=0, le=100000)
    paid_amount: Decimal = Field(Decimal("0"), ge=0, le=10000000)
    note: str | None = Field(None, max_length=500)
    work_date: date
    client_request_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("worker_name")
    @classmethod
    def _normalize_worker_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("工人名称不能为空")
        return stripped

    @field_validator("quantity", "unit_price", "paid_amount")
    @classmethod
    def _validate_money_precision(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("金额和数量最多保留两位小数")
        return v


class WageUpdateRequest(BaseModel):
    """独立工资更新请求。"""

    cycle_id: int | None = None
    operation_type: str | None = Field(None, min_length=1, max_length=50)
    worker_id: int | None = None
    worker_name: str | None = Field(None, min_length=1, max_length=100)
    crop_name: str | None = Field(None, max_length=100)
    pay_type: str | None = Field(None, max_length=20)
    quantity: Decimal | None = Field(None, ge=0, le=100000)
    unit_price: Decimal | None = Field(None, ge=0, le=100000)
    paid_amount: Decimal | None = Field(None, ge=0, le=10000000)
    note: str | None = Field(None, max_length=500)
    work_date: date | None = None

    @field_validator("worker_name")
    @classmethod
    def _normalize_worker_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("工人名称不能为空")
        return stripped

    @field_validator("quantity", "unit_price", "paid_amount")
    @classmethod
    def _validate_money_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("金额和数量最多保留两位小数")
        return v


class LaborEntryResponse(BaseModel):
    """作业单用工明细响应。"""

    id: int
    farm_id: int
    work_order_id: int
    worker_id: int
    worker_name: str | None = None
    pay_type: str
    quantity: Decimal
    unit_price: Decimal
    payable_amount: Decimal
    paid_amount: Decimal
    unpaid_amount: Decimal
    settlement_status: str
    note: str | None = None
    model_config = ConfigDict(from_attributes=True)


class WageSaveResponse(LaborEntryResponse):
    """独立记工资保存响应。"""

    cycle_id: int
    operation_type: str
    worker_name: str
    cost_record_id: int | None = None


class WorkerCycleLaborSummary(BaseModel):
    """工人在单个茬口下的用工摘要。"""

    cycle_id: int | None = None
    cycle_name: str | None = None
    total_payable: Decimal
    total_paid: Decimal
    total_unpaid: Decimal
    entry_count: int


class WorkerLaborSummary(WorkerResponse):
    """工人管理列表摘要。"""

    total_payable: Decimal = Decimal("0")
    total_paid: Decimal = Decimal("0")
    total_unpaid: Decimal = Decimal("0")
    entry_count: int = 0
    cycle_summaries: list[WorkerCycleLaborSummary] = Field(default_factory=list)


class OperationWorkOrderBase(BaseModel):
    """农事作业单基础字段。"""

    cycle_id: int | None = None
    operation_type: str = Field(..., min_length=1, max_length=50)
    operation_date: date
    scope_type: str = Field("cycle", max_length=20)
    unit_ids: list[int] = Field(default_factory=list)
    note: str | None = Field(None, max_length=500)
    photo_urls: str | None = None


class OperationWorkOrderCreate(OperationWorkOrderBase):
    """创建农事作业单请求。"""

    labor_entries: list[LaborEntryCreate] = Field(default_factory=list)


class OperationWorkOrderResponse(OperationWorkOrderBase):
    """农事作业单响应。"""

    id: int
    farm_id: int
    cycle_name: str | None = None
    unit_names: list[str] = Field(default_factory=list)
    labor_entries: list[LaborEntryResponse] = Field(default_factory=list)
    labor_cost_record_id: int | None = None
    total_payable_amount: Decimal = Decimal("0")
    total_paid_amount: Decimal = Decimal("0")
    total_unpaid_amount: Decimal = Decimal("0")
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class OperationTypeResponse(BaseModel):
    """作业类型响应。"""

    name: str
    crop: str | None = None
    is_builtin: bool = True
    sort_order: int = 0


class RecentOperationResponse(BaseModel):
    """近期农事合并视图。"""

    source_type: str
    source_id: int
    cycle_id: int | None = None
    cycle_name: str | None = None
    operation_type: str
    operation_date: date
    scope_text: str | None = None
    note: str | None = None
